"""媒体文件探测与缩略图生成。

同一条 I/O 路径服务两个入口（probe_file / make_thumbnail），约束如下：

- path 一律为 workspace 相对路径，先按 root 做 normalize + realpath；
  含 ``..`` 或经软链接逃出 root 的路径直接返回结构化错误。
- 缓存身份 = 规范化后的相对路径 + mtime_ns + size（不整读文件做 hash），
  因此 workspace 内指向同一目标的多个软链复用同一份缩略图。
- 大小上限在 stat 阶段拦截，探测不整读文件；缩略图解码前再查
  扩展名白名单与解压尺寸上限。
- 缩略图只写 user_data 下的缓存目录，临时文件 + os.replace 原子落盘，
  并发读不会看到半张图；命中缓存后仍重开校验格式与边长，坏缓存丢弃重建。
- 图片走 Pillow；音频优先 mutagen，import 失败时降级解析 WAV/MP3 文件头，
  两条路径返回同一套 metadata；文件头截断报 corrupt，不猜成 0 时长。
"""

import hashlib
import logging
import os
import struct
import tempfile
from pathlib import Path, PurePosixPath
from typing import Any, Dict, Optional, Tuple

from ..security import PathValidator

try:
    from PIL import Image
except ImportError:  # pragma: no cover - Pillow 缺失时在调用处报 dependency_missing
    Image = None  # type: ignore

try:
    from mutagen import File as _mutagen_file
except ImportError:
    # mutagen 为可选依赖；缺失时降级为 WAV/MP3 文件头解析
    _mutagen_file = None

logger = logging.getLogger(__name__)

DEFAULT_IMAGE_EXTENSIONS = {".png", ".jpg", ".jpeg", ".gif", ".bmp", ".webp"}
DEFAULT_AUDIO_EXTENSIONS = {".wav", ".mp3"}

# MP3 V1 Layer III / V2&V2.5 Layer III 比特率表（kbps）
_MP3_BITRATE_V1_L3 = [0, 32, 40, 48, 56, 64, 80, 96, 112, 128, 160, 192, 224, 256, 320]
_MP3_BITRATE_V2_L3 = [0, 8, 16, 24, 32, 40, 48, 56, 64, 80, 96, 112, 128, 144, 160]
_MP3_SAMPLE_RATES = {
    3: [44100, 48000, 32000],   # MPEG 1
    2: [22050, 24000, 16000],   # MPEG 2
    0: [11025, 12000, 8000],    # MPEG 2.5
}


class MediaError(Exception):
    """结构化媒体错误，code 写入返回值的 error 字段。"""

    def __init__(self, code: str, message: str):
        super().__init__(message)
        self.code = code
        self.message = message


def _audio_metadata(
    duration_seconds: float,
    sample_rate: Optional[int],
    channels: Optional[int],
    bitrate: Optional[int],
    codec: str,
    parser: str,
) -> Dict[str, Any]:
    """音频统一 metadata 结构，mutagen 与文件头降级两条路径共用。"""
    return {
        "duration_seconds": round(float(duration_seconds), 3),
        "sample_rate": sample_rate,
        "channels": channels,
        "bitrate": bitrate,
        "codec": codec,
        "parser": parser,
    }


class MediaOperations:
    """媒体探测与缩略图操作，入口仅 probe_file / make_thumbnail。"""

    def __init__(
        self,
        validator: PathValidator,
        config: Optional[Dict[str, Any]] = None,
        workspace_root: Optional[Path] = None,
        cache_root: Optional[Path] = None,
    ):
        self.validator = validator
        config = config or {}
        self.max_file_size = int(config.get("max_file_size_mb", 200)) * 1024 * 1024
        self.default_thumbnail_size = int(config.get("default_thumbnail_size", 128))
        self.max_thumbnail_size = int(config.get("max_thumbnail_size", 1024))
        self.max_image_pixels = int(config.get("max_image_pixels", 40_000_000))
        allowed = config.get("allowed_extensions") or {}
        self.image_extensions = {
            e.lower() for e in allowed.get("image", DEFAULT_IMAGE_EXTENSIONS)
        }
        self.audio_extensions = {
            e.lower() for e in allowed.get("audio", DEFAULT_AUDIO_EXTENSIONS)
        }

        # 规范化 root，用于 realpath 后的相对路径计算与逃逸检测
        if workspace_root is not None:
            self.root: Optional[Path] = Path(workspace_root).resolve()
        elif validator.virtual_root is not None:
            self.root = validator.virtual_root
        elif validator.allowed_dirs:
            self.root = Path(sorted(validator.allowed_dirs)[0]).resolve()
        else:
            self.root = None

        # 缓存目录只落在 user_data（cache_root）之下
        cache_dir = Path(config.get("cache_dir", ".cache/media"))
        if not cache_dir.is_absolute():
            base = Path(cache_root) if cache_root else (
                self.root.parent if self.root else Path.cwd()
            )
            cache_dir = base / cache_dir
        self.cache_dir = cache_dir.resolve()

    # ========== 内部：路径与 stat ==========

    async def _resolve(self, path: str) -> Tuple[Path, str]:
        """normalize + realpath，返回 (真实路径, 规范化相对路径缓存身份)。

        含 '..' 或软链逃出 root 时抛 MediaError（结构化报错）。
        """
        if not isinstance(path, str) or not path.strip():
            raise MediaError("invalid_path", "path must be a non-empty workspace-relative string")
        if any(p == ".." for p in PurePosixPath(path.replace("\\", "/")).parts):
            raise MediaError("path_traversal", f"path contains '..': {path}")

        abs_path, allowed = await self.validator.validate_path(path)
        if not allowed:
            raise MediaError("path_outside_root", f"path is outside the workspace: {path}")

        try:
            real = abs_path.resolve()
        except OSError:
            raise MediaError("invalid_path", f"cannot resolve path: {path}")

        if self.root is not None:
            try:
                rel = real.relative_to(self.root)
            except ValueError:
                raise MediaError(
                    "path_outside_root",
                    f"symlink target escapes the workspace: {path}",
                )
            rel_key = os.path.normcase(rel.as_posix())
        else:
            rel_key = os.path.normcase(str(real))
        return real, rel_key

    def _stat_checked(self, real: Path, path: str) -> os.stat_result:
        """stat 阶段拦截大小上限，探测不整读文件。"""
        try:
            st = real.stat()
        except FileNotFoundError:
            raise MediaError("not_found", f"file not found: {path}")
        except OSError:
            raise MediaError("unreadable", f"cannot stat file: {path}")
        if not real.is_file():
            raise MediaError("not_a_file", f"not a regular file: {path}")
        if st.st_size > self.max_file_size:
            raise MediaError(
                "too_large",
                f"file exceeds size limit ({st.st_size} > {self.max_file_size} bytes): {path}",
            )
        return st

    # ========== 入口 1：探测 ==========

    async def probe_file(self, path: str) -> Dict[str, Any]:
        """探测图片/音频元数据。超限、损坏、类型不支持均返回 error 字段。"""
        try:
            real, _rel_key = await self._resolve(path)
            st = self._stat_checked(real, path)
            ext = real.suffix.lower()
            if ext in self.image_extensions:
                kind = "image"
                metadata = self._probe_image(real, path)
            elif ext in self.audio_extensions:
                kind = "audio"
                metadata = self._probe_audio(real, st.st_size, path)
            else:
                raise MediaError(
                    "unsupported_type",
                    f"unsupported media type '{ext or '(none)'}': {path}",
                )
        except MediaError as e:
            return {"success": False, "error": e.code, "message": e.message}
        return {
            "success": True,
            "path": path,
            "type": kind,
            "size": st.st_size,
            "mtime_ns": st.st_mtime_ns,
            "metadata": metadata,
        }

    def _probe_image(self, real: Path, path: str) -> Dict[str, Any]:
        if Image is None:
            raise MediaError("dependency_missing", "Pillow is not installed")
        try:
            with Image.open(real) as img:
                return {
                    "format": img.format,
                    "width": img.width,
                    "height": img.height,
                    "mode": img.mode,
                    "frames": getattr(img, "n_frames", 1),
                }
        except MediaError:
            raise
        except Exception:
            raise MediaError("corrupt", f"cannot decode image header: {path}")

    def _probe_audio(self, real: Path, size: int, path: str) -> Dict[str, Any]:
        ext = real.suffix.lower()
        if _mutagen_file is not None:
            try:
                audio = _mutagen_file(str(real))
            except Exception:
                audio = None
            if audio is not None and getattr(audio, "info", None) is not None:
                info = audio.info
                duration = getattr(info, "length", None)
                if duration and duration > 0:
                    return _audio_metadata(
                        duration_seconds=float(duration),
                        sample_rate=getattr(info, "sample_rate", None),
                        channels=getattr(info, "channels", None),
                        bitrate=getattr(info, "bitrate", None),
                        codec=ext.lstrip("."),
                        parser="mutagen",
                    )
            # mutagen 解析失败时继续走文件头降级，截断会在那里报 corrupt
        if ext == ".wav":
            return self._probe_wav(real, path)
        if ext == ".mp3":
            return self._probe_mp3(real, size, path)
        raise MediaError(
            "unsupported_type",
            f"no fallback parser for audio type '{ext}' (mutagen unavailable): {path}",
        )

    def _probe_wav(self, real: Path, path: str) -> Dict[str, Any]:
        """解析 WAV 文件头（RIFF/fmt/data），不整读文件。"""
        try:
            with open(real, "rb") as f:
                header = f.read(12)
                if len(header) < 12 or header[:4] != b"RIFF" or header[8:12] != b"WAVE":
                    raise MediaError("corrupt", f"invalid WAV header: {path}")
                fmt_data = None
                data_size = None
                while fmt_data is None or data_size is None:
                    chunk_header = f.read(8)
                    if len(chunk_header) < 8:
                        break
                    chunk_id = chunk_header[:4]
                    chunk_size = struct.unpack("<I", chunk_header[4:])[0]
                    if chunk_id == b"fmt ":
                        fmt_data = f.read(min(chunk_size, 16))
                        if len(fmt_data) < 16:
                            raise MediaError("corrupt", f"truncated WAV fmt chunk: {path}")
                        rest = chunk_size - 16
                        if rest > 0:
                            f.seek(rest, os.SEEK_CUR)
                    elif chunk_id == b"data":
                        data_size = chunk_size
                        if fmt_data is not None:
                            break
                        f.seek(chunk_size, os.SEEK_CUR)
                    else:
                        f.seek(chunk_size, os.SEEK_CUR)
                    if chunk_size % 2:
                        f.seek(1, os.SEEK_CUR)  # RIFF 块按字对齐
            if fmt_data is None or data_size is None:
                raise MediaError("corrupt", f"truncated WAV file (missing fmt/data chunk): {path}")
            _audio_format, channels, sample_rate, byte_rate, _block_align, _bits = struct.unpack(
                "<HHIIHH", fmt_data
            )
            if byte_rate == 0 or channels == 0 or sample_rate == 0:
                raise MediaError("corrupt", f"invalid WAV fmt fields: {path}")
            duration = data_size / byte_rate
            if duration <= 0:
                raise MediaError("corrupt", f"WAV has no audio data: {path}")
            return _audio_metadata(
                duration_seconds=duration,
                sample_rate=sample_rate,
                channels=channels,
                bitrate=byte_rate * 8,
                codec="wav",
                parser="header",
            )
        except MediaError:
            raise
        except OSError:
            raise MediaError("corrupt", f"cannot read WAV file: {path}")

    def _probe_mp3(self, real: Path, size: int, path: str) -> Dict[str, Any]:
        """解析 MP3 首个有效帧头估算时长，不整读文件。"""
        try:
            with open(real, "rb") as f:
                head = f.read(10)
                offset = 0
                if len(head) == 10 and head[:3] == b"ID3":
                    tag_size = 0
                    for b in head[6:10]:
                        tag_size = (tag_size << 7) | (b & 0x7F)
                    offset = 10 + tag_size
                f.seek(offset)
                window = f.read(65536)
        except OSError:
            raise MediaError("corrupt", f"cannot read MP3 file: {path}")

        i = 0
        while i + 4 <= len(window):
            b1, b2, b3, b4 = window[i : i + 4]
            if b1 == 0xFF and (b2 & 0xE0) == 0xE0:
                version = (b2 >> 3) & 0x3
                layer = (b2 >> 1) & 0x3
                bitrate_idx = (b3 >> 4) & 0xF
                sr_idx = (b3 >> 2) & 0x3
                if version == 1 or layer != 1 or bitrate_idx in (0, 15) or sr_idx == 3:
                    i += 1
                    continue
                table = _MP3_BITRATE_V1_L3 if version == 3 else _MP3_BITRATE_V2_L3
                bitrate = table[bitrate_idx] * 1000
                sample_rate = _MP3_SAMPLE_RATES[version][sr_idx]
                channels = 1 if ((b4 >> 6) & 0x3) == 3 else 2
                audio_bytes = max(0, size - offset)
                duration = audio_bytes * 8 / bitrate
                if duration <= 0:
                    raise MediaError("corrupt", f"MP3 has no audio frames: {path}")
                return _audio_metadata(
                    duration_seconds=duration,
                    sample_rate=sample_rate,
                    channels=channels,
                    bitrate=bitrate,
                    codec="mp3",
                    parser="header",
                )
            i += 1
        raise MediaError("corrupt", f"no valid MP3 frame header found: {path}")

    # ========== 入口 2：缩略图 ==========

    async def make_thumbnail(self, path: str, max_size: Optional[int] = None) -> Dict[str, Any]:
        """生成图片缩略图并写入 user_data 缓存目录。

        缓存身份 = 规范化相对路径 + mtime_ns + size + max_size；
        命中后重开缓存图校验格式与边长，坏缓存丢弃重建。
        """
        try:
            if Image is None:
                raise MediaError("dependency_missing", "Pillow is not installed")
            if max_size is None:
                max_size = self.default_thumbnail_size
            try:
                max_size = int(max_size)
            except (TypeError, ValueError):
                raise MediaError("invalid_param", f"max_size must be an integer, got {max_size!r}")
            if not (1 <= max_size <= self.max_thumbnail_size):
                raise MediaError(
                    "invalid_param",
                    f"max_size must be within 1..{self.max_thumbnail_size}, got {max_size}",
                )

            real, rel_key = await self._resolve(path)
            st = self._stat_checked(real, path)
            ext = real.suffix.lower()
            if ext not in self.image_extensions:
                raise MediaError(
                    "unsupported_type",
                    f"thumbnail only supports image files, got '{ext or '(none)'}': {path}",
                )

            cache_file = self._cache_path(rel_key, st.st_mtime_ns, st.st_size, max_size)
            cached = self._read_valid_cache(cache_file, max_size)
            if cached is not None:
                width, height = cached
                return {
                    "success": True,
                    "path": path,
                    "cached": True,
                    "thumbnail": {
                        "file": cache_file.name,
                        "width": width,
                        "height": height,
                        "format": "PNG",
                        "max_size": max_size,
                    },
                }

            width, height = self._build_thumbnail(real, cache_file, max_size, path)
            return {
                "success": True,
                "path": path,
                "cached": False,
                "thumbnail": {
                    "file": cache_file.name,
                    "width": width,
                    "height": height,
                    "format": "PNG",
                    "max_size": max_size,
                },
            }
        except MediaError as e:
            return {"success": False, "error": e.code, "message": e.message}

    def _cache_path(self, rel_key: str, mtime_ns: int, size: int, max_size: int) -> Path:
        identity = f"{rel_key}|{mtime_ns}|{size}|{max_size}"
        digest = hashlib.sha256(identity.encode("utf-8")).hexdigest()
        return self.cache_dir / f"{digest}.png"

    def _read_valid_cache(self, cache_file: Path, max_size: int) -> Optional[Tuple[int, int]]:
        """命中后重开缓存图校验格式与边长；坏缓存删除并返回 None。"""
        if not cache_file.exists():
            return None
        try:
            with Image.open(cache_file) as img:
                if img.format != "PNG":
                    raise ValueError("unexpected cache format")
                img.load()  # 触发完整解码，拦截写了一半的缓存
                width, height = img.size
            if width <= 0 or height <= 0 or max(width, height) > max_size:
                raise ValueError("stale cache dimensions")
            return width, height
        except Exception:
            logger.warning(f"Discarding invalid thumbnail cache: {cache_file.name}")
            try:
                cache_file.unlink()
            except OSError:
                pass
            return None

    def _build_thumbnail(self, real: Path, cache_file: Path, max_size: int, path: str) -> Tuple[int, int]:
        try:
            with Image.open(real) as src:
                width, height = src.size
                if width <= 0 or height <= 0 or width * height > self.max_image_pixels:
                    raise MediaError(
                        "too_large",
                        f"decompressed dimensions {width}x{height} exceed limit: {path}",
                    )
                has_alpha = "A" in src.getbands() or "transparency" in src.info
                img = src.convert("RGBA" if has_alpha else "RGB")
            img.thumbnail((max_size, max_size))

            self.cache_dir.mkdir(parents=True, exist_ok=True)
            fd, tmp_name = tempfile.mkstemp(prefix=".thumb_", suffix=".tmp", dir=str(self.cache_dir))
            try:
                with os.fdopen(fd, "wb") as tmp:
                    img.save(tmp, format="PNG")
                os.replace(tmp_name, cache_file)  # 原子替换，并发读不到半张图
            except Exception:
                try:
                    os.unlink(tmp_name)
                except OSError:
                    pass
                raise
            return img.size
        except MediaError:
            raise
        except Exception:
            raise MediaError("corrupt", f"cannot decode image: {path}")

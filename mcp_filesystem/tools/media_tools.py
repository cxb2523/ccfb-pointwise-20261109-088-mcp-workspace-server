"""媒体工具 - media_probe / media_thumbnail

图片尺寸、音频时长探测与图片缩略图生成。
"""

from typing import Any, Dict, Optional

from ..media import MediaOperations


async def media_probe(path: str, media_ops: MediaOperations) -> Dict[str, Any]:
    """探测 workspace 内图片/音频的元数据（不整读文件）。"""
    return await media_ops.probe_file(path)


async def media_thumbnail(
    path: str,
    max_size: Optional[int],
    media_ops: MediaOperations,
) -> Dict[str, Any]:
    """生成图片缩略图，写入 user_data 下的缓存目录。"""
    return await media_ops.make_thumbnail(path, max_size=max_size)

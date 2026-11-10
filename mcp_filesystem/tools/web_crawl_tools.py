"""网页抓取工具（基于 crawl4ai），返回 Markdown，支持分页截断。"""

import json
from pathlib import Path
from typing import Any, Dict, Optional
from urllib.parse import urlparse

from fastmcp.utilities.logging import get_logger

try:
    from crawl4ai import AsyncWebCrawler
except Exception:  # pragma: no cover - 依赖缺失时给出友好错误
    AsyncWebCrawler = None  # type: ignore

logger = get_logger(__name__)

CONFIG_PATH = Path(__file__).resolve().parents[2] / "config.json"
_config_cache: Optional[Dict[str, Any]] = None


def _load_config() -> Dict[str, Any]:
    global _config_cache
    if _config_cache is not None:
        return _config_cache
    try:
        with open(CONFIG_PATH, "r", encoding="utf-8") as f:
            _config_cache = json.load(f)
    except Exception as e:
        logger.warning(f"Failed to load config from {CONFIG_PATH}: {e}")
        _config_cache = {}
    return _config_cache


def _get_max_markdown_chars(default: int = 20000) -> int:
    cfg = _load_config().get("web_crawl", {})
    raw = cfg.get("max_markdown_chars", default)
    try:
        val = int(raw)
        if val <= 0:
            raise ValueError("max_markdown_chars must be positive")
        return val
    except Exception:
        logger.warning(f"Invalid web_crawl.max_markdown_chars '{raw}', fallback to {default}")
        return default


def _get_timeout_seconds(default: int = 30) -> int:
    cfg = _load_config().get("web_crawl", {})
    raw = cfg.get("timeout_seconds", default)
    try:
        val = int(raw)
        if val <= 0:
            raise ValueError("timeout_seconds must be positive")
        return val
    except Exception:
        logger.warning(f"Invalid web_crawl.timeout_seconds '{raw}', fallback to {default}")
        return default


def _validate_url(url: str) -> Optional[str]:
    parsed = urlparse(url)
    if parsed.scheme not in ("http", "https"):
        return "仅支持 http/https URL"
    if not parsed.netloc:
        return "URL 缺少域名"
    return None


DEFAULT_TIMEOUT = 30


async def crawl_url_to_md(
    url: str,
    *,
    timeout: int = DEFAULT_TIMEOUT,
    offset: int = 0,
) -> Dict[str, Any]:
    """抓取指定 URL，输出 Markdown 与元信息，支持分页截断。"""
    if AsyncWebCrawler is None:
        return {"success": False, "error": "crawl4ai 未安装，请确认依赖已安装", "url": url}

    err = _validate_url(url)
    if err:
        return {"success": False, "error": err, "url": url}

    timeout = _get_timeout_seconds(timeout)

    try:
        async with AsyncWebCrawler() as crawler:
            try:
                result = await crawler.arun(url=url, timeout=timeout)
            except TypeError:
                # 兼容旧版签名
                result = await crawler.arun(url)
    except Exception as e:
        logger.error(f"crawl4ai arun failed for {url}: {e}", exc_info=True)
        return {"success": False, "error": str(e), "url": url}

    markdown = (
        getattr(result, "markdown", None)
        or getattr(result, "markdown_v2", None)
        or getattr(result, "content", None)
    )
    markdown = markdown or ""

    max_chars = _get_max_markdown_chars()
    try:
        start = int(offset)
    except Exception:
        start = 0
    start = max(0, start)

    total_chars = len(markdown)
    if start > total_chars:
        start = total_chars
    end = min(start + max_chars, total_chars)
    sliced_md = markdown[start:end]

    pagination = None
    needs_pagination = (start > 0) or (end < total_chars)
    if needs_pagination:
        page_index = max_chars and (start // max_chars + 1) or 1
        pagination = {
            "page_start": start,
            "page_end": end - 1 if end > 0 else 0,
            "page_size": max_chars,
            "returned_chars": len(sliced_md),
            "total_chars": total_chars,
            "has_more": end < total_chars,
        }
        if end < total_chars:
            pagination["next_start"] = end
            pagination["message"] = (
                f"内容较长，已返回第 {page_index} 段。继续读取可使用 offset={end} 再次调用 crawl_url。"
            )
        else:
            pagination["message"] = "已返回最后一段内容。"

    returned_len = len(sliced_md)
    logger.info(
        f"crawl_url_to_md: url={url} original_len={total_chars} returned_len={returned_len} paginated={bool(pagination)}"
    )

    meta = {
        "status": getattr(result, "status", None),
        "links": getattr(result, "links", None),
        "truncated": pagination is not None and pagination.get("has_more", False),
    }

    resp: Dict[str, Any] = {
        "success": True,
        "url": url,
        "markdown": sliced_md,
        "meta": meta,
    }
    if pagination:
        resp["pagination"] = pagination
    return resp


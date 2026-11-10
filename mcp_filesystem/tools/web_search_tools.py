"""博查联网搜索封装，返回整理后的上下文文本。"""

import json
from typing import Any, Dict, List, Optional
from pathlib import Path

import httpx
from fastmcp.utilities.logging import get_logger

logger = get_logger(__name__)

CONFIG_PATH = Path(__file__).resolve().parents[2] / "config.json"
_config_cache: Optional[Dict[str, Any]] = None


def _load_config() -> Dict[str, Any]:
    """读取 config.json，带简单缓存。"""
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


def _get_web_search_config() -> Dict[str, Any]:
    """获取 web_search 配置并提供默认值。"""
    cfg = _load_config().get("web_search", {})
    return {
        "base_url": cfg.get("base_url", "https://api.bochaai.com/v1/web-search"),
        "token": cfg.get("token"),
        "default_count": int(cfg.get("default_count", 10) or 10),
        "freshness": cfg.get("freshness", "noLimit"),
        "summary": bool(cfg.get("summary", True)),
    }


def _format_contexts(items: List[Dict[str, Any]], limit: int) -> str:
    """格式化搜索结果为可读文本。"""
    if not items:
        return "暂无搜索结果"
    max_context = min(len(items), limit)
    formatted = []
    for i in range(max_context):
        ctx = items[i] or {}
        formatted.append(
            f"[[引用:{i + 1}]]\n"
            f"网页标题:{ctx.get('name') or ''}\n"
            f"网页链接:{ctx.get('url') or ''}\n"
            f"网页内容:{ctx.get('summary') or ''}\n"
            f"发布时间:{ctx.get('dateLastCrawled') or ''}\n"
            f"网站名称:{ctx.get('name') or ''}"
        )
    return "\n\n".join(formatted)


async def web_search(
    query: str,
    *,
    count: Optional[int] = None,
    freshness: Optional[str] = None,
    summary: Optional[bool] = None,
) -> Dict[str, Any]:
    """调用博查联网搜索，返回整理后的上下文。"""
    cfg = _get_web_search_config()
    base_url = cfg.get("base_url")
    token = cfg.get("token")
    if not token:
        return {"success": False, "error": "缺少 web_search token，请在 config.json 配置。"}

    try:
        count_int = int(count) if count is not None else int(cfg.get("default_count", 10))
    except Exception:
        count_int = int(cfg.get("default_count", 10))
    count_int = max(1, min(count_int, 50))  # 简单限流保护

    freshness_val = freshness or cfg.get("freshness", "noLimit")
    summary_val = cfg.get("summary", True) if summary is None else bool(summary)

    payload = {
        "query": query,
        "summary": summary_val,
        "freshness": freshness_val,
        "count": count_int,
    }
    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json",
    }

    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            resp = await client.post(base_url, json=payload, headers=headers)
        status_code = resp.status_code
        try:
            data = resp.json()
        except Exception:
            data = {"raw": resp.text}

        if status_code >= 400:
            return {
                "success": False,
                "status_code": status_code,
                "error": data.get("message") if isinstance(data, dict) else resp.text,
            }

        web_pages = {}
        if isinstance(data, dict):
            web_pages = data.get("data", {}).get("webPages", {})
        items = web_pages.get("value") if isinstance(web_pages, dict) else None
        items = items or []

        context_text = _format_contexts(items, count_int)
        return {
            "success": True,
            "query": query,
            "count": count_int,
            "freshness": freshness_val,
            "summary": summary_val,
            "context": context_text,
            "raw_count": len(items),
        }
    except httpx.HTTPError as e:
        logger.error(f"web_search http error: {e}")
        return {"success": False, "error": f"HTTP error: {e}"}
    except Exception as e:
        logger.error(f"web_search error: {e}", exc_info=True)
        return {"success": False, "error": str(e)}


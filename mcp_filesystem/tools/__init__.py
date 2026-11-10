"""Unified MCP Tools

工具清单：
- fs_read: 读取任意格式文件（自动识别 txt/xlsx/json/csv）
- fs_write: 创建/覆盖文件（自动识别格式，包括 text/md/xlsx/python/html）
- fs_ops: 文件系统操作（列目录、创建目录、移动文件、获取信息）
- fs_search: 搜索文件名或内容
- excel_edit: 编辑 Excel 文件（单元格/格式/公式/工作表/行列/图表）
- exec: 执行 Python 命令
- preview_frontend: 前端项目部署（保持不变）
- list_excel_templates: 列出 Excel 模板（保持不变）
- create_excel_from_template: 从模板创建 Excel（保持不变）
- kb_search: 企业知识库 glob 搜索（外部接口）
- kb_read: 企业知识库文件读取（返回 Markdown 文本）

注意：
- Excel 文件的读取使用 fs_read
- Excel 文件的写入使用 fs_write
- Excel 元数据获取使用 fs_ops("info")
"""

from pathlib import Path
import json

from .fs_tools import (
    fs_read,
    fs_write,
    fs_ops,
    fs_search,
)
from .excel_tools import (
    excel_edit,
)
from .exec_tools import exec_command


def _load_cfg() -> dict:
    """加载配置以决定是否启用 web_search。"""
    try:
        cfg_path = Path(__file__).resolve().parents[1] / "config.json"
        with open(cfg_path, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {}


_cfg = _load_cfg()
_kb_enabled = bool(_cfg.get("kb", {}).get("enabled", True))
_web_crawl_enabled = bool(_cfg.get("web_crawl", {}).get("enabled", True))
_web_search_enabled = bool(_cfg.get("web_search", {}).get("enabled", False))

if _kb_enabled:
    from .kb_tools import kb_search, kb_read_url as kb_read

if _web_crawl_enabled:
    from .web_crawl_tools import crawl_url_to_md

if _web_search_enabled:
    from .web_search_tools import web_search

__all__ = [
    # 文件系统工具 (4个)
    "fs_read",
    "fs_write", 
    "fs_ops",
    "fs_search",
    # Excel 工具 (1个)
    "excel_edit",
    # 执行工具 (1个)
    "exec_command",
]

if _kb_enabled:
    __all__.extend(["kb_search", "kb_read"])

if _web_crawl_enabled:
    __all__.append("crawl_url_to_md")

if _web_search_enabled:
    __all__.append("web_search")


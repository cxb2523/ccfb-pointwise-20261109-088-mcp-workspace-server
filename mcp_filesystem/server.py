"""MCP Filesystem Server.

工具清单：
1. fs_read - 读取文件（txt/json/csv/xlsx，支持批量）
2. fs_write - 创建/覆盖文件（自动识别格式）
3. fs_replace - 基于SEARCH/REPLACE精确编辑文件
4. fs_ops - 文件操作（list/mkdir/move/info/delete）
5. fs_search - 搜索（按文件名或内容）
6. excel_edit - Excel编辑（单元格/公式/格式/工作表/图表）
7. exec - 执行Python代码或文件
8. preview_frontend - 部署静态前端
9. list_excel_templates - 列出Excel模板
10. create_excel_from_template - 从模板创建Excel
11. generate_image - 生成图像（数据图表、Mermaid流程图或HTML渲染）
"""

import json
import os
import sys
from pathlib import Path
from typing import Annotated, Any, Dict, List, Literal, Optional, Union

from fastmcp import Context, FastMCP
from fastmcp.utilities.logging import get_logger
from pydantic import Field
from contextlib import asynccontextmanager
from starlette.types import ASGIApp, Receive, Scope, Send

from .advanced import AdvancedFileOperations
from .command import CommandExecutor, PreviewManager
from .context import (
    chat_id_var,
    user_id_var,
    session_id_var,
    get_session_info,
    set_session_info,
    get_workspace_name,
)
from .excel import ExcelOperations
from .grep import GrepTools
from .operations import FileOperations
from .security import (
    PathValidator,
    sanitize_error_simple,
    sanitize_tool_response,
    PathLeakageError,
    configure_response_sanitizer,
)
from .command.preview import PreviewRoutingMiddleware

# Import unified tools
from .tools.fs_tools import (
    fs_read as _fs_read,
    fs_write as _fs_write,
    fs_ops as _fs_ops,
    fs_search as _fs_search,
)
from .tools.excel_tools import (
    excel_edit as _excel_edit,
)
from .tools.exec_tools import exec_command as _exec_command
from .tools.replace_tools import fs_replace as _fs_replace
from .tools.image_tools import generate_image as _generate_image

logger = get_logger(__name__)

# Force INFO level logging for debugging
import logging

# 统一的日志格式，包含日期时间戳
LOG_FORMAT = "%(asctime)s %(levelname)s:%(name)s:%(message)s"
LOG_DATE_FORMAT = "%Y-%m-%d %H:%M:%S"

# 创建统一的格式化器
formatter = logging.Formatter(LOG_FORMAT, LOG_DATE_FORMAT)

logging.basicConfig(
    level=logging.INFO,
    format=LOG_FORMAT,
    datefmt=LOG_DATE_FORMAT,
    force=True,
)
logger.setLevel(logging.INFO)

# 配置所有现有和未来的 logger 使用统一格式
def configure_logger_format(logger_name: str):
    """配置指定 logger 的格式，包含日期时间戳"""
    log = logging.getLogger(logger_name)
    log.setLevel(logging.INFO)
    # 为所有现有的 handler 设置格式
    for handler in log.handlers:
        handler.setFormatter(formatter)
    # 如果没有 handler，添加一个使用统一格式的 handler
    if not log.handlers:
        handler = logging.StreamHandler()
        handler.setFormatter(formatter)
        log.addHandler(handler)
        # 避免日志向上传播到 root logger（避免重复输出）
        log.propagate = False

# 配置常见的第三方库 logger（在 uvicorn 启动前配置）
for logger_name in ["uvicorn", "uvicorn.access", "uvicorn.error", "httpx", "mcp"]:
    configure_logger_format(logger_name)

# 确保 root logger 也使用统一格式
root_logger = logging.getLogger()
for handler in root_logger.handlers:
    handler.setFormatter(formatter)

# 创建一个函数，用于在 uvicorn 启动后重新配置日志格式
# 这个方法会在需要时被调用，确保所有日志都有日期时间戳
def ensure_unified_logging():
    """确保所有 logger 都使用统一的日期时间戳格式"""
    # 重新配置所有已知的 logger
    for logger_name in ["uvicorn", "uvicorn.access", "uvicorn.error", "httpx", "mcp"]:
        configure_logger_format(logger_name)
    
    # 配置 root logger
    root_logger = logging.getLogger()
    for handler in root_logger.handlers:
        handler.setFormatter(formatter)
    
    # 遍历所有已存在的 logger 并配置格式
    # 这确保所有日志都有日期时间戳，包括 uvicorn 启动后创建的 logger
    for name in logging.Logger.manager.loggerDict:
        log = logging.getLogger(name)
        for handler in log.handlers:
            handler.setFormatter(formatter)


# ========== Config Loading ==========
_config_cache: Optional[Dict[str, Any]] = None


def load_config() -> Dict[str, Any]:
    """Load configuration from config.json file."""
    global _config_cache
    if _config_cache is not None:
        return _config_cache
    
    config_path = Path(__file__).parent.parent / "config.json"
    if config_path.exists():
        try:
            with open(config_path, "r", encoding="utf-8") as f:
                _config_cache = json.load(f)
                logger.info(f"Loaded config from {config_path}")
        except Exception as e:
            logger.warning(f"Failed to load config: {e}")
            _config_cache = {}
    else:
        logger.warning(f"Config file not found: {config_path}")
        _config_cache = {}
    
    return _config_cache


# web_search/kb/web_crawl 可配置开关，可能不启用
def _is_kb_enabled() -> bool:
    cfg = load_config().get("kb", {})
    return bool(cfg.get("enabled", True))


def _is_web_search_enabled() -> bool:
    cfg = load_config().get("web_search", {})
    return bool(cfg.get("enabled", False))


def _is_web_crawl_enabled() -> bool:
    cfg = load_config().get("web_crawl", {})
    return bool(cfg.get("enabled", True))


def _get_web_crawl_timeout(default: int = 30) -> int:
    cfg = load_config().get("web_crawl", {})
    raw = cfg.get("timeout_seconds", default)
    try:
        val = int(raw)
        if val <= 0:
            raise ValueError("timeout_seconds must be positive")
        return val
    except Exception:
        logger.warning(f"Invalid web_crawl.timeout_seconds '{raw}', fallback to {default}")
        return default


if _is_kb_enabled():
    from .tools.kb_tools import kb_search as _kb_search, kb_read_url as _kb_read

if _is_web_crawl_enabled():
    from .tools.web_crawl_tools import crawl_url_to_md as _crawl_url_to_md

if _is_web_search_enabled():
    from .tools.web_search_tools import web_search as _web_search


def _init_response_sanitizer() -> None:
    """Initialize the response sanitizer with config-based patterns.
    
    This should be called once at startup to configure sensitive path patterns.
    """
    config = load_config()
    security_config = config.get("security", {})
    
    # Get additional sensitive patterns from config
    additional_patterns = security_config.get("sensitive_path_patterns", [])
    
    # Always include workspace directory pattern from environment
    workspaces_dir = os.environ.get("MCP_WORKSPACES_DIR", "")
    if workspaces_dir:
        # Extract the directory name to use as a pattern
        # e.g., /user_data_jaxckqcdxlyyodcpwd -> user_data_jaxckqcdxlyyodcpwd
        dir_name = Path(workspaces_dir).name
        if dir_name and dir_name not in additional_patterns:
            additional_patterns.append(dir_name)
    
    configure_response_sanitizer(additional_patterns=additional_patterns)
    logger.info(f"Response sanitizer initialized with {len(additional_patterns)} additional patterns")


def safe_json_response(result: Any, user_path: Optional[str] = None) -> Any:
    """Safely return a result with security checks.

    This function should be used by all tools to return their results.
    It performs path leakage detection before returning.

    Args:
        result: The result to return (dict/list)
        user_path: The user-provided path (for error messages)

    Returns:
        The result object (FastMCP will serialize it)
        Or error dict if security violation detected
    """
    try:
        # Check for path leakage
        sanitize_tool_response(result, raise_on_violation=True)
        return result  # 直接返回字典，让 FastMCP 序列化
    except PathLeakageError as e:
        # Log the security violation
        logger.error(f"SECURITY: Path leakage blocked: {e.violations}")
        # Return a generic error to the client
        return {
            "success": False,
            "error": "Internal error: response validation failed",
            "message": "The operation may have completed, but the response could not be validated.",
        }
    except Exception as e:
        return f"Error: {sanitize_error_simple(e, user_path)}"


# Initialize response sanitizer at module load
_init_response_sanitizer()


def get_allowed_dirs() -> List[Union[str, Path]]:
    """Get the list of allowed directories from environment or arguments."""
    allowed_dirs = os.environ.get("MCP_ALLOWED_DIRS", "").split(os.pathsep)
    if len(sys.argv) > 1:
        allowed_dirs.extend(sys.argv[1:])
    if not allowed_dirs or all(not d for d in allowed_dirs):
        allowed_dirs = [os.getcwd()]
    return [d for d in allowed_dirs if d]


# Components cache
_components_cache: Dict[Optional[str], Dict[str, Any]] = {}


async def get_session_components(ctx: Context) -> Dict[str, Any]:
    """Initialize and return shared components for the current session."""
    workspace_path: Optional[Path] = None
    user_id = user_id_var.get()
    chat_id = chat_id_var.get()
    config = load_config()
    
    if not user_id and not chat_id:
        try:
            if hasattr(ctx, "request_context") and ctx.request_context:
                session_id = session_id_var.get()
                if session_id:
                    user_id, chat_id = get_session_info(session_id)
        except Exception:
            pass
    
    workspace_name = get_workspace_name(user_id, chat_id)
            
    if workspace_name in _components_cache:
        return _components_cache[workspace_name]

    virtual_root = None
    if workspace_name:
        default_user_data_dir = Path(__file__).parent.parent / "user_data"
        base_dir = os.environ.get("MCP_WORKSPACES_DIR", str(default_user_data_dir))
        workspace_path = Path(base_dir) / workspace_name
        
        try:
            workspace_path.mkdir(parents=True, exist_ok=True)
            logger.info(f"Created/Using workspace '{workspace_name}': {workspace_path}")
        except Exception as e:
            logger.error(f"Failed to create workspace '{workspace_name}': {e}")
            raise
            
        allowed_dirs_typed = [workspace_path]
        virtual_root = workspace_path
    else:
        if None in _components_cache:
            return _components_cache[None]
        allowed_dirs_typed = get_allowed_dirs()

    validator = PathValidator(allowed_dirs_typed, virtual_root=virtual_root)
    operations = FileOperations(validator)
    advanced = AdvancedFileOperations(validator, operations)
    grep = GrepTools(validator)
    excel = ExcelOperations(validator, config.get("excel", {}))
    
    command_executor = None
    preview_manager = None
    if workspace_path:
        command_config = config.get("command", {})
        command_executor = CommandExecutor(
            workspace_path=workspace_path,
            config=command_config,
        )
        preview_manager = PreviewManager(
            workspace_path=workspace_path,
            workspace_name=workspace_name,
            config=config,
        )

    components = {
        "validator": validator,
        "operations": operations,
        "advanced": advanced,
        "grep": grep,
        "excel": excel,
        "command": command_executor,
        "preview": preview_manager,
        "allowed_dirs": validator.get_allowed_dirs(),
        "workspace_path": workspace_path if virtual_root else None,
    }

    _components_cache[workspace_name] = components
    logger.info(f"Initialized filesystem components for workspace '{workspace_name}'")
    return components


# Global flag for restore (module level to persist across requests)
_restore_done = {"done": False}


class UserContextMiddleware:
    """ASGI middleware to capture X-User-ID and X-Chat-ID headers."""

    def __init__(self, app: ASGIApp):
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send):
        # 在第一次 HTTP 请求时，确保所有日志都使用统一的日期时间戳格式
        # 此时 uvicorn 应该已经启动，可以重新配置日志格式
        if not _restore_done["done"] and scope["type"] == "http":
            _restore_done["done"] = True
            # 确保所有 logger 都使用统一的日期时间戳格式
            ensure_unified_logging()
            # Run restoration in background (don't block the request)
            import asyncio
            try:
                asyncio.create_task(_restore_previews_on_startup())
                logger.info("Preview restoration task created successfully")
            except Exception as e:
                logger.error(f"Failed to create preview restoration task: {e}", exc_info=True)

        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        headers = dict(scope.get("headers", []))
        user_id = headers.get(b"x-user-id", b"").decode() or None
        chat_id = headers.get(b"x-chat-id", b"").decode() or None

        query_string = scope.get("query_string", b"").decode()
        session_id = None
        for param in query_string.split("&"):
            if param.startswith("session_id="):
                session_id = param.split("=", 1)[1]
                break

        user_token = user_id_var.set(user_id)
        chat_token = chat_id_var.set(chat_id)

        if session_id and (user_id or chat_id):
            set_session_info(session_id, user_id, chat_id)

        try:
            await self.app(scope, receive, send)
        finally:
            user_id_var.reset(user_token)
            chat_id_var.reset(chat_token)


async def _restore_previews_on_startup():
    """Restore all preview services from JSON file."""
    logger.info("=" * 60)
    logger.info("Starting preview services restoration on server startup...")
    try:
        config = load_config()
        default_user_data_dir = Path(__file__).parent.parent / "user_data"
        workspaces_dir = Path(os.environ.get("MCP_WORKSPACES_DIR", str(default_user_data_dir)))
        
        logger.info(f"Workspaces directory: {workspaces_dir}")
        
        if workspaces_dir.exists():
            logger.info(f"Workspaces directory exists, proceeding with restoration...")
            restored_count = await PreviewManager.restore_all_previews_on_startup(
                workspaces_dir=workspaces_dir,
                config=config,
            )
            logger.info(f"Preview restoration completed: {restored_count} services restored")
        else:
            logger.warning(f"Workspaces directory does not exist: {workspaces_dir}, skipping preview restore")
    except Exception as e:
        logger.error(f"Error restoring preview services on startup: {e}", exc_info=True)
    finally:
        logger.info("=" * 60)


class FilesystemFastMCP(FastMCP):
    """FastMCP with unified tools and HTTP routes."""

    def http_app(self, **kwargs):
        app = super().http_app(**kwargs)
        # Serve preview content in single-port mode by host routing
        app.add_middleware(PreviewRoutingMiddleware, config=load_config())
        app.add_middleware(UserContextMiddleware)

        # Add HTTP routes for admin/user APIs
        from .http_routes import add_http_routes
        add_http_routes(app)

        return app


# Create MCP server
mcp = FilesystemFastMCP(
    name="Filesystem MCP Server",
    instructions="文件系统 MCP 服务器 - 整合版",
)


# ========== 文件系统工具 (4个) ==========

@mcp.tool()
async def fs_read(
    path: Annotated[Union[str, List[str]], Field(description="文件路径或路径列表")],
    ctx: Context,
    sheet: Annotated[str, Field(description="Excel工作表名（默认第一个）")] = "",
    range: Annotated[str, Field(description="Excel读取范围如A1:C10")] = "",
    line_range: Annotated[str, Field(description="文档按行读取范围，如'10:','20:50'")] = "",
) -> Any:
    """读取文件，自动识别格式（md/txt/json/csv/xlsx/py）。支持批量读取。
    
    Examples:
        fs_read("README.md")
        fs_read("data.xlsx", sheet="Sheet1", range="A1:D100")
        fs_read(["a.py", "config.json"])
        fs_read("README.md", line_range="1:50")
    """
    try:
        components = await get_session_components(ctx)
        result = await _fs_read(
            path=path,
            validator=components["validator"],
            operations=components["operations"],
            excel_ops=components["excel"],
            sheet=sheet if sheet else None,
            range=range if range else None,
            encoding="utf-8",
            line_range=line_range or None,
        )
        return safe_json_response(result, str(path))
    except Exception as e:
        logger.error(f"fs_read error for path '{path}': {type(e).__name__}: {e}", exc_info=True)
        return f"Error: {sanitize_error_simple(e, str(path))}"


@mcp.tool()
async def fs_write(
    path: Annotated[str, Field(description="文件路径")],
    content: Annotated[Any, Field(description="内容：字符串/dict/2D数组")],
    ctx: Context,
    overwrite: Annotated[bool, Field(description="覆盖已存在文件")] = True,
    append: Annotated[bool, Field(description="追加模式")] = False,
    sheet: Annotated[str, Field(description="Excel工作表名")] = "",
) -> Any:
    """创建或覆盖文件。根据扩展名自动处理格式（md/txt/json/csv/xlsx/py等）。
    
    Examples:
        fs_write("README.md", "# Title\n内容")
        fs_write("config.json", {"key": "value"})
        fs_write("data.xlsx", [["Name","Age"],["Alice",30]])
        fs_write("script.py", "print('hi')")
        fs_write("log.txt", "新日志", append=True)
    """
    try:
        components = await get_session_components(ctx)
        result = await _fs_write(
            path=path,
            content=content,
            validator=components["validator"],
            operations=components["operations"],
            excel_ops=components["excel"],
            overwrite=overwrite,
            append=append,
            sheet=sheet if sheet else None,
            encoding="utf-8",
        )
        return safe_json_response(result, path)
    except Exception as e:
        return f"Error: {sanitize_error_simple(e, path)}"


@mcp.tool()
async def fs_ops(
    operation: Annotated[
        Literal["list", "mkdir", "move", "info", "delete"],
        Field(description="list|mkdir|move|info|delete")
    ],
    path: Annotated[str, Field(description="目标路径")],
    ctx: Context,
    destination: Annotated[str, Field(description="move的目标路径")] = "",
) -> Any:
    """文件系统操作：列目录、创建目录、移动/重命名、获取信息、删除。
    
    Examples:
        fs_ops("list", "/")
        fs_ops("mkdir", "/new_folder")
        fs_ops("move", "/old.txt", destination="/renamed.txt")
        fs_ops("info", "/file.xlsx")  # 包含Excel元数据
        fs_ops("delete", "/temp")
    """
    try:
        components = await get_session_components(ctx)
        result = await _fs_ops(
            operation=operation,
            path=path,
            validator=components["validator"],
            operations=components["operations"],
            excel_ops=components["excel"],
            destination=destination if destination else None,
            recursive=True,
        )
        return safe_json_response(result, path)
    except Exception as e:
        return f"Error: {sanitize_error_simple(e, path)}"


@mcp.tool()
async def fs_search(
    search_type: Annotated[
        Literal["glob", "content"],
        Field(description="glob=按文件名（不区分大小写）, content=按内容正则")
    ],
    pattern: Annotated[str, Field(description="glob 模式或内容正则")],
    ctx: Context,
    context_lines: Annotated[int, Field(description="content搜索返回匹配行前后的上下文行数")] = 2,
) -> Any:
    """搜索workspace内的文件。
    
    - glob：文件名 glob，默认起点=工作区根，不区分大小写
    - content：内容搜索，默认使用正则，最大返回 20 条
    - context_lines：仅对 content 搜索有效，指定返回匹配行前后的上下文行数
    """
    try:
        components = await get_session_components(ctx)
        internal_type = "filename" if search_type == "glob" else "content"
        max_results = 20
        result = await _fs_search(
            search_type=internal_type,
            pattern=pattern,
            validator=components["validator"],
            grep_tools=components["grep"],
            operations=components["operations"],
            path=None,  # 始终以工作区根作为起点
            max_results=max_results,
            case_sensitive=False,  # 工具侧不区分大小写
            is_regex=True if internal_type == "content" else False,  # 内容默认支持正则
            context_lines=context_lines,  # 传递上下文行数参数
        )
        return safe_json_response(result)
    except Exception as e:
        logger.error(f"fs_search error for pattern '{pattern}': {type(e).__name__}: {e}", exc_info=True)
        return f"Error: {sanitize_error_simple(e, pattern)}"


@mcp.tool()
async def fs_replace(
    path: Annotated[str, Field(description="文件路径")],
    diff: Annotated[str, Field(description="SEARCH/REPLACE diff文本")],
    ctx: Context
) -> Any:
    """精确编辑文件内容，使用 SEARCH/REPLACE diff 语法。

    Examples:
        fs_replace("config.py", diff=\"\"\"
        ------- SEARCH
        DEBUG = True
        =======
        DEBUG = False
        +++++++ REPLACE
        \"\"\")
    """
    try:
        components = await get_session_components(ctx)
        result = await _fs_replace(
            path=path,
            diff=diff,
            validator=components["validator"],
            operations=components["operations"],
            allow_relaxed=False,
        )
        return safe_json_response(result, path)
    except Exception as e:
        logger.error(f"fs_replace error for path '{path}': {type(e).__name__}: {e}", exc_info=True)
        return f"Error: {sanitize_error_simple(e, path)}"


# ========== 知识库工具 ==========

if _is_kb_enabled():
    @mcp.tool()
    async def kb_search(
        pattern: Annotated[str, Field(description="Glob pattern, e.g. '**/*.pdf' or '**/*报销*'")],
        ctx: Context,
        limit: Annotated[int, Field(description="Max results (1-50)")] = 10,
    ) -> Any:
        """企业知识库 glob 搜索，返回匹配文件列表。"""
        try:
            result = await _kb_search(pattern=pattern, limit=limit)
            return safe_json_response(result)
        except Exception as e:
            logger.error(f"kb_search error for pattern '{pattern}': {type(e).__name__}: {e}", exc_info=True)
            return f"Error: {sanitize_error_simple(e, pattern)}"


    @mcp.tool()
    async def kb_read(
        url: Annotated[str, Field(description="File URL returned by kb_search (e.g. '/api/s/xxx')")],
        ctx: Context,
        offset: Annotated[int, Field(description="可选，字符偏移量，用于分页读取")] = 0,
        collection_ids: Annotated[List[str], Field(description="可选，collectionId 列表，用于片段检索")] = [],
        text: Annotated[str, Field(description="可选，当使用 collection_ids 时的查询文本")] = "",
    ) -> Any:
        """读取知识库文件或按 collectionIds 检索片段，并返回 Markdown 文本。"""
        try:
            result = await _kb_read(url=url, offset=offset, collection_ids=collection_ids, text=text)
            return safe_json_response(result, url)
        except Exception as e:
            logger.error(f"kb_read error for url '{url}': {type(e).__name__}: {e}", exc_info=True)
            return f"Error: {sanitize_error_simple(e, url)}"
else:
    logger.info("kb tools disabled via config (kb.enabled=false)")


# ========== 网页抓取工具 (1个) ==========

if _is_web_crawl_enabled():
    @mcp.tool()
    async def crawl_url(
        url: Annotated[str, Field(description="目标网站 URL")],
        ctx: Context,
        offset: Annotated[int, Field(description="可选，字符偏移量，用于分页截断")] = 0,
    ) -> Any:
        """抓取网页并返回 Markdown。"""
        try:
            result = await _crawl_url_to_md(
                url=url,
                offset=offset,
                timeout=_get_web_crawl_timeout(),
            )
            return safe_json_response(result, url)
        except Exception as e:
            logger.error(f"crawl_url error for url '{url}': {type(e).__name__}: {e}", exc_info=True)
            return f"Error: {sanitize_error_simple(e, url)}"
else:
    logger.info("web_crawl disabled via config (web_crawl.enabled=false)")


# ========== 联网搜索工具 (1个) ==========


if _is_web_search_enabled():
    @mcp.tool()
    async def web_search(
        query: Annotated[str, Field(description="搜索关键词或语义查询")],
        ctx: Context,
        count: Annotated[int, Field(description="可选，返回条数")] = 10,
    ) -> Any:
        """调用联网搜索，返回搜索结果。"""
        try:
            count_val = None if count in (-1, 0) else count
            result = await _web_search(
                query=query,
                count=count_val,
            )
            return safe_json_response(result, query)
        except Exception as e:
            logger.error(f"web_search error for query '{query}': {type(e).__name__}: {e}", exc_info=True)
            return f"Error: {sanitize_error_simple(e, query)}"
else:
    logger.info("web_search disabled via config (web_search.enabled=false)")


# ========== Excel 工具 (1个) ==========

@mcp.tool()
async def excel_edit(
    path: Annotated[str, Field(description="Excel文件路径")],
    edit_type: Annotated[
        Literal["cells", "format"],
        Field(description="cells|format")
    ],
    ctx: Context,
    sheet: Annotated[str, Field(description="工作表名")] = "",
    # cells: 批量更新单元格
    updates: Annotated[
        List[Dict[str, Any]],
        Field(description="cells: [{cell,value},...]")
    ] = [],
    # format: 格式化范围
    range: Annotated[str, Field(description="format/range: A1:C10")] = "",
    style: Annotated[
        Dict[str, Any],
        Field(description="format: {bold,bg_color}")
    ] = {},
) -> Any:
    """编辑Excel文件。
    - cells: 批量更新单元格值
    - format: 加粗/改背景色
    
    Examples:
        excel_edit("data.xlsx", "cells", updates=[{"cell":"A1","value":"Hello"}])
        excel_edit("data.xlsx", "format", range="A1:C1", style={"bold":True,"bg_color":"FFFF00"})  # 仅用于非模板文件
    """
    try:
        components = await get_session_components(ctx)
        result = await _excel_edit(
            path=path,
            edit_type=edit_type,
            excel_ops=components["excel"],
            validator=components["validator"],
            sheet=sheet if sheet else None,
            updates=updates if updates else None,
            range=range if range else None,
            style=style if style else None,
            # 低频/不再暴露的能力统一置空
            cell=None,
            formula=None,
            operation=None,
            source_range=None,
            target_range=None,
            sheet_operation=None,
            target_sheet=None,
            new_name=None,
            row_col_operation=None,
            start_index=None,
            count=None,
            chart_type=None,
            data_range=None,
            target_cell=None,
            chart_title=None,
        )
        return safe_json_response(result, path)
    except Exception as e:
        return f"Error: {sanitize_error_simple(e, path)}"



# ========== 执行工具 (1个) ==========

@mcp.tool()
async def exec(
    ctx: Context,
    code: Annotated[str, Field(description="代码字符串")] = "",
    file: Annotated[str, Field(description="文件路径（与code二选一）")] = "",
    args: Annotated[List[str], Field(description="命令行参数")] = [],
) -> Any:
    """执行Python代码或文件。code和file二选一。返回stdout/stderr/exit_code。
    
    代码在工作区目录执行，可用相对路径访问工作区文件。
    
    Examples:
        exec(code="print(2+2)")
        exec(file="/script.py", args=["--verbose"])
    """
    try:
        components = await get_session_components(ctx)
        result = await _exec_command(
            runtime="python",
            command_executor=components["command"],
            validator=components["validator"],
            operations=components["operations"],
            code=code if code else None,
            file=file if file else None,
            args=args if args else None,
        )
        return safe_json_response(result)
    except Exception as e:
        return f"Error: {sanitize_error_simple(e)}"


# ========== 部署工具 (1个) ==========

@mcp.tool()
async def preview_frontend(
    entry_file: Annotated[str, Field(description="入口HTML文件")] = "index.html",
    ctx: Context = None,
) -> Any:
    """部署静态前端到预览服务器，返回可访问的URL。
    
    Examples:
        preview_frontend()  # 默认 index.html
        preview_frontend("dist/index.html")
    """
    try:
        components = await get_session_components(ctx)
        preview = components["preview"]
        
        if preview is None:
            return safe_json_response({
                "success": False,
                "error": "Preview not available in global mode. Use session mode with user_id/chat_id."
            })
        
        # 支持传入路径形式的入口文件（例如 "dist/index.html"）
        clean_path = entry_file.lstrip("/").replace("\\", "/") if isinstance(entry_file, str) else "index.html"
        if "/" in clean_path:
            directory_rel, entry = clean_path.rsplit("/", 1)
            directory = f"/{directory_rel}" if directory_rel else "/"
        else:
            directory = "/"
            entry = clean_path

        result = await preview.start_preview(directory=directory, entry=entry)
        return safe_json_response(result, entry_file)
    except Exception as e:
        return f"Error deploying preview: {sanitize_error_simple(e)}"


# ========== 模板工具 (2个) ==========

@mcp.tool()
async def list_excel_templates(ctx: Context) -> Any:
    """列出可用的Excel模板。返回模板标题和描述，用于create_excel_from_template。"""
    try:
        components = await get_session_components(ctx)
        excel = components["excel"]
        result = await excel.list_templates()
        return safe_json_response(result)
    except Exception as e:
        return f"Error listing Excel templates: {sanitize_error_simple(e)}"


@mcp.tool()
async def create_excel_from_template(
    template_title: Annotated[str, Field(description="模板标题（来自list_excel_templates）")],
    ctx: Context,
    file_name: Annotated[str, Field(description="新文件名（可选）")] = "",
    directory: Annotated[str, Field(description="目标目录（可选）")] = "",
) -> Any:
    """从模板创建Excel文件，使用excel_edit填充数据即可"""
    try:
        components = await get_session_components(ctx)
        excel = components["excel"]
        result = await excel.create_from_template(
            template_title=template_title,
            directory=directory if directory else None,
            file_name=file_name if file_name else None,
        )
        return safe_json_response(result, template_title)
    except Exception as e:
        logger.error(f"Error creating Excel from template: {e}", exc_info=True)
        return f"Error creating Excel from template: {sanitize_error_simple(e)}"


# ========== 图像生成工具 (1个) ==========

@mcp.tool()
async def generate_image(
    mermaid_code: Annotated[
        str,
        Field(description="时序图、流程图等逻辑关系图使用，渲染为PNG图片。（与html_code二选一）")
    ] = "",
    html_code: Annotated[
        str,
        Field(description="HTML代码，图表、graph、架构图等使用，渲染为PNG图片。")
    ] = "",
    ctx: Context = None,
) -> Any:
    """生成图表/架构图等返回图像url。
    
    Examples:
        generate_image(mermaid_code="flowchart TD\\nA[开始] --> B[结束]")
        generate_image(html_code="<html><body><h1>System Architecture</h1></body></html>")
    """
    # 支持的图表类型：line/bar/column/pie/area/scatter/histogram/boxplot/radar/network-graph/treemap/sankey/funnel/organization-chart/word-cloud/liquid/auto
    try:
        components = await get_session_components(ctx)
        result = await _generate_image(
            chart_data=None,
            mermaid_code=mermaid_code,
            html_code=html_code,
            workspace_path=components.get("workspace_path"),
        )
        return safe_json_response(result)
    except Exception as e:
        logger.error(f"generate_image error: {type(e).__name__}: {e}", exc_info=True)
        return f"Error: {sanitize_error_simple(e)}"

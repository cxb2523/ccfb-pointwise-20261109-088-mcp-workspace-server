"""文件替换工具 - fs_replace

实现基于 SEARCH/REPLACE diff 语法的精确文件编辑能力。
"""

import re
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

try:
    from mcp.server.fastmcp.utilities.logging import get_logger
    logger = get_logger(__name__)
except ImportError:
    import logging
    logger = logging.getLogger(__name__)

try:
    from ..operations import FileOperations
    from ..security import PathValidator, sanitize_error_simple
except ImportError:
    # 允许独立测试核心逻辑
    FileOperations = None
    PathValidator = None
    sanitize_error_simple = lambda e, p=None: str(e)


class ReplaceBlock:
    """单个 SEARCH/REPLACE 块"""
    def __init__(self, search: str, replace: str):
        self.search = search
        self.replace = replace


class DiffParseError(Exception):
    """Diff 解析错误"""
    pass


class SearchNotFoundError(Exception):
    """SEARCH 内容未找到"""
    pass


def strip_code_fence(raw: str) -> str:
    """去掉 diff 外层的 ``` 包裹（如果存在）"""
    lines = raw.strip().split("\n")
    if len(lines) < 2:
        return raw

    # 检查首行是否是 ```（可能带语言标记）
    if lines[0].strip().startswith("```"):
        # 检查末行是否是 ```
        if lines[-1].strip() == "```":
            return "\n".join(lines[1:-1])

    return raw


def is_search_start(line: str) -> bool:
    """判断是否是 SEARCH 起始标记"""
    # 支持: ------- SEARCH, <<<<<<< SEARCH
    pattern = r"^(-{3,}|<{3,})\s*SEARCH>?\s*$"
    return bool(re.match(pattern, line.strip()))


def is_search_end(line: str) -> bool:
    """判断是否是 SEARCH 结束标记（= 分隔符）"""
    return bool(re.match(r"^={3,}\s*$", line.strip()))


def is_replace_end(line: str) -> bool:
    """判断是否是 REPLACE 结束标记"""
    # 支持: +++++++ REPLACE, >>>>>>> REPLACE
    pattern = r"^(\+{3,}|>{3,})\s*REPLACE>?\s*$"
    return bool(re.match(pattern, line.strip()))


def parse_diff(raw_diff: str) -> List[ReplaceBlock]:
    """解析 diff 文本为 ReplaceBlock 列表

    Args:
        raw_diff: diff 文本，可能被 ``` 包裹

    Returns:
        ReplaceBlock 列表

    Raises:
        DiffParseError: 格式错误
    """
    cleaned = strip_code_fence(raw_diff)
    lines = cleaned.split("\n")

    blocks: List[ReplaceBlock] = []
    state: str = "idle"  # idle | search | replace
    search_buf: List[str] = []
    replace_buf: List[str] = []

    for i, line in enumerate(lines):
        if is_search_start(line):
            if state != "idle":
                raise DiffParseError(
                    f"Line {i+1}: Unexpected SEARCH marker while in '{state}' state. "
                    "Each SEARCH block must be closed with ======= before starting a new one."
                )
            state = "search"
            search_buf = []
            continue

        if is_search_end(line):
            if state != "search":
                raise DiffParseError(
                    f"Line {i+1}: Unexpected ======= marker while in '{state}' state. "
                    "The ======= marker should only appear after a SEARCH block."
                )
            state = "replace"
            replace_buf = []
            continue

        if is_replace_end(line):
            if state != "replace":
                raise DiffParseError(
                    f"Line {i+1}: Unexpected REPLACE marker while in '{state}' state. "
                    "Each REPLACE block must follow a SEARCH block and =======."
                )
            blocks.append(ReplaceBlock(
                search="\n".join(search_buf),
                replace="\n".join(replace_buf)
            ))
            state = "idle"
            continue

        # 收集内容行
        if state == "search":
            search_buf.append(line)
        elif state == "replace":
            replace_buf.append(line)
        # idle 状态下的非标记行被忽略（允许注释等）

    if state != "idle":
        raise DiffParseError(
            f"Incomplete diff block: ended in '{state}' state. "
            "Make sure all SEARCH blocks have ======= and all REPLACE blocks end with +++++++."
        )

    if len(blocks) == 0:
        raise DiffParseError(
            "No valid SEARCH/REPLACE blocks found. "
            "Make sure your diff follows the format:\n"
            "------- SEARCH\n"
            "<original lines>\n"
            "=======\n"
            "<replacement lines>\n"
            "+++++++ REPLACE"
        )

    return blocks


def find_match_exact(content: str, search: str) -> int:
    """精确匹配 search 在 content 中的位置

    Returns:
        匹配的起始字符索引，未找到返回 -1
    """
    return content.find(search)


def find_match_relaxed(content: str, search: str) -> Tuple[int, int]:
    """宽松匹配：忽略行首尾空白

    Returns:
        (起始字符索引, 结束字符索引)，未找到返回 (-1, -1)
    """
    content_lines = content.split("\n")
    search_lines = search.split("\n")

    # trim 后的 search 行
    trimmed_search = [line.strip() for line in search_lines]

    # 滑动窗口匹配
    for i in range(len(content_lines) - len(search_lines) + 1):
        window = content_lines[i:i + len(search_lines)]
        trimmed_window = [line.strip() for line in window]

        if trimmed_window == trimmed_search:
            # 计算原始内容中的字符位置
            start_pos = sum(len(line) + 1 for line in content_lines[:i])  # +1 for \n
            end_pos = start_pos + sum(len(line) + 1 for line in window)
            return start_pos, end_pos - 1  # 不包含最后一个 \n

    return -1, -1


def apply_blocks(
    original: str,
    blocks: List[ReplaceBlock],
    allow_relaxed: bool = False
) -> str:
    """应用所有 SEARCH/REPLACE 块

    Args:
        original: 原始文件内容
        blocks: ReplaceBlock 列表
        allow_relaxed: 是否允许宽松匹配（忽略首尾空白）

    Returns:
        修改后的文件内容

    Raises:
        SearchNotFoundError: 某个 SEARCH 块未找到匹配
    """
    content = original

    for idx, block in enumerate(blocks):
        # 先尝试精确匹配
        pos = find_match_exact(content, block.search)

        if pos < 0 and allow_relaxed:
            # 宽松匹配
            start_pos, end_pos = find_match_relaxed(content, block.search)
            if start_pos >= 0:
                # 替换匹配的内容
                content = content[:start_pos] + block.replace + content[end_pos+1:]
                continue

        if pos < 0:
            # 未找到匹配，尝试诊断
            diagnostic_msg = f"Block {idx+1}: SEARCH content not found in file.\n\n"
            
            # 尝试宽松匹配以提供更好的诊断
            relaxed_start, relaxed_end = find_match_relaxed(content, block.search)
            if relaxed_start >= 0:
                # 找到了宽松匹配，说明是缩进/空白问题
                matched_lines = content[relaxed_start:relaxed_end+1].split("\n")
                diagnostic_msg += (
                    "⚠️  Found similar content with different indentation/whitespace.\n"
                    "💡 Solution: Enable relaxed mode (allow_relaxed=True) or fix indentation.\n\n"
                    f"SEARCH content (expected):\n{block.search[:300]}\n\n"
                    f"Actual content in file:\n{chr(10).join(matched_lines[:5])[:300]}...\n"
                )
            else:
                # 完全找不到，尝试查找相似内容
                search_first_line = block.search.split("\n")[0].strip()
                if search_first_line:
                    # 查找包含第一行关键词的位置
                    similar_positions = []
                    for i, line in enumerate(content.split("\n")):
                        if search_first_line.lower() in line.lower():
                            similar_positions.append((i, line[:100]))
                            if len(similar_positions) >= 3:
                                break
                    
                    if similar_positions:
                        diagnostic_msg += (
                            f"💡 Found similar lines in file (line numbers may help):\n"
                        )
                        for line_num, line_content in similar_positions:
                            diagnostic_msg += f"  Line ~{line_num+1}: {line_content}\n"
                        diagnostic_msg += "\n"
            
            diagnostic_msg += (
                "Please ensure:\n"
                "1. Using the latest file content (read the file first)\n"
                "2. SEARCH blocks match exactly, including indentation\n"
                "3. Blocks are applied in order (from top to bottom)\n"
                f"4. Enable relaxed mode if whitespace differences exist\n\n"
                f"SEARCH content:\n{block.search[:300]}..."
            )
            
            raise SearchNotFoundError(diagnostic_msg)

        # 精确匹配成功，替换
        content = content[:pos] + block.replace + content[pos + len(block.search):]

    return content


async def fs_replace(
    path: str,
    diff: str,
    validator: PathValidator,
    operations: FileOperations,
    allow_relaxed: bool = False,
) -> Dict[str, Any]:
    """文件内容精确替换工具

    使用 SEARCH/REPLACE diff 语法进行精确的文件编辑。

    Args:
        path: 文件路径
        diff: SEARCH/REPLACE diff 文本
        validator: 路径校验器
        operations: 文件操作器
        allow_relaxed: 是否允许宽松匹配（忽略行首尾空白）

    Returns:
        {
            "success": True,
            "path": "...",
            "blocks_applied": 3,
            "final_length": 1234,
            "message": "..."
        }

    Error types:
        - format_error: diff 格式错误
        - search_not_found: SEARCH 内容未找到
        - file_not_found: 文件不存在
        - ignore_denied: 路径被忽略规则屏蔽
        - other: 其他错误
    """
    try:
        # 1. 路径校验
        real_path, allowed = await validator.validate_path(path)

        if not allowed:
            return {
                "success": False,
                "error": "ignore_denied",
                "message": f"Access denied: path is not within allowed directories",
            }

        # 2. 检查文件是否存在
        if not real_path.exists():
            return {
                "success": False,
                "error": "file_not_found",
                "message": f"File not found: {path}",
            }

        if not real_path.is_file():
            return {
                "success": False,
                "error": "other",
                "message": f"Not a file: {path}",
            }

        # 3. 校验必填参数
        if not diff or not diff.strip():
            return {
                "success": False,
                "error": "format_error",
                "message": "diff parameter is required and cannot be empty",
            }

        # 4. 读取原始文件内容
        # 注意：传入虚拟路径字符串，而不是真实路径
        # operations.read_file 内部会再次调用 validate_path
        original_content = await operations.read_file(path)
        if isinstance(original_content, bytes):
            try:
                original_content = original_content.decode("utf-8")
            except UnicodeDecodeError:
                return {
                    "success": False,
                    "error": "other",
                    "message": "File is not UTF-8 encoded text",
                }

        # 5. 解析 diff
        try:
            blocks = parse_diff(diff)
        except DiffParseError as e:
            return {
                "success": False,
                "error": "format_error",
                "message": str(e),
            }

        # 6. 应用 SEARCH/REPLACE 块
        try:
            final_content = apply_blocks(original_content, blocks, allow_relaxed)
        except SearchNotFoundError as e:
            return {
                "success": False,
                "error": "search_not_found",
                "message": str(e),
                "hint": "Try reading the file again to get the latest content, or reduce the number of blocks per request",
            }

        # 7. 写回文件
        # 注意：传入虚拟路径字符串，而不是真实路径
        # operations.write_file 内部会再次调用 validate_path
        try:
            await operations.write_file(path, final_content)
        except Exception as e:
            logger.error(f"Failed to write file {real_path}: {e}", exc_info=True)
            return {
                "success": False,
                "error": "other",
                "message": f"Failed to write file: {sanitize_error_simple(e, path)}",
            }

        # 8. 返回成功结果
        return {
            "success": True,
            "path": validator.real_to_virtual(real_path, strict=False),
            "blocks_applied": len(blocks),
            "final_length": len(final_content),
            "message": f"Successfully applied {len(blocks)} replacement(s)",
        }

    except Exception as e:
        logger.error(f"fs_replace error for path '{path}': {type(e).__name__}: {e}", exc_info=True)
        return {
            "success": False,
            "error": "other",
            "message": sanitize_error_simple(e, path),
        }

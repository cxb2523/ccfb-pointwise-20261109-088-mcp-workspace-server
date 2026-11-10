"""命令执行工具 - exec.

学习 Claude Code 的 Bash 工具设计：
- 支持权限过滤
- 强制超时限制（默认 2 分钟）
- 资源限制（内存、CPU）

整合前：run_command
整合后：exec（支持 code/file/args）
"""

import shlex
import uuid
from pathlib import Path
from typing import Any, Dict, List, Literal, Optional

from mcp.server.fastmcp.utilities.logging import get_logger

from ..command import CommandExecutor
from ..operations import FileOperations
from ..security import PathValidator

logger = get_logger(__name__)


async def exec_command(
    runtime: Literal["python"],
    command_executor: Optional[CommandExecutor],
    validator: PathValidator,
    operations: FileOperations,
    *,
    code: Optional[str] = None,
    file: Optional[str] = None,
    args: Optional[List[str]] = None,
) -> Dict[str, Any]:
    """执行 Python 代码或文件.

    Args:
        runtime: 运行时类型，目前仅支持 'python'
        command_executor: 命令执行器实例
        validator: 路径验证器
        operations: 文件操作实例
        code: Python 代码字符串（与 file 二选一）
        file: Python 文件路径（虚拟路径，与 code 二选一）
        args: 命令行参数列表

    Returns:
        {
            "success": bool,
            "exit_code": int,
            "stdout": str,
            "stderr": str,
            "execution_time": float,
            "timed_out": bool
        }

    Examples:
        # 执行代码
        exec_command("python", executor, validator, ops, code="print(1+1)")

        # 执行文件
        exec_command("python", executor, validator, ops, file="/script.py")

        # 带参数执行
        exec_command("python", executor, validator, ops,
                    file="/process.py", args=["input.csv", "output.csv"])

    Raises:
        ValueError: 如果参数不合法
        RuntimeError: 如果命令执行器不可用
    """
    logger.info("=" * 80)
    logger.info(f"exec_command ENTRY: runtime={runtime}, code={bool(code)}, file={file!r}, args={args}")
    logger.info(f"exec_command: validator.virtual_root={validator.virtual_root}")
    logger.info(f"exec_command: validator.allowed_dirs={validator.allowed_dirs}")

    if runtime != "python":
        raise ValueError(f"Unsupported runtime: {runtime}. Only 'python' is supported.")

    if command_executor is None:
        raise RuntimeError(
            "Command executor not available. "
            "Make sure you're using session mode with a workspace."
        )

    # 参数验证：code 和 file 必须提供且只能提供一个
    if not code and not file:
        raise ValueError("Must provide either 'code' or 'file' parameter")

    if code and file:
        raise ValueError("Cannot provide both 'code' and 'file' parameters")

    # 如果提供了 file，读取文件内容
    code_content = code
    if file:
        logger.info(f"exec_command: Processing file parameter: {file!r}")
        logger.info(f"exec_command: Calling validator.validate_path({file!r})...")

        abs_path, allowed = await validator.validate_path(file)

        logger.info(f"exec_command: validate_path returned:")
        logger.info(f"  - abs_path: {abs_path}")
        logger.info(f"  - abs_path type: {type(abs_path)}")
        logger.info(f"  - allowed: {allowed}")
        logger.info(f"  - abs_path.exists(): {abs_path.exists()}")

        if abs_path.exists():
            logger.info(f"  - abs_path.is_file(): {abs_path.is_file()}")
            logger.info(f"  - abs_path.stat(): {abs_path.stat()}")

        if not allowed:
            error_msg = f"File path not allowed: {file}"
            logger.error(f"exec_command: {error_msg}")
            raise ValueError(error_msg)

        if not abs_path.exists():
            error_msg = f"File not found: {file} (resolved to: {abs_path})"
            logger.error(f"exec_command: {error_msg}")
            raise ValueError(error_msg)

        # 关键修复：传入虚拟路径字符串，而不是真实路径 Path 对象
        # operations.read_file 内部会再次调用 validate_path
        logger.info(f"exec_command: Calling operations.read_file({file!r})...")
        code_content = await operations.read_file(file)  # 传入虚拟路径！
        logger.info(f"exec_command: Successfully read file, size={len(code_content)} bytes")
        logger.info(f"exec_command: First 100 chars: {code_content[:100]!r}")
    else:
        logger.info(f"exec_command: Using code parameter, size={len(code)} bytes")

    # 执行前进行 lint 校验（Python 语法检查）
    logger.info("exec_command: Performing lint check before execution...")
    try:
        from ..lint.python_linter import PythonLinter
        linter = PythonLinter()
        
        # 创建临时 Path 对象用于 lint（不实际写入文件）
        temp_path = Path(f"<exec_code>.py")
        lint_result = await linter.lint(temp_path, content=code_content)
        
        if not lint_result.passed:
            logger.warning(f"exec_command: Code has lint errors, aborting execution")
            return {
                "success": False,
                "exit_code": -1,
                "stdout": "",
                "stderr": "Code has syntax errors, execution aborted",
                "execution_time": 0.0,
                "timed_out": False,
                "lint": lint_result.to_dict(),
            }
        else:
            logger.info("exec_command: Lint check passed")
    except Exception as e:
        logger.warning(f"exec_command: Lint check failed: {e}, continuing execution")

    # 准备参数列表
    args_list = args or []
    logger.info(f"exec_command: args_list={args_list}")

    # 构建执行命令
    # 使用临时文件方式，这样可以正确传递 args 且不需要复杂的 shell 转义
    temp_file_name = f".exec_{uuid.uuid4().hex[:8]}.py"
    logger.info(f"exec_command: temp_file_name={temp_file_name}")

    try:
        # 写入临时文件（使用文件名作为虚拟路径，自动落在 workspace 根目录）
        logger.info(f"exec_command: Calling operations.write_file({temp_file_name!r}, code_content)...")
        await operations.write_file(temp_file_name, code_content)
        logger.info(f"exec_command: Successfully created temporary file: {temp_file_name}")

        # 验证临时文件是否真的创建了
        temp_abs_path, temp_allowed = await validator.validate_path(temp_file_name)
        logger.info(f"exec_command: Verified temp file: abs_path={temp_abs_path}, exists={temp_abs_path.exists()}")

        # 构建命令：python <temp_file> arg1 arg2 ...
        cmd_parts = ["python", temp_file_name]
        cmd_parts.extend(args_list)

        # 使用 shlex.join 安全地构建命令（Python 3.8+）
        python_cmd = shlex.join(cmd_parts)

        # 从配置中获取超时时间
        timeout = command_executor.default_timeout

        logger.info(f"exec_command: Executing command: {python_cmd}")
        logger.info(f"exec_command: Working dir: /")
        logger.info(f"exec_command: Timeout: {timeout}s (from config)")

        # 执行命令（使用配置中的超时时间）
        result = await command_executor.execute(
            command=python_cmd,
            timeout=timeout,
            working_dir="/",  # 在 workspace 根目录执行
        )

        logger.info(f"exec_command: Execution completed:")
        logger.info(f"  - success: {result.success}")
        logger.info(f"  - exit_code: {result.exit_code}")
        logger.info(f"  - stdout length: {len(result.stdout)}")
        logger.info(f"  - stderr length: {len(result.stderr)}")

        return {
            "success": result.success,
            "runtime": runtime,
            "exit_code": result.exit_code,
            "stdout": result.stdout,
            "stderr": result.stderr,
            "execution_time": result.execution_time,
            "timed_out": result.timed_out,
            "error": result.error,
        }

    except Exception as e:
        logger.error(f"exec_command: Exception during execution: {type(e).__name__}: {e}")
        logger.exception("Full traceback:")
        return {
            "success": False,
            "runtime": runtime,
            "exit_code": -1,
            "stdout": "",
            "stderr": str(e),
            "execution_time": 0,
            "timed_out": False,
            "error": str(e),
        }

    finally:
        # 清理临时文件（使用虚拟路径）
        logger.info(f"exec_command: Cleaning up temporary file: {temp_file_name}")
        try:
            # 获取临时文件的真实路径来检查是否存在
            temp_abs_path, _ = await validator.validate_path(temp_file_name)
            logger.info(f"exec_command: Temp file abs_path={temp_abs_path}, exists={temp_abs_path.exists()}")
            if temp_abs_path.exists():
                temp_abs_path.unlink()
                logger.info(f"exec_command: Cleaned up temporary file: {temp_file_name}")
            else:
                logger.warning(f"exec_command: Temp file doesn't exist, skipping cleanup")
        except Exception as e:
            logger.warning(f"exec_command: Failed to clean up temporary file: {e}")


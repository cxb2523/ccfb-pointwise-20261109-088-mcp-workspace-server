"""文件 Lint 校验模块.

提供文件质量检查功能，支持多种文件类型的语法和格式验证。
"""

from .base import FileLinter, LintResult
from .registry import LinterRegistry, get_linter, lint_file

__all__ = [
    'FileLinter',
    'LintResult',
    'LinterRegistry',
    'get_linter',
    'lint_file',
]


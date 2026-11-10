"""Python 文件 Linter."""

import ast
from pathlib import Path
from typing import List, Optional

from .base import FileLinter, LintError, LintResult


class PythonLinter(FileLinter):
    """Python 文件校验器.
    
    使用 ast.parse() 进行语法检查（零依赖）。
    可选支持 pyflakes 进行代码质量检查。
    """
    
    @classmethod
    def supported_extensions(cls) -> List[str]:
        return ['.py', '.pyw']
    
    async def lint(self, file_path: Path, content: Optional[str] = None) -> LintResult:
        """执行 Python 代码校验."""
        errors: List[LintError] = []
        warnings: List[LintError] = []
        
        # 读取内容
        if content is None:
            try:
                content = file_path.read_text(encoding='utf-8')
            except Exception as e:
                return LintResult(
                    checked=False,
                    passed=False,
                    error=f"Failed to read file: {e}"
                )
        
        # 1. AST 语法检查（零依赖，必须执行）
        try:
            compile(content, str(file_path), 'exec', ast.PyCF_ONLY_AST)
        except SyntaxError as e:
            errors.append(LintError(
                severity="error",
                message=f"Syntax error: {e.msg}",
                rule="python/syntax",
                line=e.lineno,
                column=e.offset,
                suggestion="Fix the syntax error before running the code"
            ))
        except Exception as e:
            errors.append(LintError(
                severity="error",
                message=f"Compilation error: {str(e)}",
                rule="python/compile"
            ))
        
        # 2. Pyflakes 检查（可选，如果安装了的话）
        if self.config.get("use_pyflakes", True) and not errors:
            try:
                import pyflakes.api
                import pyflakes.reporter
                from io import StringIO
                
                # 捕获 pyflakes 输出
                warning_stream = StringIO()
                error_stream = StringIO()
                reporter = pyflakes.reporter.Reporter(warning_stream, error_stream)
                
                pyflakes.api.check(content, str(file_path), reporter=reporter)
                
                # 解析警告
                warning_output = warning_stream.getvalue()
                if warning_output:
                    for line in warning_output.strip().split('\n'):
                        if line:
                            warnings.append(LintError(
                                severity="warning",
                                message=line,
                                rule="python/pyflakes"
                            ))
            except ImportError:
                # pyflakes 未安装，跳过
                pass
            except Exception as e:
                # pyflakes 检查失败不影响整体结果
                pass
        
        # 构建结果
        passed = len(errors) == 0
        
        if passed and not warnings:
            message = "✓ Python syntax validation passed"
        else:
            message = None
        
        return LintResult(
            checked=True,
            passed=passed,
            errors=errors,
            warnings=warnings,
            message=message
        )


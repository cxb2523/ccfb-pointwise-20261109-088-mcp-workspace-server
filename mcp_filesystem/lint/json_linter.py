"""JSON 文件 Linter."""

import json
from pathlib import Path
from typing import List, Optional

from .base import FileLinter, LintError, LintResult


class JsonLinter(FileLinter):
    """JSON 文件校验器.
    
    使用 json.loads() 进行格式验证（零依赖）。
    """
    
    @classmethod
    def supported_extensions(cls) -> List[str]:
        return ['.json', '.jsonl']
    
    async def lint(self, file_path: Path, content: Optional[str] = None) -> LintResult:
        """执行 JSON 格式校验."""
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
        
        # JSON 格式验证
        try:
            json.loads(content)
            return LintResult(
                checked=True,
                passed=True,
                message="✓ Valid JSON format"
            )
        except json.JSONDecodeError as e:
            return LintResult(
                checked=True,
                passed=False,
                errors=[LintError(
                    severity="error",
                    message=f"JSON decode error: {e.msg}",
                    rule="json/syntax",
                    line=e.lineno,
                    column=e.colno,
                    suggestion="Fix the JSON syntax error"
                )]
            )
        except Exception as e:
            return LintResult(
                checked=False,
                passed=False,
                error=f"JSON validation failed: {str(e)}"
            )


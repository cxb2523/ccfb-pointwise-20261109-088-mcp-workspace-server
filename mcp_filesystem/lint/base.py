"""Lint 基础类定义."""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional


@dataclass
class LintError:
    """Lint 错误信息."""
    
    severity: str  # "error" | "warning"
    message: str
    rule: str
    line: Optional[int] = None
    column: Optional[int] = None
    suggestion: Optional[str] = None
    
    def to_dict(self) -> Dict[str, Any]:
        """转换为字典格式."""
        result = {
            "severity": self.severity,
            "message": self.message,
            "rule": self.rule,
        }
        if self.line is not None:
            result["line"] = self.line
        if self.column is not None:
            result["column"] = self.column
        if self.suggestion:
            result["suggestion"] = self.suggestion
        return result


@dataclass
class LintResult:
    """Lint 校验结果."""
    
    checked: bool = True  # 是否执行了校验
    passed: bool = True  # 是否通过校验
    errors: List[LintError] = field(default_factory=list)
    warnings: List[LintError] = field(default_factory=list)
    message: Optional[str] = None
    error: Optional[str] = None  # 校验过程本身的错误
    
    def to_dict(self) -> Dict[str, Any]:
        """转换为字典格式，用于返回给客户端."""
        result: Dict[str, Any] = {
            "checked": self.checked,
            "passed": self.passed,
        }
        
        if self.message:
            result["message"] = self.message
        
        if self.error:
            result["error"] = self.error
        
        if self.errors:
            result["errors"] = [e.to_dict() for e in self.errors]
        
        if self.warnings:
            result["warnings"] = [w.to_dict() for w in self.warnings]
        
        # 生成摘要信息
        if not self.passed and (self.errors or self.warnings):
            error_count = len(self.errors)
            warning_count = len(self.warnings)
            summary_parts = []
            if error_count > 0:
                summary_parts.append(f"{error_count} error(s)")
            if warning_count > 0:
                summary_parts.append(f"{warning_count} warning(s)")
            result["summary"] = f"⚠ Found {' and '.join(summary_parts)}"
        
        return result


class FileLinter(ABC):
    """文件 Linter 基类."""
    
    def __init__(self, config: Optional[Dict[str, Any]] = None):
        """初始化 Linter.
        
        Args:
            config: 配置字典
        """
        self.config = config or {}
    
    @abstractmethod
    async def lint(self, file_path: Path, content: Optional[str] = None) -> LintResult:
        """执行 lint 校验.
        
        Args:
            file_path: 文件路径
            content: 文件内容（可选，如果不提供则从文件读取）
            
        Returns:
            LintResult: 校验结果
        """
        pass
    
    @classmethod
    @abstractmethod
    def supported_extensions(cls) -> List[str]:
        """返回支持的文件扩展名列表.
        
        Returns:
            扩展名列表，如 ['.py', '.pyw']
        """
        pass
    
    def is_enabled(self) -> bool:
        """检查此 linter 是否启用."""
        return self.config.get("enabled", True)


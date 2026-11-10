"""Linter 注册表."""

import json
import logging
from pathlib import Path
from typing import Any, Dict, Optional, Type

from .base import FileLinter, LintResult
from .html_linter import HtmlLinter
from .json_linter import JsonLinter
from .python_linter import PythonLinter
from .svg_linter import SvgLinter

logger = logging.getLogger(__name__)


class LinterRegistry:
    """Linter 注册表，管理所有可用的 linter."""
    
    _instance: Optional['LinterRegistry'] = None
    _linters: Dict[str, Type[FileLinter]] = {}
    _config: Dict[str, Any] = {}
    
    def __init__(self):
        """初始化注册表."""
        # 注册内置 linter
        self.register(PythonLinter)
        self.register(JsonLinter)
        self.register(HtmlLinter)
        self.register(SvgLinter)
        
        # 加载配置
        self._load_config()
    
    @classmethod
    def get_instance(cls) -> 'LinterRegistry':
        """获取单例实例."""
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance
    
    def register(self, linter_class: Type[FileLinter]) -> None:
        """注册一个 linter.
        
        Args:
            linter_class: Linter 类
        """
        for ext in linter_class.supported_extensions():
            self._linters[ext.lower()] = linter_class
            logger.info(f"Registered linter for {ext}: {linter_class.__name__}")
    
    def get_linter(self, file_path: Path) -> Optional[FileLinter]:
        """根据文件扩展名获取对应的 linter.
        
        Args:
            file_path: 文件路径
            
        Returns:
            Linter 实例，如果没有找到则返回 None
        """
        ext = file_path.suffix.lower()
        linter_class = self._linters.get(ext)
        
        if linter_class is None:
            return None
        
        # 获取该 linter 的配置
        linter_name = linter_class.__name__.replace('Linter', '').lower()
        linter_config = self._config.get('linters', {}).get(linter_name, {})
        
        return linter_class(config=linter_config)
    
    def _load_config(self) -> None:
        """从 config.json 加载 lint 配置."""
        # 查找 config.json（相对于当前模块）
        config_path = Path(__file__).resolve().parents[2] / "config.json"
        
        try:
            if config_path.exists():
                with open(config_path, 'r', encoding='utf-8') as f:
                    full_config = json.load(f)
                    self._config = full_config.get('lint', {})
                    logger.info(f"Loaded lint config from {config_path}")
            else:
                logger.info(f"No config file found at {config_path}, using defaults")
                self._config = {'enabled': True, 'linters': {}}
        except Exception as e:
            logger.warning(f"Failed to load lint config: {e}")
            self._config = {'enabled': True, 'linters': {}}
    
    def is_enabled(self) -> bool:
        """检查 lint 功能是否全局启用."""
        return self._config.get('enabled', True)


# 便捷函数

def get_linter(file_path: Path) -> Optional[FileLinter]:
    """获取文件对应的 linter.
    
    Args:
        file_path: 文件路径
        
    Returns:
        Linter 实例，如果没有找到或 lint 被禁用则返回 None
    """
    registry = LinterRegistry.get_instance()
    
    if not registry.is_enabled():
        return None
    
    return registry.get_linter(file_path)


async def lint_file(file_path: Path, content: Optional[str] = None) -> Optional[Dict[str, Any]]:
    """对文件执行 lint 校验.
    
    Args:
        file_path: 文件路径
        content: 文件内容（可选）
        
    Returns:
        Lint 结果字典，如果没有对应的 linter 则返回 None
    """
    try:
        linter = get_linter(file_path)
        
        if linter is None:
            return None
        
        if not linter.is_enabled():
            return None
        
        result = await linter.lint(file_path, content)
        return result.to_dict()
        
    except Exception as e:
        logger.error(f"Lint failed for {file_path}: {e}", exc_info=True)
        return {
            "checked": False,
            "passed": True,  # 不阻止文件操作
            "error": f"Lint check failed: {str(e)}"
        }


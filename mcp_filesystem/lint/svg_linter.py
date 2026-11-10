"""SVG 文件 Linter."""

import xml.etree.ElementTree as ET
from pathlib import Path
from typing import List, Optional

from .base import FileLinter, LintError, LintResult


class SvgLinter(FileLinter):
    """SVG 文件校验器.
    
    使用 xml.etree.ElementTree 进行 XML 格式验证（零依赖）。
    """
    
    @classmethod
    def supported_extensions(cls) -> List[str]:
        return ['.svg']
    
    async def lint(self, file_path: Path, content: Optional[str] = None) -> LintResult:
        """执行 SVG 校验."""
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
        
        # XML 格式验证
        try:
            root = ET.fromstring(content)
            
            # 检查是否是有效的 SVG
            svg_tags = ['{http://www.w3.org/2000/svg}svg', 'svg']
            if root.tag not in svg_tags:
                return LintResult(
                    checked=True,
                    passed=False,
                    errors=[LintError(
                        severity="error",
                        message=f"Root element must be <svg>, found <{root.tag}>",
                        rule="svg/root-element",
                        suggestion="Ensure the root element is <svg>"
                    )]
                )
            
            # 检查基本属性
            warnings: List[LintError] = []
            
            # 建议添加 viewBox
            if 'viewBox' not in root.attrib:
                warnings.append(LintError(
                    severity="warning",
                    message="Missing 'viewBox' attribute on <svg>",
                    rule="svg/viewbox",
                    suggestion="Add viewBox attribute for better scalability"
                ))
            
            # 建议添加 xmlns
            if 'xmlns' not in root.attrib and root.tag == 'svg':
                warnings.append(LintError(
                    severity="warning",
                    message="Missing 'xmlns' attribute on <svg>",
                    rule="svg/xmlns",
                    suggestion="Add xmlns=\"http://www.w3.org/2000/svg\""
                ))
            
            return LintResult(
                checked=True,
                passed=True,
                warnings=warnings,
                message="✓ Valid SVG file" if not warnings else None
            )
            
        except ET.ParseError as e:
            line = e.position[0] if e.position else None
            return LintResult(
                checked=True,
                passed=False,
                errors=[LintError(
                    severity="error",
                    message=f"XML parse error: {str(e)}",
                    rule="svg/xml-syntax",
                    line=line,
                    suggestion="Fix the XML syntax error"
                )]
            )
        except Exception as e:
            return LintResult(
                checked=False,
                passed=False,
                error=f"SVG validation failed: {str(e)}"
            )


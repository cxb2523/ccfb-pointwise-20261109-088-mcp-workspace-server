"""HTML 文件 Linter."""

import re
from html.parser import HTMLParser
from pathlib import Path
from typing import List, Optional

from .base import FileLinter, LintError, LintResult


class HTMLValidator(HTMLParser):
    """HTML 验证解析器."""
    
    def __init__(self):
        super().__init__()
        self.errors: List[LintError] = []
        self.warnings: List[LintError] = []
        self.tag_stack: List[tuple] = []  # (tag, line, col)
        self.current_line = 1
        
    def handle_starttag(self, tag, attrs):
        """处理开始标签."""
        line, col = self.getpos()
        
        # 检查自闭合标签
        void_elements = {
            'area', 'base', 'br', 'col', 'embed', 'hr', 'img', 'input',
            'link', 'meta', 'param', 'source', 'track', 'wbr'
        }
        
        if tag not in void_elements:
            self.tag_stack.append((tag, line, col))
        
        # 检查 img 标签的 alt 属性
        if tag == 'img':
            attrs_dict = dict(attrs)
            if 'alt' not in attrs_dict:
                self.warnings.append(LintError(
                    severity="warning",
                    message=f"Missing 'alt' attribute on <img> tag",
                    rule="html/img-alt",
                    line=line,
                    column=col,
                    suggestion="Add alt=\"description\" for accessibility"
                ))
    
    def handle_endtag(self, tag):
        """处理结束标签."""
        line, col = self.getpos()
        
        if self.tag_stack:
            last_tag, start_line, start_col = self.tag_stack[-1]
            if last_tag == tag:
                self.tag_stack.pop()
            else:
                self.errors.append(LintError(
                    severity="error",
                    message=f"Mismatched closing tag </{tag}>, expected </{last_tag}>",
                    rule="html/mismatched-tag",
                    line=line,
                    column=col,
                    suggestion=f"Close <{last_tag}> tag properly"
                ))
        else:
            self.warnings.append(LintError(
                severity="warning",
                message=f"Unexpected closing tag </{tag}> with no matching opening tag",
                rule="html/unexpected-closing-tag",
                line=line,
                column=col
            ))
    
    def error(self, message):
        """处理解析错误."""
        line, col = self.getpos()
        self.errors.append(LintError(
            severity="error",
            message=f"HTML parsing error: {message}",
            rule="html/parse-error",
            line=line,
            column=col
        ))
    
    def check_unclosed_tags(self):
        """检查未关闭的标签."""
        for tag, line, col in self.tag_stack:
            self.errors.append(LintError(
                severity="error",
                message=f"Unclosed <{tag}> tag",
                rule="html/unclosed-tag",
                line=line,
                column=col,
                suggestion=f"Add closing </{tag}> tag"
            ))


class HtmlLinter(FileLinter):
    """HTML 文件校验器.
    
    检查：
    1. HTML 结构（标签配对）
    2. XSS 风险
    3. 基本可访问性
    """
    
    @classmethod
    def supported_extensions(cls) -> List[str]:
        return ['.html', '.htm']
    
    async def lint(self, file_path: Path, content: Optional[str] = None) -> LintResult:
        """执行 HTML 校验."""
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
        
        # 1. HTML 结构检查
        parser = HTMLValidator()
        try:
            parser.feed(content)
            parser.check_unclosed_tags()
            errors.extend(parser.errors)
            warnings.extend(parser.warnings)
        except Exception as e:
            errors.append(LintError(
                severity="error",
                message=f"HTML parsing failed: {str(e)}",
                rule="html/parse-error"
            ))
        
        # 2. XSS 安全检查
        if self.config.get("check_xss", True):
            # 检查内联事件处理器
            inline_event_pattern = r'<[^>]*\s+on\w+\s*=\s*["\'][^"\']*["\']'
            for match in re.finditer(inline_event_pattern, content, re.IGNORECASE):
                line = content[:match.start()].count('\n') + 1
                warnings.append(LintError(
                    severity="warning",
                    message="Potential XSS risk: inline event handler detected (onclick, onerror, etc.)",
                    rule="html/xss-inline-event",
                    line=line,
                    suggestion="Use addEventListener() instead of inline event handlers"
                ))
            
            # 检查 javascript: 协议
            javascript_protocol_pattern = r'javascript:\s*'
            if re.search(javascript_protocol_pattern, content, re.IGNORECASE):
                warnings.append(LintError(
                    severity="warning",
                    message="Potential XSS risk: javascript: protocol detected in URL",
                    rule="html/xss-javascript-protocol",
                    suggestion="Avoid using javascript: URLs"
                ))
        
        # 构建结果
        passed = len(errors) == 0
        
        if passed and not warnings:
            message = "✓ HTML validation passed"
        else:
            message = None
        
        return LintResult(
            checked=True,
            passed=passed,
            errors=errors,
            warnings=warnings,
            message=message
        )


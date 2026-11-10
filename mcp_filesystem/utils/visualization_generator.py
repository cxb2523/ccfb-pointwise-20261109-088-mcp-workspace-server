"""
Visualization generator - 统一可视化生成器
从 mcp-chart-python 项目整合，适配 mcp-filesystem 工作区系统
"""

import asyncio
import uuid
import os
import json
import sys
from pathlib import Path
from typing import Any, Dict, Optional

from .auto_detector import AutoChartDetector
from .style_enhancer import StyleEnhancer
from .api_client import ChartAPIClient


# Mermaid 主题配置
MERMAID_BUILTIN_THEMES = {
    "default": "默认主题 - 标准样式",
    "dark": "深色主题 - 适合暗色背景",
    "forest": "森林主题 - 绿色系",
    "neutral": "中性主题 - 黑白灰"
}

MERMAID_CUSTOM_THEMES = {
    "tech-cyan": {  # 科技青蓝主题 - 基于平台配色 ⭐ 推荐
        "theme": "base",
        "themeVariables": {
            "primaryColor": "#06b6d4",
            "primaryTextColor": "#ffffff",
            "primaryBorderColor": "#0891b2",
            "secondaryColor": "#3b82f6",
            "secondaryBorderColor": "#2563eb",
            "secondaryTextColor": "#ffffff",
            "tertiaryColor": "#10b981",
            "tertiaryBorderColor": "#0d9488",
            "tertiaryTextColor": "#ffffff",
            "lineColor": "#0e7490",
            "edgeLabelBackground": "#f0fdfa",
            "background": "#ffffff",
            "mainBkg": "#ecfeff",
            "secondBkg": "#cffafe",
            "nodeBorder": "#0891b2",
            "clusterBkg": "#f0fdfa",
            "clusterBorder": "#0e7490",
            "fontFamily": "Arial, 'Microsoft YaHei', sans-serif",
            "fontSize": "16px",
            "noteBkgColor": "#FEF3C7",
            "noteTextColor": "#1f2937",
            "noteBorderColor": "#f59e0b",
            "actorBkg": "#06b6d4",
            "actorBorder": "#0891b2",
            "actorTextColor": "#ffffff",
            "signalColor": "#0e7490",
            "signalTextColor": "#1f2937",
            "gridColor": "#e5e7eb",
            "doneTaskBkgColor": "#10b981",
            "activeTaskBkgColor": "#3b82f6",
            "critBkgColor": "#ef4444",
        }
    },
    "tech-blue": {
        "theme": "base",
        "themeVariables": {
            "primaryColor": "#3b82f6",
            "primaryTextColor": "#ffffff",
            "primaryBorderColor": "#2563eb",
            "lineColor": "#1d4ed8",
            "secondaryColor": "#10b981",
            "tertiaryColor": "#06b6d4",
            "background": "#ffffff",
            "mainBkg": "#eff6ff",
            "fontFamily": "Arial, 'Microsoft YaHei', sans-serif"
        }
    },
    "warm-orange": {
        "theme": "base",
        "themeVariables": {
            "primaryColor": "#f97316",
            "primaryTextColor": "#ffffff",
            "primaryBorderColor": "#ea580c",
            "lineColor": "#c2410c",
            "secondaryColor": "#fb923c",
            "tertiaryColor": "#fbbf24",
            "background": "#ffffff",
            "mainBkg": "#fff7ed",
            "fontFamily": "Arial, 'Microsoft YaHei', sans-serif"
        }
    }
}



class VisualizationGenerator:
    """可视化图表生成器"""

    def __init__(
        self,
        workspace_path: Optional[Path] = None,
        api_endpoint: Optional[str] = None,
        chart_default_width: int = 800,
        chart_default_height: int = 600,
        mermaid_default_theme: str = "forest",
        mermaid_format: str = "svg",
        base_url: Optional[str] = None
    ):
        """
        初始化生成器
        :param workspace_path: 工作区路径，用于保存生成的图片
        :param api_endpoint: 图表API端点
        :param chart_default_width: 图表默认宽度
        :param chart_default_height: 图表默认高度
        :param mermaid_default_theme: Mermaid默认主题
        :param mermaid_format: Mermaid输出格式，可选 "svg" 或 "png"
        :param base_url: 图片访问的基础URL，用于生成完整的图片访问地址
        """
        self.detector = AutoChartDetector()
        self.enhancer = StyleEnhancer()
        self.api_client = ChartAPIClient(api_endpoint=api_endpoint)
        self.workspace_path = workspace_path
        self.chart_default_width = chart_default_width
        self.chart_default_height = chart_default_height
        self.mermaid_default_theme = mermaid_default_theme
        self.mermaid_format = mermaid_format.lower() if mermaid_format else "svg"
        self.base_url = base_url.rstrip("/") if base_url else None
        # 在工作区创建 images 目录
        if workspace_path:
            self.images_dir = workspace_path / "images"
            self.images_dir.mkdir(parents=True, exist_ok=True)
        else:
            self.images_dir = None

    async def generate(
        self,
        type: str,
        chart_type: Optional[str],
        data: Any,
        options: Optional[Dict] = None
    ) -> Dict[str, Any]:
        """
        生成可视化图表
        :param type: 类型 (chart/mermaid)
        :param chart_type: 图表类型
        :param data: 数据或Mermaid代码
        :param options: 额外选项
        :return: 生成结果
        """
        options = options or {}

        # 处理chart类型
        if type == "chart":
            return await self._generate_chart(chart_type, data, options)

        # 处理mermaid类型
        elif type == "mermaid":
            return await self._generate_mermaid(data, options)

        # 处理html类型
        elif type == "html":
            return await self._generate_html(data, options)

        else:
            return {
                "success": False,
                "error": f"不支持的类型: {type}",
                "type": type
            }

    async def _generate_chart(
        self,
        chart_type: Optional[str],
        data: Any,
        options: Dict
    ) -> Dict[str, Any]:
        """生成数据图表"""
        # 如果chart_type没填或auto，自动判断
        if not chart_type or chart_type.lower() == "auto":
            chart_type = self.detector.detect(data, type_hint="chart")

        # 自动增强数据样式
        if isinstance(data, list):
            enhanced_data = self.enhancer.enhance(data, chart_type)
        else:
            enhanced_data = data

        # 构建完整的chart_data
        chart_data = {
            "type": chart_type,
            "data": enhanced_data,
            "width": options.get("width", self.chart_default_width),
            "height": options.get("height", self.chart_default_height)
        }
        
        if options.get("title"):
            chart_data["title"] = options["title"]
        if options.get("axisXTitle"):
            chart_data["axisXTitle"] = options["axisXTitle"]
        if options.get("axisYTitle"):
            chart_data["axisYTitle"] = options["axisYTitle"]

        # 调用图床API
        result = await self.api_client.render_chart(chart_data)

        return result

    async def _generate_mermaid(
        self,
        code: str,
        options: Dict
    ) -> Dict[str, Any]:
        """生成Mermaid图表"""
        try:
            # 获取输出格式（优先使用 options 中的格式，否则使用配置的格式）
            output_format = options.get("format", self.mermaid_format).lower()
            if output_format not in ["svg", "png"]:
                output_format = "svg"  # 默认使用 SVG
            
            # 渲染Mermaid代码
            image_data = await self._render_mermaid(code, options, output_format)

            # 生成唯一文件名
            filename = f"mermaid_{uuid.uuid4()}.{output_format}"
            
            # 保存到工作区的 images 目录
            if not self.images_dir:
                return {
                    "success": False,
                    "error": "工作区路径未设置，无法保存图片"
                }
            
            file_path = self.images_dir / filename
            
            # 保存到工作区 images 目录
            with open(file_path, "wb") as f:
                f.write(image_data)
            
            # 同时复制到公共图床目录（按日期组织）
            try:
                from datetime import datetime
                import shutil
                
                # 获取图床目录路径：MCP_WORKSPACES_DIR/YYYYMMDD/
                workspaces_dir_env = os.environ.get("MCP_WORKSPACES_DIR", "")
                if workspaces_dir_env:
                    workspaces_dir = Path(workspaces_dir_env)
                else:
                    # 如果没有设置环境变量，使用默认路径
                    default_user_data_dir = Path(__file__).parent.parent.parent / "user_data"
                    workspaces_dir = default_user_data_dir
                
                # 创建日期目录（格式：YYYYMMDD）
                date_str = datetime.now().strftime("%Y%m%d")
                gallery_dir = workspaces_dir / date_str
                gallery_dir.mkdir(parents=True, exist_ok=True)
                
                # 复制文件到图床目录
                gallery_file = gallery_dir / filename
                shutil.copy2(file_path, gallery_file)
            except Exception as e:
                # 如果复制失败，记录日志但不影响主流程
                import sys
                print(f"Warning: Failed to copy image to gallery: {e}", file=sys.stderr)

            # 使用公开路由，构建可访问的URL 无需 user_id 和 chat_id（类似图床）
            relative_url = f"/api/public/image/{filename}"
            # 如果配置了 base_url，则拼接完整 URL
            image_url = f"{self.base_url}{relative_url}" if self.base_url else relative_url

            # 计算文件相对路径
            if self.workspace_path:
                file_relative = f"/{file_path.relative_to(self.workspace_path)}".replace("\\", "/")
            else:
                file_relative = f"/images/{filename}"

            return {
                "success": True,
                "url": image_url,
                "file": file_relative,
                "chart_type": "flowchart",
                "message": "Mermaid图表渲染成功"
            }

        except Exception as e:
            return {
                "success": False,
                "error": f"Mermaid渲染失败: {str(e)}"
            }
    
    async def _generate_html(
        self,
        html_code: str,
        options: Dict
    ) -> Dict[str, Any]:
        """生成HTML渲染的PNG图片"""
        try:
            if not self.workspace_path:
                return {
                    "success": False,
                    "error": "工作区路径未设置，无法保存文件"
                }
            
            # 生成唯一文件名
            unique_id = uuid.uuid4()
            html_filename = f"html_{unique_id}.html"
            png_filename = f"html_{unique_id}.png"
            
            # 保存HTML文件到工作区
            html_file_path = self.workspace_path / html_filename
            with open(html_file_path, "w", encoding="utf-8") as f:
                f.write(html_code)
            
            # 保存 PNG 到工作区 images 目录
            if not self.images_dir:
                return {
                    "success": False,
                    "error": "工作区路径未设置，无法保存图片"
                }
            
            images_png_path = self.images_dir / png_filename
            
            # 使用 playwright 渲染 HTML 为 PNG
            from playwright.async_api import async_playwright
            
            width = options.get("width", self.chart_default_width)
            height = options.get("height", self.chart_default_height)
            
            async with async_playwright() as p:
                browser = await p.chromium.launch(headless=True)
                page = await browser.new_page(viewport={"width": width, "height": height})
                
                # 加载 HTML 文件
                await page.goto(f"file://{html_file_path.resolve()}")
                
                # 等待页面加载完成
                await page.wait_for_load_state("networkidle", timeout=5000)
                
                # 截图直接保存到 images 目录
                await page.screenshot(path=str(images_png_path), type="png", full_page=True)
                
                await browser.close()
            
            # 同时复制到公共图床目录（按日期组织）
            try:
                from datetime import datetime
                import shutil
                
                # 获取图床目录路径：MCP_WORKSPACES_DIR/YYYYMMDD/
                workspaces_dir_env = os.environ.get("MCP_WORKSPACES_DIR", "")
                if workspaces_dir_env:
                    workspaces_dir = Path(workspaces_dir_env)
                else:
                    # 如果没有设置环境变量，使用默认路径
                    default_user_data_dir = Path(__file__).parent.parent.parent / "user_data"
                    workspaces_dir = default_user_data_dir
                
                # 创建日期目录（格式：YYYYMMDD）
                date_str = datetime.now().strftime("%Y%m%d")
                gallery_dir = workspaces_dir / date_str
                gallery_dir.mkdir(parents=True, exist_ok=True)
                
                # 复制文件到图床目录
                gallery_file = gallery_dir / png_filename
                shutil.copy2(images_png_path, gallery_file)
            except Exception as e:
                # 如果复制失败，记录日志但不影响主流程
                import sys
                print(f"Warning: Failed to copy image to gallery: {e}", file=sys.stderr)
            
            # 使用公开路由，构建可访问的URL 无需 user_id 和 chat_id（类似图床）
            relative_url = f"/api/public/image/{png_filename}"
            # 如果配置了 base_url，则拼接完整 URL
            image_url = f"{self.base_url}{relative_url}" if self.base_url else relative_url
            
            # 使用已有路径变量计算相对路径
            html_file = f"/{html_file_path.relative_to(self.workspace_path)}".replace("\\", "/")
            png_file = f"/{images_png_path.relative_to(self.workspace_path)}".replace("\\", "/")
            
            return {
                "success": True,
                "url": image_url,
                "html_file": html_file,
                "png_file": png_file,
                "message": "HTML渲染为PNG成功"
            }
            
        except Exception as e:
            return {
                "success": False,
                "error": f"HTML渲染失败: {str(e)}"
            }

    async def _render_mermaid(self, code: str, options: Dict, output_format: str) -> bytes:
        """使用mermaid-py渲染Mermaid代码为图片"""
        try:
            from mermaid import Mermaid
            from mermaid.graph import Graph

            # 预处理 mermaid 代码
            code = self._preprocess_mermaid_code(code)

            # 获取主题名称（优先使用用户指定的主题，否则使用配置的默认主题）
            theme_name = options.get("theme", self.mermaid_default_theme)
            
            # 判断是自定义主题还是内置主题
            if theme_name in MERMAID_CUSTOM_THEMES:
                theme_config = MERMAID_CUSTOM_THEMES[theme_name].copy()
            elif theme_name in MERMAID_BUILTIN_THEMES:
                theme_config = {"theme": theme_name}
                if "themeVariables" in options:
                    theme_config["themeVariables"] = options["themeVariables"]
            else:
                # 未知主题，使用默认
                if self.mermaid_default_theme in MERMAID_CUSTOM_THEMES:
                    theme_config = MERMAID_CUSTOM_THEMES[self.mermaid_default_theme].copy()
                else:
                    theme_config = {"theme": self.mermaid_default_theme}
            
            # 注入主题配置到 Mermaid 代码
            theme_init = f"%%{{init: {json.dumps(theme_config)}}}%%"
            
            # 组合代码：主题配置 + 标题（可选）+ 原始代码
            code_parts = [theme_init]
            
            # 如果有标题，使用YAML前置语法添加
            title = options.get("title", "")
            if title:
                code_parts.append(f"---\ntitle: {title}\n---")
            
            code_parts.append(code)
            code_with_theme = "\n".join(code_parts)
            
            # 创建Graph对象
            graph = Graph('diagram', code_with_theme)
            
            # 创建 Mermaid 对象
            diagram = Mermaid(graph)
            
            # 根据输出格式选择返回内容
            if output_format == "png":
                # 直接使用 mermaid-py 的 PNG 支持
                return diagram.img_response.content
            else:
                # 返回 SVG
                return diagram.svg_response.content
            
        except ImportError:
            # 如果mermaid-py未安装，回退到mermaid-cli
            return await self._render_mermaid_cli(code, options, output_format)
        except Exception as e:
            raise Exception(f"Mermaid渲染失败: {str(e)}")

    def _preprocess_mermaid_code(self, code: str) -> str:
        """
        预处理 Mermaid 代码，兼容 AI 智能体生成的各种格式

        处理内容：
        1. 将字面 \\n \\t \\r 转换为真正的换行符/制表符
        2. 将 subgraph 名称和节点标签中的括号 () 替换为其他符号，避免解析错误
        """
        import re

        # 1. 将字面转义字符转换为真正的控制字符
        code = code.replace('\\n', '\n').replace('\\t', '\t').replace('\\r', '\r')

        # 2. 处理 subgraph 中的括号
        # 匹配: subgraph "名称 (备注)" 或 subgraph 名称 (备注)
        # 将括号替换为方括号或破折号
        def replace_subgraph_parens(match):
            prefix = match.group(1)  # subgraph
            content = match.group(2)  # 名称内容
            # 将 (xxx) 替换为 - xxx
            content = re.sub(r'\s*\(([^)]*)\)', r' - \1', content)
            return prefix + content

        # 处理带引号的 subgraph: subgraph "xxx (yyy)"
        code = re.sub(
            r'(subgraph\s+)"([^"]*)"',
            lambda m: m.group(1) + '"' + re.sub(r'\s*\(([^)]*)\)', r' - \1', m.group(2)) + '"',
            code
        )

        # 处理不带引号的 subgraph: subgraph xxx (yyy) 直到换行
        code = re.sub(
            r'(subgraph\s+)([^\n"]+?)(\n)',
            lambda m: m.group(1) + re.sub(r'\s*\(([^)]*)\)', r' - \1', m.group(2)) + m.group(3),
            code
        )

        # 3. 处理节点标签中的括号（方括号内的内容）
        # 匹配: [名称 (备注)] 将其中的 () 替换
        def replace_bracket_parens(match):
            content = match.group(1)
            # 将 (xxx) 替换为 - xxx
            content = re.sub(r'\s*\(([^)]*)\)', r' - \1', content)
            return '[' + content + ']'

        code = re.sub(r'\[([^\]]*\([^\]]*)\]', replace_bracket_parens, code)

        # 4. 处理连接标签中的括号
        # 匹配: -- "标签 (备注)" --> 或 -- "标签(备注)" -->
        def replace_edge_label_parens(match):
            prefix = match.group(1)  # -- "
            content = match.group(2)  # 标签内容
            suffix = match.group(3)  # " -->
            content = re.sub(r'\s*\(([^)]*)\)', r' - \1', content)
            return prefix + content + suffix

        code = re.sub(
            r'(--\s*"|\|\s*)([^"|]*\([^"|]*)("|\|)',
            replace_edge_label_parens,
            code
        )

        return code


    async def _render_mermaid_cli(self, code: str, options: Dict, output_format: str = "svg") -> bytes:
        """使用mermaid-cli渲染（备用方案）"""
        import tempfile

        # 预处理 mermaid 代码
        code = self._preprocess_mermaid_code(code)

        temp_dir = tempfile.mkdtemp()
        temp_file = os.path.join(temp_dir, f"diagram_{uuid.uuid4()}.mmd")
        output_file = os.path.join(temp_dir, f"diagram_{uuid.uuid4()}.{output_format}")

        # 写入Mermaid代码
        with open(temp_file, "w", encoding="utf-8") as f:
            f.write(code)

        # 执行mermaid-cli（使用配置的默认值）
        width = options.get("width", self.chart_default_width)
        height = options.get("height", self.chart_default_height)

        cmd = [
            "mmdc",
            "-i", temp_file,
            "-o", output_file,
            "-t", "default",
            "-b", "white",
            "-w", str(width),
            "-H", str(height),
            "-f", output_format
        ]

        process = await asyncio.create_subprocess_exec(
            *cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE
        )

        stdout, stderr = await process.communicate()

        if process.returncode != 0:
            error_msg = stderr.decode() if stderr else "Unknown error"
            raise Exception(f"mermaid-cli执行失败: {error_msg}")

        # 读取生成的图片
        if not os.path.exists(output_file):
            raise Exception("图片文件未生成")

        with open(output_file, "rb") as f:
            return f.read()


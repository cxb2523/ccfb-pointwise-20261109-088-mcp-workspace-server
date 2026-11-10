"""图像生成工具 - generate_image

支持生成数据图表和Mermaid流程图
从 mcp-chart-python 项目整合
"""

import json
import logging
from pathlib import Path
from typing import Any, Dict, Optional

from ..utils.visualization_generator import VisualizationGenerator
from ..security import sanitize_error_simple

logger = logging.getLogger(__name__)


def load_image_config() -> Dict[str, Any]:
    """加载图像生成配置"""
    try:
        from ..server import load_config
        config = load_config()
        return config.get("image_generator", {})
    except Exception:
        return {}


async def generate_image(
    chart_data: Optional[Any] = None,
    mermaid_code: Optional[str] = None,
    html_code: Optional[str] = None,
    workspace_path: Optional[Path] = None,
) -> Dict[str, Any]:
    """
    生成图像（数据图表、Mermaid流程图或HTML渲染）
    
    Args:
        chart_data: 图表数据（JSON对象或字符串），包含type/data/title等字段
        mermaid_code: Mermaid代码字符串
        html_code: HTML代码字符串，将渲染为PNG图片
        workspace_path: 工作区路径，用于保存生成的图片
    
    Returns:
        生成结果字典
    """
    try:
        # 加载配置
        config = load_image_config()
        api_endpoint = config.get("chart_api_endpoint", "")
        chart_default_width = config.get("chart_default_width", 800)
        chart_default_height = config.get("chart_default_height", 600)
        mermaid_default_theme = config.get("mermaid_default_theme", "dark")
        mermaid_format = config.get("mermaid_format", "svg")
        base_url = config.get("base_url")
        
        # 创建生成器（传入配置参数）
        generator = VisualizationGenerator(
            workspace_path=workspace_path,
            api_endpoint=api_endpoint,
            chart_default_width=chart_default_width,
            chart_default_height=chart_default_height,
            mermaid_default_theme=mermaid_default_theme,
            mermaid_format=mermaid_format,
            base_url=base_url
        )
        
        # 处理chart_data（可能是dict、str、list）
        parsed_chart = None
        if chart_data is not None:
            if isinstance(chart_data, dict):
                parsed_chart = chart_data
            elif isinstance(chart_data, str) and chart_data.strip():
                try:
                    parsed_chart = json.loads(chart_data)
                except json.JSONDecodeError:
                    parsed_chart = None
            elif isinstance(chart_data, list) and len(chart_data) > 0:
                item = chart_data[0]
                if isinstance(item, dict):
                    parsed_chart = item
                elif isinstance(item, str) and item.strip():
                    try:
                        parsed_chart = json.loads(item)
                    except json.JSONDecodeError:
                        pass

        # 处理mermaid_code（可能是str、list）
        parsed_mermaid = None
        if mermaid_code is not None:
            if isinstance(mermaid_code, str) and mermaid_code.strip():
                parsed_mermaid = mermaid_code
            elif isinstance(mermaid_code, list) and len(mermaid_code) > 0:
                item = mermaid_code[0]
                if isinstance(item, str) and item.strip():
                    parsed_mermaid = item
        
        # 处理html_code（字符串格式）
        parsed_html = None
        if html_code is not None and isinstance(html_code, str) and html_code.strip():
            parsed_html = html_code

        # 判断生成类型（只能选择一种）
        provided_types = sum([
            parsed_chart is not None,
            parsed_mermaid is not None,
            parsed_html is not None
        ])
        
        if provided_types == 0:
            return {
                "success": False,
                "error": "请填写chart_data、mermaid_code或html_code其中之一"
            }
        
        if provided_types > 1:
            return {
                "success": False,
                "error": "chart_data、mermaid_code和html_code只能三选一，不能同时填写"
            }

        # 生成数据图表
        if parsed_chart:
            result = await generator.generate(
                type="chart",
                chart_type=parsed_chart.get("type", "auto"),
                data=parsed_chart.get("data", []),
                options={
                    "title": parsed_chart.get("title", ""),
                    "axisXTitle": parsed_chart.get("axisXTitle", ""),
                    "axisYTitle": parsed_chart.get("axisYTitle", ""),
                    "width": parsed_chart.get("width", chart_default_width),
                    "height": parsed_chart.get("height", chart_default_height)
                }
            )
        
        # 生成Mermaid流程图
        elif parsed_mermaid:
            # 从chart_data中提取theme和title（如果存在）
            theme = None
            title = ""
            if parsed_chart:
                theme = parsed_chart.get("theme")
                title = parsed_chart.get("title", "")
            
            result = await generator.generate(
                type="mermaid",
                chart_type="flowchart",
                data=parsed_mermaid,
                options={
                    "theme": theme,
                    "title": title
                }
            )
        
        # 生成HTML渲染图片
        elif parsed_html:
            result = await generator.generate(
                type="html",
                chart_type=None,
                data=parsed_html,
                options={
                    "width": chart_default_width,
                    "height": chart_default_height
                }
            )

        return result

    except Exception as e:
        logger.error(f"Error in generate_image: {e}", exc_info=True)
        return {
            "success": False,
            "error": f"处理失败: {str(e)}"
        }


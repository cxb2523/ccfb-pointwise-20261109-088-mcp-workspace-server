"""
API client for chart rendering service - 图表渲染API客户端
"""

import asyncio
import logging
from typing import Dict, Any, Optional

import httpx

logger = logging.getLogger(__name__)


class ChartAPIClient:
    """图表API客户端"""

    def __init__(self, api_endpoint: Optional[str] = None):
        """
        初始化API客户端
        :param api_endpoint: API端点URL，如果为None则从配置读取
        """
        self.api_endpoint = api_endpoint

    async def render_chart(self, chart_data: Dict, api_endpoint: Optional[str] = None) -> Dict[str, Any]:
        """
        渲染图表
        :param chart_data: 完整的图表数据，包含type、data、title等
        :param api_endpoint: 可选的API端点，覆盖默认值
        :return: 渲染结果
        """
        endpoint = api_endpoint or self.api_endpoint
        if not endpoint:
            return {
                "success": False,
                "error": "API端点未配置，请在config.json中设置image_generator.chart_api_endpoint",
                "type": "chart",
                "chart_type": chart_data.get("type", "auto")
            }

        request_data = {
            "type": chart_data.get("type", "auto"),
            "data": chart_data.get("data", []),
            "width": chart_data.get("width", 800),
            "height": chart_data.get("height", 600)
        }

        if chart_data.get("title"):
            request_data["title"] = chart_data["title"]
        if chart_data.get("axisXTitle"):
            request_data["axisXTitle"] = chart_data["axisXTitle"]
        if chart_data.get("axisYTitle"):
            request_data["axisYTitle"] = chart_data["axisYTitle"]

        chart_type = chart_data.get("type", "auto")

        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.post(
                    endpoint,
                    json=request_data,
                    headers={"Content-Type": "application/json"}
                )
                result = response.json()
                
                logger.info(f"图床API响应: {result}")

                if result.get("success"):
                    image_url = result.get("resultObj") or result.get("url", "")
                    return {
                        "success": True,
                        "url": image_url,
                        "type": "chart",
                        "chart_type": chart_type,
                        "message": "图表生成成功"
                    }
                else:
                    return {
                        "success": False,
                        "error": result.get("errorMessage", "未知错误"),
                        "type": "chart",
                        "chart_type": chart_type
                    }

        except httpx.TimeoutException:
            return {
                "success": False,
                "error": "API调用超时",
                "type": "chart",
                "chart_type": chart_type
            }
        except Exception as e:
            logger.error(f"API调用失败: {e}")
            return {
                "success": False,
                "error": f"API调用失败: {str(e)}",
                "type": "chart",
                "chart_type": chart_type
            }


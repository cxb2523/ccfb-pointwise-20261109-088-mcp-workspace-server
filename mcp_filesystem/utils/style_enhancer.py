"""
Style enhancer - 自动补充科技风样式
从 mcp-chart-python 项目整合
"""

from typing import List, Dict, Any

# 科技风配色方案（蓝绿科技风）
TECH_COLORS = [
    "#3b82f6",  # 蓝色-500
    "#10b981",  # 绿色-500
    "#06b6d4",  # 青色-500
    "#2563eb",  # 蓝色-600
    "#0d9488",  # 绿色-600
    "#0891b2",  # 青色-600
    "#1d4ed8",  # 蓝色-700
    "#047857",  # 绿色-700
    "#0e7490",  # 青色-700
    "#1e40af",  # 蓝色-800
    "#065f46",  # 绿色-800
    "#164e63",  # 青色-800
]


class StyleEnhancer:
    """科技风样式增强器"""

    def enhance(self, data: List[Dict], chart_type: str) -> List[Dict]:
        """
        自动增强数据样式
        :param data: 原始数据
        :param chart_type: 图表类型
        :return: 增强后的数据
        """
        if not data:
            return data

        # 如果数据已经有颜色，不处理
        if self._has_existing_color(data):
            return data

        # 根据图表类型增强
        if chart_type == "pie":
            return self._enhance_pie_chart(data)
        elif chart_type in ["bar", "column"]:
            return self._enhance_bar_chart(data)
        elif chart_type == "line":
            return self._enhance_line_chart(data)
        elif chart_type == "scatter":
            return self._enhance_scatter_chart(data)
        elif chart_type == "area":
            return self._enhance_area_chart(data)
        elif chart_type == "radar":
            return self._enhance_radar_chart(data)
        else:
            return self._enhance_generic_chart(data)

    def _enhance_pie_chart(self, data: List[Dict]) -> List[Dict]:
        """增强饼图数据"""
        result = []
        for i, item in enumerate(data):
            new_item = item.copy()
            if "color" not in new_item:
                new_item["color"] = TECH_COLORS[i % len(TECH_COLORS)]
            result.append(new_item)
        return result

    def _enhance_bar_chart(self, data: List[Dict]) -> List[Dict]:
        """增强柱状图数据"""
        result = []
        for i, item in enumerate(data):
            new_item = item.copy()
            if "color" not in new_item:
                new_item["color"] = TECH_COLORS[i % len(TECH_COLORS)]
            result.append(new_item)
        return result

    def _enhance_line_chart(self, data: List[Dict]) -> List[Dict]:
        """增强折线图数据"""
        result = []
        for i, item in enumerate(data):
            new_item = item.copy()
            if "color" not in new_item:
                # 折线图使用渐变色
                new_item["color"] = TECH_COLORS[i % len(TECH_COLORS)]
                new_item["strokeWidth"] = 2
            result.append(new_item)
        return result

    def _enhance_scatter_chart(self, data: List[Dict]) -> List[Dict]:
        """增强散点图数据"""
        result = []
        for i, item in enumerate(data):
            new_item = item.copy()
            if "color" not in new_item:
                new_item["color"] = TECH_COLORS[i % len(TECH_COLORS)]
                new_item["size"] = 5
            result.append(new_item)
        return result

    def _enhance_area_chart(self, data: List[Dict]) -> List[Dict]:
        """增强面积图数据"""
        result = []
        for i, item in enumerate(data):
            new_item = item.copy()
            if "color" not in new_item:
                new_item["color"] = TECH_COLORS[i % len(TECH_COLORS)]
                new_item["opacity"] = 0.6
            result.append(new_item)
        return result

    def _enhance_radar_chart(self, data: List[Dict]) -> List[Dict]:
        """增强雷达图数据"""
        result = []
        for i, item in enumerate(data):
            new_item = item.copy()
            if "color" not in new_item:
                new_item["color"] = TECH_COLORS[i % len(TECH_COLORS)]
                new_item["fillOpacity"] = 0.3
            result.append(new_item)
        return result

    def _enhance_generic_chart(self, data: List[Dict]) -> List[Dict]:
        """通用增强"""
        result = []
        for i, item in enumerate(data):
            new_item = item.copy()
            if "color" not in new_item:
                new_item["color"] = TECH_COLORS[i % len(TECH_COLORS)]
            result.append(new_item)
        return result

    def _has_existing_color(self, data: List[Dict]) -> bool:
        """检查是否已有颜色"""
        if not data:
            return False

        sample = data[0]
        color_fields = ["color", "fill", "stroke", "backgroundColor", "fillColor"]
        return any(field in sample for field in color_fields)


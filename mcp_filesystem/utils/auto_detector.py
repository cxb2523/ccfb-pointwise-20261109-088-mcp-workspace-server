"""
Auto chart type detector - 自动检测图表类型
从 mcp-chart-python 项目整合
"""

import re
from typing import List, Dict, Any


class AutoChartDetector:
    """自动检测图表类型"""

    def detect(self, data: Any, type_hint: str = None) -> str:
        """
        自动检测图表类型，直接返回类型，不返回推荐信息
        :param data: 数据
        :param type_hint: 类型提示 (chart/mermaid)
        :return: 图表类型字符串
        """
        # 如果是mermaid，不检测
        if type_hint == "mermaid":
            return "mermaid"

        # 如果是列表/数组，分析图表类型
        if isinstance(data, list) and data:
            chart_type = self._detect_chart_type_simple(data)
            return chart_type

        # 如果是字符串，可能是mermaid
        if isinstance(data, str):
            if self._is_mermaid_code(data):
                return "mermaid"

        # 默认返回柱状图
        return "bar"

    def _detect_chart_type_simple(self, data: List[Dict]) -> str:
        """简单检测图表类型，直接返回类型"""
        if not data:
            return "bar"

        sample = data[0]
        fields = list(sample.keys())

        # 分析数据特征
        features = self._analyze_features(data, fields)

        # 获取最佳推荐
        recommendations = self._recommend_charts(features)

        return recommendations[0]["chart_type"] if recommendations else "bar"

    def _analyze_features(self, data: List[Dict], fields: List[str]) -> Dict[str, Any]:
        """分析数据特征"""
        return {
            "total_fields": len(fields),
            "time_fields": self._find_time_fields(fields, data),
            "numeric_fields": self._find_numeric_fields(fields, data),
            "categorical_fields": self._find_categorical_fields(fields, data),
            "sample_size": len(data),
            "has_groups": self._has_grouping_fields(fields)
        }

    def _find_time_fields(self, fields: List[str], data: List[Dict]) -> List[str]:
        """查找时间字段"""
        time_patterns = [r'time', r'date', r'month', r'year', r'day', r'period']

        for field in fields:
            for pattern in time_patterns:
                if re.search(pattern, field, re.IGNORECASE):
                    if self._validate_time_data(field, data):
                        return [field]
        return []

    def _validate_time_data(self, field: str, data: List[Dict]) -> bool:
        """验证时间数据"""
        date_patterns = [
            r'\d{4}-\d{2}-\d{2}',  # 2024-01-01
            r'\d{4}/\d{2}/\d{2}',  # 2024/01/01
            r'\d{4}-\d{2}',        # 2024-01
            r'\d{2}:\d{2}',        # 14:30
            r'Q[1-4]\d{4}',        # Q12024
        ]

        sample_count = 0
        for item in data[:5]:
            value = str(item.get(field, ""))
            for pattern in date_patterns:
                if re.search(pattern, value):
                    sample_count += 1
                    break

        return sample_count >= 3

    def _find_numeric_fields(self, fields: List[str], data: List[Dict]) -> List[str]:
        """查找数值字段"""
        numeric_fields = []
        for field in fields:
            numeric_count = 0
            for item in data[:5]:
                try:
                    float(str(item.get(field, 0)))
                    numeric_count += 1
                except:
                    pass
            if numeric_count >= 3:
                numeric_fields.append(field)
        return numeric_fields

    def _find_categorical_fields(self, fields: List[str], data: List[Dict]) -> List[str]:
        """查找分类字段"""
        categorical_fields = []
        for field in fields:
            try:
                unique_values = set(str(item.get(field)) for item in data[:10])
                if 2 <= len(unique_values) <= 20:  # 合理分类数量
                    categorical_fields.append(field)
            except:
                pass
        return categorical_fields

    def _has_grouping_fields(self, fields: List[str]) -> bool:
        """检查是否有分组字段"""
        group_fields = ["group", "category", "type", "class", "label", "name"]
        return any(field in fields for field in group_fields)

    def _recommend_charts(self, features: Dict) -> List[Dict]:
        """推荐图表类型"""
        recommendations = []

        # 时间序列数据 - 推荐折线图/面积图
        if features.get("time_fields") and features.get("numeric_fields"):
            recommendations.append({
                "chart_type": "line",
                "confidence": 0.9,
                "reason": "检测到时间序列数据，推荐折线图"
            })
            recommendations.append({
                "chart_type": "area",
                "confidence": 0.8,
                "reason": "面积图适合展示累积趋势"
            })

        # 分类对比数据 - 推荐饼图/柱状图
        if features.get("categorical_fields") and features.get("numeric_fields"):
            if features["sample_size"] <= 6:
                recommendations.append({
                    "chart_type": "pie",
                    "confidence": 0.85,
                    "reason": "数据量少，适合饼图展示占比"
                })
            recommendations.append({
                "chart_type": "bar",
                "confidence": 0.9,
                "reason": "分类数据对比，推荐柱状图"
            })
            recommendations.append({
                "chart_type": "column",
                "confidence": 0.85,
                "reason": "垂直柱状图适合分类对比"
            })

        # 散点图（相关性分析）
        if len(features.get("numeric_fields", [])) >= 2:
            recommendations.append({
                "chart_type": "scatter",
                "confidence": 0.8,
                "reason": "多个数值字段，适合散点图展示相关性"
            })

        # 分布分析
        if len(features.get("numeric_fields", [])) >= 1:
            recommendations.append({
                "chart_type": "histogram",
                "confidence": 0.7,
                "reason": "数值分布分析"
            })
            recommendations.append({
                "chart_type": "boxplot",
                "confidence": 0.65,
                "reason": "统计分布分析"
            })

        # 软件公司常用高级图表
        if len(features.get("numeric_fields", [])) >= 3:
            recommendations.append({
                "chart_type": "radar",
                "confidence": 0.75,
                "reason": "多维度数据，适合雷达图对比"
            })
            recommendations.append({
                "chart_type": "treemap",
                "confidence": 0.7,
                "reason": "层级数据结构，适合树图展示"
            })
            recommendations.append({
                "chart_type": "sankey",
                "confidence": 0.65,
                "reason": "流向分析"
            })

        # 其他场景
        if features.get("has_groups"):
            recommendations.append({
                "chart_type": "funnel",
                "confidence": 0.6,
                "reason": "转化漏斗分析"
            })

        # 默认推荐
        if not recommendations:
            recommendations.append({
                "chart_type": "bar",
                "confidence": 0.6,
                "reason": "默认推荐柱状图"
            })

        return recommendations[:5]  # 返回前5个推荐

    def _is_mermaid_code(self, text: str) -> bool:
        """检查是否为Mermaid代码"""
        text = text.strip()

        # Mermaid代码模式
        mermaid_patterns = [
            r'^\s*(flowchart|graph)\s+[TD|LR|BT|RL]',
            r'^\s*sequenceDiagram',
            r'^\s*classDiagram',
            r'^\s*stateDiagram',
            r'^\s*gantt',
            r'^\s*erDiagram',
            r'^\s*journey',
            r'^\s*mindmap',
            r'^\s*timeline',
            r'^\s*quadrantChart',
            r'^\s*gitgraph'
        ]

        for pattern in mermaid_patterns:
            if re.search(pattern, text, re.IGNORECASE):
                return True

        # 检查是否包含mermaid标识
        if "```mermaid" in text or "graph" in text.lower() or "sequenceDiagram" in text:
            return True

        return False


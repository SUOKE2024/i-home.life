"""质检知识服务 — QAInspectorAgent 专用知识注入

质检 Agent 在验收检查时自动检索：
1. 对应工种的施工规范（来自 techniques.json）
2. 对应材料的验收标准（来自 standards.json）
3. 常见质量缺陷与判定标准（来自 faq.json）
"""
from __future__ import annotations

import logging
from typing import Any

from knowledge.loader import load_knowledge_base

logger = logging.getLogger(__name__)

# 施工阶段到知识域/标签的映射
_PHASE_KNOWLEDGE_MAP: dict[str, dict[str, Any]] = {
    "mep": {
        "name": "水电工程",
        "technique_tags": ["水电改造", "水电", "打压", "电路", "布线"],
        "standard_tags": ["电气", "给排水", "验收", "水电"],
        "defect_keywords": ["水电", "漏水", "电路", "短路", "接线"],
    },
    "masonry": {
        "name": "泥瓦工程",
        "technique_tags": ["瓷砖", "防水", "铺贴", "铺装"],
        "standard_tags": ["瓷砖", "防水", "饰面砖", "验收"],
        "defect_keywords": ["空鼓", "裂缝", "渗漏", "瓷砖", "防水", "平整度"],
    },
    "carpentry": {
        "name": "木工工程",
        "technique_tags": ["吊顶", "木工", "柜体", "安装", "接缝", "龙骨"],
        "standard_tags": ["吊顶", "细部", "木家具", "验收"],
        "defect_keywords": ["吊顶", "柜门", "缝隙", "平整度", "安装"],
    },
    "painting": {
        "name": "油漆工程",
        "technique_tags": ["墙面", "腻子", "底漆", "面漆", "涂刷", "油漆"],
        "standard_tags": ["涂饰", "涂料", "VOC", "验收"],
        "defect_keywords": ["色差", "流坠", "平整度", "阴阳角", "开裂"],
    },
    "installation": {
        "name": "安装工程",
        "technique_tags": ["安装", "卫浴", "洁具", "灯具"],
        "standard_tags": ["安装", "电气", "验收"],
        "defect_keywords": ["安装", "松动", "不牢固", "接线"],
    },
}


class QAKnowledgeService:
    """质检知识服务 — 为 QAInspectorAgent 注入领域知识。

    质检 Agent 进行验收检查时，通过本服务自动检索对应工种的施工规范、
    材料验收标准和常见缺陷知识，确保验收报告有据可依、引用标准准确。
    """

    def __init__(self) -> None:
        self._loader = load_knowledge_base()

    def get_checklist(self, phase: str) -> list[dict[str, Any]]:
        """获取指定施工阶段的质检清单。

        综合 techniques.json 中的施工规范和 standards.json 中的验收标准，
        生成该阶段的验收检查项列表。

        Args:
            phase: 施工阶段代码（mep/masonry/carpentry/painting/installation）

        Returns:
            质检清单列表，每项包含 item/standard/citation/tags
        """
        phase_info = _PHASE_KNOWLEDGE_MAP.get(phase)
        if not phase_info:
            logger.warning("未知施工阶段: %s", phase)
            return []

        checklist: list[dict[str, Any]] = []
        seen: set[str] = set()

        # 1. 从施工工艺库检索
        for tag in phase_info.get("technique_tags", []):
            results = self._loader.keyword_search(
                tag, domains=["techniques"], max_results=5
            )
            for entry in results:
                item_key = entry.get("content", "")[:50]
                if item_key not in seen:
                    seen.add(item_key)
                    checklist.append({
                        "item": entry.get("content", ""),
                        "citation": entry.get("citation", ""),
                        "tags": entry.get("tags", []),
                        "source": "techniques",
                    })

        # 2. 从验收标准库检索
        for tag in phase_info.get("standard_tags", []):
            results = self._loader.keyword_search(
                tag, domains=["standards"], max_results=3
            )
            for entry in results:
                item_key = entry.get("content", "")[:50]
                if item_key not in seen:
                    seen.add(item_key)
                    checklist.append({
                        "item": entry.get("content", ""),
                        "citation": entry.get("citation", ""),
                        "tags": entry.get("tags", []),
                        "source": "standards",
                    })

        return checklist

    def check_standard(self, material: str, attribute: str = "") -> dict[str, Any]:
        """查询某材料属性的验收标准。

        Args:
            material: 材料名称或品类（如 瓷砖/地板/涂料/板材）
            attribute: 属性名称（如 空鼓率/平整度/VOC含量/甲醛释放量）

        Returns:
            标准信息字典，包含 content/citation/tags；未找到返回空字典
        """
        # 组合查询
        query = f"{material} {attribute}".strip() if attribute else material

        # 优先从标准库检索
        results = self._loader.keyword_search(query, domains=["standards"], max_results=3)
        if results:
            return {
                "material": material,
                "attribute": attribute,
                "standard_content": results[0].get("content", ""),
                "citation": results[0].get("citation", ""),
                "tags": results[0].get("tags", []),
                "all_results": results,
            }

        # 降级到材料库
        results = self._loader.keyword_search(query, domains=["materials"], max_results=3)
        if results:
            return {
                "material": material,
                "attribute": attribute,
                "standard_content": results[0].get("content", ""),
                "citation": results[0].get("citation", ""),
                "tags": results[0].get("tags", []),
                "all_results": results,
            }

        return {
            "material": material,
            "attribute": attribute,
            "standard_content": "",
            "citation": "",
            "tags": [],
            "all_results": [],
        }

    def get_defect_knowledge(self, keyword: str) -> list[dict[str, Any]]:
        """根据关键词搜索已知质量缺陷。

        从 FAQ 库和施工工艺库中检索与缺陷关键词相关的内容。

        Args:
            keyword: 缺陷关键词（如 空鼓/裂缝/渗漏/色差/平整度/缝隙/安装）

        Returns:
            缺陷知识条目列表
        """
        results: list[dict[str, Any]] = []

        # 1. FAQ 库中检索
        faq_results = self._loader.keyword_search(
            keyword, domains=["faq"], max_results=5
        )
        results.extend(faq_results)

        # 2. 施工工艺库中检索
        tech_results = self._loader.keyword_search(
            keyword, domains=["techniques"], max_results=3
        )
        results.extend(tech_results)

        return results

    def get_defect_standard(self, defect_type: str, material: str = "") -> dict[str, Any]:
        """获取缺陷的判定标准。

        结合常见缺陷分类和材料属性，返回具体的判定标准。

        Args:
            defect_type: 缺陷类型（空鼓/裂缝/渗漏/色差/平整度/缝隙/安装）
            material: 材料或部位（如 瓷砖/墙面/吊顶/水电）

        Returns:
            缺陷判定标准信息
        """
        # 缺陷类型到标准查询词的映射
        defect_query_map: dict[str, str] = {
            "空鼓": "空鼓率 标准",
            "裂缝": "裂缝 开裂 标准",
            "渗漏": "防水 渗漏 闭水试验",
            "色差": "色差 验收",
            "平整度": "平整度 偏差",
            "缝隙": "缝隙 留缝 接缝",
            "安装": "安装 牢固",
        }

        query = defect_query_map.get(defect_type, f"{defect_type} {material}".strip())
        if material:
            query = f"{material} {query}"

        # 从标准库和施工工艺库检索
        all_results = []
        standard_results = self._loader.keyword_search(
            query, domains=["standards"], max_results=3
        )
        all_results.extend(standard_results)

        tech_results = self._loader.keyword_search(
            query, domains=["techniques"], max_results=2
        )
        all_results.extend(tech_results)

        # 提取缺陷的数值标准
        numeric_standards = self._extract_numeric_standards(defect_type, all_results)

        return {
            "defect_type": defect_type,
            "material": material,
            "all_results": all_results,
            "numeric_standards": numeric_standards,
            "citation": all_results[0].get("citation", "") if all_results else "",
        }

    @staticmethod
    def _extract_numeric_standards(
        defect_type: str, results: list[dict[str, Any]]
    ) -> list[str]:
        """从搜索结果中提取数值型标准要求。

        Args:
            defect_type: 缺陷类型
            results: 搜索结果

        Returns:
            数值标准列表
        """
        # 预定义的常见数值标准
        known_standards: dict[str, list[str]] = {
            "空鼓": ["单砖边角空鼓<5%不计", "整体空鼓率<3%"],
            "平整度": ["2m靠尺：地砖≤2mm，墙面≤3mm"],
            "缝隙": ["墙砖缝隙1.5-2mm", "地砖缝隙2-3mm", "柜门缝隙1.5-2.5mm"],
            "渗漏": ["闭水试验≥24h无渗漏", "压力降<0.05MPa"],
            "裂缝": ["宽度≤0.3mm为微裂缝", "结构裂缝需挂网处理"],
            "色差": ["1.5m距离目测无可见色差"],
            "安装": ["水平度偏差≤2mm/m", "牢固度≥4倍自重"],
        }

        return known_standards.get(defect_type, [])


# 模块级单例
qa_knowledge_service = QAKnowledgeService()

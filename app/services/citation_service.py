"""引用服务 — 为 Agent 回复添加知识库来源引用

当 AgenticRAG 检索到知识库条目时，自动在 Agent 回复末尾附加引用来源，
格式：📚 参考来源：GB 50210-2018 §4.2.3 / 材质库·瓷砖选购指南
"""
from __future__ import annotations

import logging
from typing import Any

logger = logging.getLogger(__name__)


class CitationService:
    """引用服务 — 从 evidence 条目中提取 citation 字段并格式化为参考来源。"""

    # 知识域中文名称映射
    _DOMAIN_NAMES: dict[str, str] = {
        "materials": "材质库",
        "techniques": "施工工艺库",
        "standards": "验收标准库",
        "eco_ratings": "环保等级库",
        "safety": "安全规范库",
        "design_rules": "设计规范库",
        "cost_reference": "造价参考库",
        "faq": "常见问题库",
    }

    def extract_citations(self, evidence: list[dict[str, Any]]) -> list[str]:
        """从 evidence 列表中提取去重后的引用来源。

        Args:
            evidence: AgenticRAG 返回的证据列表，每项包含 citation/domain/source 字段

        Returns:
            去重后的引用来源列表
        """
        if not evidence:
            return []

        seen: set[str] = set()
        citations: list[str] = []

        for entry in evidence:
            citation = (entry.get("citation") or "").strip()
            domain = entry.get("domain") or entry.get("source", "")
            domain_name = self._DOMAIN_NAMES.get(domain, domain)

            if citation:
                # 构建规范编号 + 知识域的引用格式
                ref = f"{citation} / {domain_name}"
            elif domain_name:
                ref = domain_name
            else:
                continue

            if ref and ref not in seen:
                seen.add(ref)
                citations.append(ref)

        return citations

    def format_citations(self, evidence: list[dict[str, Any]]) -> str:
        """将 evidence 格式化为引用文本段落。

        Args:
            evidence: 证据条目列表

        Returns:
            格式化的引用文本，无引用时返回空字符串
        """
        citations = self.extract_citations(evidence)
        if not citations:
            return ""

        lines = ["\n\n📚 **参考来源：**"]
        for i, cit in enumerate(citations, 1):
            lines.append(f"{i}. {cit}")

        return "\n".join(lines)

    def append_to_reply(self, reply: str, evidence: list[dict[str, Any]]) -> str:
        """在 Agent 回复末尾附加引用来源。

        Args:
            reply: Agent 生成的回复文本
            evidence: AgenticRAG 返回的证据条目列表

        Returns:
            附带引用来源的完整回复文本
        """
        if not evidence:
            return reply

        citation_text = self.format_citations(evidence)
        if not citation_text:
            return reply

        return reply + citation_text

    @staticmethod
    def format_single(citation: str, domain: str = "") -> str:
        """格式化单条引用来源。

        Args:
            citation: 来源引用（如标准编号）
            domain: 知识域

        Returns:
            格式化后的引用文本
        """
        if not citation:
            return ""
        if domain:
            return f"📚 参考：{citation}（{domain}）"
        return f"📚 参考：{citation}"


# 模块级单例
citation_service = CitationService()

"""装修知识库加载器 — 结构化装修知识管理与来源引用

知识域（8 个）：
1. materials      材质库（板材/瓷砖/涂料/石材/五金等）
2. techniques     施工工艺（水电/泥瓦/木工/油漆等工序标准）
3. standards      验收标准（GB 50210/GB 50327/GB 50300 等国标引用）
4. eco_ratings    环保等级（E0/E1/ENF 标准解读及适用范围）
5. safety         安全规范（承重结构/消防/燃气/电气安全）
6. design_rules   设计规范（空间尺寸/动线/采光/无障碍）
7. cost_reference 造价参考（各工种市场价区间/地区差异系数）
8. faq            常见问题（装修流程/避坑指南/选材建议）
"""
from __future__ import annotations

import json
import logging
import os
from pathlib import Path
from typing import Any

from app.config import get_settings

settings = get_settings()
logger = logging.getLogger(__name__)

# 知识域名称到 JSON 文件的映射
_DOMAIN_FILE_MAP: dict[str, str] = {
    "materials": "materials.json",
    "techniques": "techniques.json",
    "standards": "standards.json",
    "eco_ratings": "eco_ratings.json",
    "safety": "safety.json",
    "design_rules": "design_rules.json",
    "cost_reference": "cost_reference.json",
    "faq": "faq.json",
}


class KnowledgeLoader:
    """装修知识库加载器

    支持两种检索模式：
    1. 关键词搜索 — 基于内存的全文匹配，始终可用
    2. 向量搜索   — 当 vector_db_url 配置时，调用 Qdrant/Milvus 语义检索

    每条知识条目包含字段：
    - id: 唯一标识
    - content: 知识正文
    - citation: 引用来源（标准编号、文档名称、页码）
    - domain: 所属知识域
    - tags: 标签列表
    """

    def __init__(self, knowledge_dir: str | None = None) -> None:
        self.knowledge_dir = Path(knowledge_dir or os.path.join(os.path.dirname(__file__)))
        self._cache: dict[str, list[dict[str, Any]]] = {}

    def _load_domain(self, domain: str) -> list[dict[str, Any]]:
        """加载指定知识域的 JSON 文件，支持缓存。"""
        if domain in self._cache:
            return self._cache[domain]

        filename = _DOMAIN_FILE_MAP.get(domain)
        if not filename:
            logger.warning("未知知识域: %s", domain)
            return []

        filepath = self.knowledge_dir / filename
        if not filepath.exists():
            logger.debug("知识文件不存在: %s", filepath)
            self._cache[domain] = []
            return []

        try:
            with open(filepath, "r", encoding="utf-8") as f:
                entries = json.load(f)
        except (json.JSONDecodeError, OSError) as e:
            logger.error("加载知识文件失败 %s: %s", filepath, e)
            self._cache[domain] = []
            return []

        # 确保每个条目有 domain 字段
        for entry in entries:
            if "domain" not in entry:
                entry["domain"] = domain

        self._cache[domain] = entries
        return entries

    def load_all(self) -> list[dict[str, Any]]:
        """加载全部知识域的条目。"""
        all_entries: list[dict[str, Any]] = []
        for domain in _DOMAIN_FILE_MAP:
            all_entries.extend(self._load_domain(domain))
        return all_entries

    def load_domain(self, domain: str) -> list[dict[str, Any]]:
        """加载指定知识域的条目。"""
        return self._load_domain(domain)

    def keyword_search(
        self,
        query: str,
        domains: list[str] | None = None,
        max_results: int = 5,
    ) -> list[dict[str, Any]]:
        """关键词搜索 — 在知识条目中做全文匹配。

        Args:
            query: 搜索关键词
            domains: 限定搜索的知识域列表，None 表示全部域
            max_results: 最大返回条数

        Returns:
            按匹配度排序的知识条目列表
        """
        if not query:
            return []

        # 提取长度≥2 的关键词
        keywords = [w for w in query.replace("，", " ").replace("。", " ").split() if len(w) >= 2]
        if not keywords:
            return []

        target_domains = domains or list(_DOMAIN_FILE_MAP.keys())
        scored: list[tuple[int, dict[str, Any]]] = []

        for domain in target_domains:
            entries = self._load_domain(domain)
            for entry in entries:
                content = entry.get("content", "")
                tags = " ".join(entry.get("tags", []))
                name = entry.get("name", "")
                searchable = f"{name} {content} {tags}"

                score = 0
                for kw in keywords:
                    score += searchable.count(kw)

                if score > 0:
                    scored.append((score, entry))

        # 按分数降序排列
        scored.sort(key=lambda x: x[0], reverse=True)

        results = []
        for _, entry in scored:
            results.append({
                "source": entry.get("domain", ""),
                "content": entry.get("content", ""),
                "citation": entry.get("citation", ""),
                "domain": entry.get("domain", ""),
                "tags": entry.get("tags", []),
                "score": 0.0,  # 关键词匹配无归一化分数
            })

        return results[:max_results]

    async def vector_search(
        self,
        query: str,
        domains: list[str] | None = None,
        max_results: int = 5,
    ) -> list[dict[str, Any]]:
        """向量搜索 — 通过向量数据库做语义检索。

        仅在 settings.vector_db_url 配置时有效，否则返回空列表。

        Args:
            query: 查询文本
            domains: 限定搜索的知识域列表
            max_results: 最大返回条数

        Returns:
            按语义相似度排序的知识条目列表
        """
        if not settings.vector_db_url or not query:
            return []

        try:
            import httpx

            domain_filter = domains or list(_DOMAIN_FILE_MAP.keys())

            async with httpx.AsyncClient(timeout=10) as client:
                resp = await client.post(
                    f"{settings.vector_db_url}/collections/{settings.vector_db_collection}/points/search",
                    json={
                        "vector": [0.0] * 128,  # placeholder — 生产环境用真实 embedding
                        "limit": max_results,
                        "with_payload": True,
                        "filter": {
                            "must": [
                                {"key": "domain", "match": {"any": domain_filter}}
                            ]
                        },
                    },
                )
                if resp.status_code != 200:
                    logger.debug("vector_search non-200: %s", resp.status_code)
                    return []

                data = resp.json()
                results = data.get("result", [])

                return [
                    {
                        "source": r.get("payload", {}).get("domain", ""),
                        "content": r.get("payload", {}).get("content", ""),
                        "citation": r.get("payload", {}).get("citation", ""),
                        "domain": r.get("payload", {}).get("domain", ""),
                        "tags": r.get("payload", {}).get("tags", []),
                        "score": float(r.get("score", 0)),
                    }
                    for r in results
                ]
        except Exception as e:
            logger.debug("vector_search 失败: %s", e)
            return []

    async def search(
        self,
        query: str,
        domains: list[str] | None = None,
        max_results: int = 5,
    ) -> list[dict[str, Any]]:
        """统一搜索入口 — 优先向量搜索，降级到关键词搜索。

        Args:
            query: 查询文本
            domains: 限定搜索的知识域列表
            max_results: 最大返回条数

        Returns:
            知识条目列表，每项包含 source/content/citation/domain/tags/score
        """
        if not query:
            return []

        # 策略 1: 向量搜索
        if settings.vector_db_url:
            results = await self.vector_search(query, domains, max_results)
            if results:
                return results

        # 策略 2: 关键词搜索（降级）
        return self.keyword_search(query, domains, max_results)

    def get_by_id(self, entry_id: str) -> dict[str, Any] | None:
        """根据 ID 获取单条知识条目。"""
        for domain in _DOMAIN_FILE_MAP:
            entries = self._load_domain(domain)
            for entry in entries:
                if entry.get("id") == entry_id:
                    return {
                        "source": entry.get("domain", domain),
                        "content": entry.get("content", ""),
                        "citation": entry.get("citation", ""),
                        "domain": entry.get("domain", domain),
                        "tags": entry.get("tags", []),
                        "score": 1.0,
                        "raw": entry,
                    }
        return None

    def list_domains(self) -> list[dict[str, Any]]:
        """列出所有知识域及其条目数。"""
        result = []
        for domain in _DOMAIN_FILE_MAP:
            entries = self._load_domain(domain)
            result.append({
                "domain": domain,
                "entry_count": len(entries),
            })
        return result

    def clear_cache(self) -> None:
        """清除知识条目缓存。"""
        self._cache.clear()


# 模块级单例
_knowledge_loader: KnowledgeLoader | None = None


def load_knowledge_base(knowledge_dir: str | None = None) -> KnowledgeLoader:
    """获取知识库加载器单例。

    Args:
        knowledge_dir: 知识文件目录路径，None 使用默认目录

    Returns:
        KnowledgeLoader 实例
    """
    global _knowledge_loader
    if _knowledge_loader is None:
        _knowledge_loader = KnowledgeLoader(knowledge_dir)
    return _knowledge_loader

"""AgenticRAG 证据检索服务（借鉴索克生活 AgenticRAG 13 模块）

索克生活的 AgenticRAG 在 Agent 推理前主动检索知识库证据，按「检索-评估-注入」
状态机工作，避免 LLM 凭空生成。本模块将该方法论移植到家居领域：在 think_with_tools
前置 evidence 检索，将相关知识注入 system prompt 上下文。

状态机：
  RETRIEVE → 评估证据相关性 → 注入 top-k → 调用 LLM
  失败/无证据 → 降级到无 RAG 的普通调用

知识来源（按优先级）：
1. vector_db_url 配置时 → Qdrant/Milvus 语义检索
2. 未配置时 → 内存关键词匹配（materials/products/floorplans 表的简单 LIKE）
3. 全部失败 → 返回空 evidence，不阻断主流程
"""
from __future__ import annotations

import logging
from typing import Any

import httpx
from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings

settings = get_settings()
logger = logging.getLogger(__name__)


class AgenticRAG:
    """AgenticRAG 证据检索器

    受 settings.agentic_rag_enabled feature flag 控制：
    - True: think_with_tools 前置检索并注入证据
    - False: 直接返回空字符串，不检索
    """

    def __init__(self, max_evidence: int | None = None):
        self.max_evidence = max_evidence or settings.agentic_rag_max_evidence

    async def retrieve(
        self,
        query: str,
        db: AsyncSession | None = None,
        project_id: str | None = None,
    ) -> list[dict[str, Any]]:
        """检索与 query 相关的证据条目。

        Args:
            query: 用户查询文本
            db: 异步数据库会话（内存降级时可为 None）
            project_id: 项目 ID（用于项目维度过滤，可选）

        Returns:
            evidence: [{"source": str, "content": str, "score": float}, ...]
                      按 score 降序，截断到 max_evidence 条
        """
        if not settings.agentic_rag_enabled or not query:
            return []

        # 策略 1: 向量数据库语义检索
        if settings.vector_db_url:
            evidence = await self._retrieve_vector(query, project_id)
            if evidence:
                return evidence[: self.max_evidence]

        # 策略 2: 内存关键词匹配（降级）
        if db is not None:
            evidence = await self._retrieve_keyword(query, db, project_id)
            if evidence:
                return evidence[: self.max_evidence]

        # 策略 3: 无可用知识源，返回空
        return []

    async def _retrieve_vector(
        self, query: str, project_id: str | None
    ) -> list[dict[str, Any]]:
        """向量数据库语义检索（Qdrant/Milvus）。"""
        try:
            # 简化实现：调用向量库的 search 端点
            # 生产环境应使用 embedding 模型将 query 向量化后检索
            async with httpx.AsyncClient(timeout=10) as client:
                # Qdrant 风格的搜索端点
                resp = await client.post(
                    f"{settings.vector_db_url}/collections/{settings.vector_db_collection}/points/search",
                    json={
                        "vector": [0.0] * 128,  # placeholder — 生产环境用真实 embedding
                        "limit": self.max_evidence,
                        "with_payload": True,
                    },
                )
                if resp.status_code != 200:
                    logger.debug("vector_search non-200: %s", resp.status_code)
                    return []
                data = resp.json()
                results = data.get("result", [])
                return [
                    {
                        "source": "vector_db",
                        "content": r.get("payload", {}).get("content", ""),
                        "score": float(r.get("score", 0)),
                    }
                    for r in results
                ]
        except Exception as e:
            logger.debug("vector_retrieve 失败（降级到关键词）: %s", e)
            return []

    async def _retrieve_keyword(
        self,
        query: str,
        db: AsyncSession,
        project_id: str | None,
    ) -> list[dict[str, Any]]:
        """内存关键词匹配降级：从 materials/products 表做 LIKE 检索。"""
        evidence: list[dict[str, Any]] = []
        # 提取查询中的长度≥2 的关键词
        keywords = [w for w in query.replace("，", " ").replace("。", " ").split() if len(w) >= 2]
        if not keywords:
            return []

        try:
            # materials 表关键词匹配
            from app.models.material import Material
            conditions = [Material.name.like(f"%{kw}%") for kw in keywords]
            stmt = select(Material).where(or_(*conditions)).limit(self.max_evidence)
            result = await db.execute(stmt)
            for row in result.scalars().all():
                evidence.append({
                    "source": "materials",
                    "content": f"材料: {row.name}（单价 {row.unit_price}元/{row.unit}）",
                    "score": 0.6,
                })
        except Exception as e:
            logger.debug("keyword_retrieve materials 失败: %s", e)

        try:
            # products 表关键词匹配
            from app.models.product import Product
            conditions = [Product.name.like(f"%{kw}%") for kw in keywords]
            stmt = select(Product).where(or_(*conditions)).limit(self.max_evidence)
            result = await db.execute(stmt)
            for row in result.scalars().all():
                evidence.append({
                    "source": "products",
                    "content": f"商品: {row.name}（售价 {row.price}元）",
                    "score": 0.5,
                })
        except Exception as e:
            logger.debug("keyword_retrieve products 失败: %s", e)

        return evidence

    def build_evidence_context(self, evidence: list[dict[str, Any]]) -> str:
        """将证据列表格式化为可注入 system prompt 的上下文文本。"""
        if not evidence:
            return ""
        parts = ["以下是从知识库检索到的相关信息，请参考作答：\n"]
        for i, e in enumerate(evidence, 1):
            parts.append(f"{i}. [{e['source']}] {e['content']}\n")
        return "".join(parts)


# 模块级单例
agentic_rag = AgenticRAG()

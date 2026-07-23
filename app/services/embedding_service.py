"""Embedding 服务 — AgenticRAG 真实向量检索支撑（v1.1.31 FP-3 修复）

替代 agentic_rag._retrieve_vector 中的 [0.0]*128 占位向量。
调用 OpenAI 兼容的 /v1/embeddings 端点，将 query 文本转向量后供向量库语义检索。

支持的后端（任选其一，通过 embedding_api_url + embedding_api_key 配置）：
- OpenAI text-embedding-3-small (1536 维)
- 智谱 embedding-3 (2048 维)
- BGE-M3 via DashScope (1024 维)
- 本地部署的任意 OpenAI 兼容 embedding 服务

受 settings.real_embedding_enabled flag 控制：
- True + 配齐 key → 真实 embedding
- False 或未配 key → 返回 None，调用方降级到关键词匹配
"""
from __future__ import annotations

import logging
from typing import Optional

try:
    import httpx
except ImportError:  # httpx 为可选依赖
    httpx = None  # type: ignore

from app.config import get_settings

logger = logging.getLogger(__name__)

# 嵌入结果缓存（query 文本 → 向量），进程内 LRU，避免相同 query 重复调用
_EMBED_CACHE: dict[str, list[float]] = {}
_EMBED_CACHE_MAX = 256


async def embed_query(text: str) -> Optional[list[float]]:
    """将文本转为 embedding 向量。

    Args:
        text: 待向量化的文本

    Returns:
        向量列表（维度由 settings.embedding_dim 决定），失败/禁用时返回 None
    """
    settings = get_settings()
    if not settings.real_embedding_enabled:
        logger.debug("embed_query: real_embedding_enabled=False，跳过真实 embedding")
        return None

    if not text or not text.strip():
        return None

    if httpx is None:
        logger.warning("embed_query: httpx 未安装，无法调用 embedding API")
        return None

    # 缓存命中
    cache_key = text.strip()[:200]
    if cache_key in _EMBED_CACHE:
        return _EMBED_CACHE[cache_key]

    # 解析 API 端点与密钥：优先 embedding 专用配置，复用 deepseek/qwen
    api_key = settings.embedding_api_key or settings.deepseek_api_key
    if not api_key:
        # deepseek 未配时尝试 qwen
        api_key = settings.qwen_api_key
    if not api_key:
        logger.warning("embed_query: 未配置 embedding_api_key / deepseek_api_key / qwen_api_key")
        return None

    api_url = settings.embedding_api_url
    if not api_url:
        # 默认复用 deepseek base（DeepSeek 暂不支持 embedding，则回退 qwen/dashscope）
        if settings.embedding_api_key:
            api_url = ""  # 必须显式配置
        else:
            api_url = settings.qwen_api_base.rstrip("/") + "/embeddings"
    if not api_url:
        logger.warning("embed_query: 未配置 embedding_api_url，无法调用")
        return None

    payload = {
        "model": settings.embedding_model,
        "input": text,
    }
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }

    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            resp = await client.post(api_url, json=payload, headers=headers)
            if resp.status_code != 200:
                logger.warning(
                    "embed_query: API non-200 status=%s body=%s",
                    resp.status_code, resp.text[:200],
                )
                return None
            data = resp.json()
            # OpenAI 兼容响应：{"data": [{"embedding": [...]}]}
            embeddings = data.get("data", [])
            if not embeddings:
                logger.warning("embed_query: 响应无 data 字段: %s", str(data)[:200])
                return None
            vector = embeddings[0].get("embedding", [])
            if not vector:
                return None

            # 维度校验（与配置不一致时告警但不阻断）
            if len(vector) != settings.embedding_dim:
                logger.warning(
                    "embed_query: 维度不匹配 expected=%s actual=%s，请检查 embedding_dim 配置",
                    settings.embedding_dim, len(vector),
                )

            # 写入缓存
            if len(_EMBED_CACHE) >= _EMBED_CACHE_MAX:
                _EMBED_CACHE.pop(next(iter(_EMBED_CACHE)))
            _EMBED_CACHE[cache_key] = vector
            return vector
    except Exception as e:
        logger.warning("embed_query: 调用失败 %s", e)
        return None


def clear_embed_cache() -> None:
    """清空 embedding 缓存（测试用）"""
    _EMBED_CACHE.clear()

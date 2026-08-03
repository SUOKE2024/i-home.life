"""F47 AI 装修问答/案例搜索服务层 — 知识库检索 + 引用来源 + 诚实降级

使用 knowledge/loader.py 的 KnowledgeLoader 单例：
- 向量搜索优先（配置 vector_db_url 时），关键词搜索降级
- 未命中时不编造内容，明确返回 no_match 与 honest_note（诚实降级）
"""

from typing import Any

from knowledge.loader import load_knowledge_base

ANSWER_SUFFIX = "以上答案基于内置装修知识库（含 GB 标准引用），供参考"
NO_MATCH_ANSWER = "未在内置知识库找到精确匹配，建议咨询专业设计师或联系客服"
HONEST_NOTE = "答案来自内置装修知识库（source: knowledge_base），未命中时不编造内容（诚实降级）"

FAQS_LIMIT = 20
SNIPPET_LENGTH = 120
TITLE_LENGTH = 40


def _entry_title(content: str, domain: str) -> str:
    """从知识正文生成标题（搜索结果不含 name 字段，取正文前缀）。"""
    text = content.strip()
    if not text:
        return domain
    return text[:TITLE_LENGTH] + ("…" if len(text) > TITLE_LENGTH else "")


async def search(query: str) -> dict[str, Any]:
    """知识库问答搜索：向量优先、关键词降级。

    Args:
        query: 用户问题（已由 API 层校验非空）

    Returns:
        {query, answer, sources, match_type, honest_note}
        - 命中: match_type="knowledge_base"，sources 取前 1-2 条含引用
        - 未命中: match_type="no_match"，sources=[]，不编造答案
    """
    kb = load_knowledge_base()
    results = await kb.search(query, max_results=5)

    if not results:
        return {
            "query": query,
            "answer": NO_MATCH_ANSWER,
            "sources": [],
            "match_type": "no_match",
            "honest_note": HONEST_NOTE,
        }

    top = results[:2]
    sources = [
        {
            "domain": entry.get("domain", ""),
            "title": _entry_title(entry.get("content", ""), entry.get("domain", "")),
            "citation": entry.get("citation", ""),
            "snippet": (entry.get("content", "") or "")[:SNIPPET_LENGTH],
        }
        for entry in top
    ]

    contents = [entry.get("content", "") for entry in top if entry.get("content")]
    answer = "\n".join(contents) + "\n" + ANSWER_SUFFIX

    return {
        "query": query,
        "answer": answer,
        "sources": sources,
        "match_type": "knowledge_base",
        "honest_note": HONEST_NOTE,
    }


def faq_topics() -> dict[str, Any]:
    """FAQ 话题列表（知识库 faq 域，截断前 20 条）。"""
    kb = load_knowledge_base()
    faqs = kb.load_domain("faq")
    topics = [
        {
            "id": entry.get("id", ""),
            "name": entry.get("name", "") or entry.get("question", ""),
            "content": entry.get("content", ""),
            "citation": entry.get("citation", ""),
        }
        for entry in faqs[:FAQS_LIMIT]
    ]
    return {
        "total": len(faqs),
        "topics": topics,
    }

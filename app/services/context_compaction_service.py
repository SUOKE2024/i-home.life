"""会话上下文压缩服务 — v1.15.5 语境工程落地

借鉴 2026 LangChain「Long-Horizon Agents 元年 / Context Engineering」前沿：
长会话历史全量注入会导致上下文膨胀（context rot）——时延 70-140s、成本与
注意力预算失控（对齐 v1.13.5 注入预算同一方法论，但作用于客户端 history）。

策略（chat_context_compaction_enabled 门控）：
  - history 长度 ≤ chat_context_max_turns：原样返回（无额外成本）
  - 超限：尾部保留最近 N 条消息（不丢关键上下文）+ 头部经 LLM 摘要为
    单条 system 消息注入；摘要失败回退纯截断（诚实降级，best-effort 不阻断）
  - 摘要走 BaseAgent fallback chain（不绕过 LLM 降级纪律），economy 档省成本

设计约束（对齐 CLAUDE.md）：
- feature flag 门控，默认 True；关闭即回退旧行为（全量透传）
- best-effort：摘要失败仅 log warning + 截断回退，不影响主流程
- 确定性可测：summarize_fn 可注入（测试用 mock，零 LLM 成本）
"""
from __future__ import annotations

import logging

from app.config import get_settings

logger = logging.getLogger(__name__)

# 摘要前缀（注入 system 消息，供前端/轨迹回放识别）
_SUMMARY_PREFIX = "[早前对话摘要] "


async def summarize_messages(messages: list[dict]) -> str:
    """LLM 摘要一段对话历史（内部 helper，供 compact_history 默认使用）。

    任何失败向上抛，由 compact_history 回退截断。
    """
    from app.agents.base import BaseAgent

    agent = BaseAgent()
    agent.agent_name = "context_compactor"
    agent.cost_tier = "economy"
    agent.system_prompt = (
        "你是会话摘要器。把对话压缩为 200 字以内的要点摘要（需求、约束、"
        "已达成的结论、待办事项），只返回摘要正文，不加任何前缀。"
    )
    try:
        history_text = "\n".join(
            f"{m.get('role')}: {str(m.get('content') or '')[:500]}" for m in messages
        )
        reply = await agent._chat([
            {"role": "system", "content": agent.system_prompt},
            {"role": "user", "content": f"请摘要以下对话：\n{history_text}"},
        ])
        return str(reply or "").strip()[:600]
    finally:
        await agent.close()


async def compact_history(
    history: list[dict] | None,
    *,
    max_turns: int | None = None,
    summarize_fn=None,
) -> list[dict]:
    """压缩客户端 history（/chat 与 /chat/stream 共用）。

    Args:
        history: 客户端消息列表 [{role, content}, ...]
        max_turns: 保留的尾部消息条数（None → 取 settings.chat_context_max_turns）
        summarize_fn: 可注入摘要函数（测试 mock）；None → summarize_messages

    Returns:
        压缩后的消息列表（未超限时原样返回；摘要失败回退尾部截断）
    """
    settings = get_settings()
    if not settings.chat_context_compaction_enabled:
        return list(history or [])
    if not history:
        return []

    threshold = max_turns if max_turns is not None else settings.chat_context_max_turns
    if len(history) <= threshold:
        return list(history)

    head, tail = history[:-threshold], history[-threshold:]
    try:
        fn = summarize_fn or summarize_messages
        summary = await fn(head)
        if not summary:
            raise ValueError("summary empty")
        logger.info(
            "context_compaction: 压缩 %d 条历史 → 摘要 %d 字 + 保留 %d 条",
            len(head), len(summary), len(tail),
        )
        return [{"role": "system", "content": f"{_SUMMARY_PREFIX}{summary}"}] + list(tail)
    except Exception as e:
        logger.warning(
            "context_compaction: 摘要失败（回退纯截断，保留尾部 %d 条）: %s",
            len(tail), e,
        )
        return list(tail)

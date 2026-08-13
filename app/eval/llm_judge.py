"""LLM-as-judge 语义正确性评估（v1.13.6，对齐 2026 LLM-as-judge Eval 前沿）

2026 Agent 评估前沿（AI VOID 12-metric / MLflow 2026）：启发式关键词代理无法衡量
「回答对不对」，需引入 LLM-as-judge 对输出做语义评分。本模块对
faithfulness/completeness/sufficiency 三要素做 0-1 语义评分：
- faithfulness（忠实性）：回复是否有据可依、不幻觉
- completeness（完整性）：是否覆盖任务全部组成部分
- sufficiency（充分性）：是否恰如其分（不过度/不遗漏）

设计原则：
- 抽样执行（成本控制），受 settings.llm_judge_enabled 门控（默认关闭）
- 诚实标注：LLM judge 非确定性，仅作抽样金标准对比，不替代确定性关键词基线
- 复用 BaseAgent._chat（多 LLM fallback chain），不绕过 fallback
"""

from __future__ import annotations

import json
import logging
import random

from app.config import get_settings

settings = get_settings()
logger = logging.getLogger(__name__)

# 三要素 → 语义评分 rubric（供 LLM judge prompt；与 IHomeEvalDimension 三要素对齐）
LLM_JUDGE_DIMENSIONS: dict[str, str] = {
    "faithfulness": "回复是否有据可依、无幻觉（引用来源/依据，不编造事实）",
    "completeness": "回复是否覆盖任务全部组成部分（无遗漏关键子任务）",
    "sufficiency": "回复是否恰如其分（不过度冗长、不遗漏关键信息）",
}

_JUDGE_SYSTEM_PROMPT = (
    "你是一个家居装修领域 Agent 回复质量评估器。根据用户问题与 Agent 回复，"
    "对以下三个维度打分（0-5 整数分，5 最好）：\n"
    "- faithfulness（忠实性）：{faithfulness}\n"
    "- completeness（完整性）：{completeness}\n"
    "- sufficiency（充分性）：{sufficiency}\n\n"
    "只返回 JSON 对象（形如 "
    '{{"faithfulness": 5, "completeness": 4, "sufficiency": 4}}），'
    "不要输出任何其他内容。"
).format(**LLM_JUDGE_DIMENSIONS)


class _JudgeAgent:
    """LLM 语义评分器（抽样评估专用，非生产路径）。

    复用 BaseAgent._chat（多 LLM fallback chain），system_prompt 限定为
    质量评分；成本受 llm_judge_enabled 门控（默认关闭）。
    """

    def __init__(self) -> None:
        from app.agents.base import BaseAgent

        self._agent = BaseAgent()
        self._agent.agent_name = "llm_judge_eval"
        self._agent.system_prompt = _JUDGE_SYSTEM_PROMPT

    async def chat(self, prompt: str, reply: str) -> str:
        result = await self._agent._chat([
            {"role": "user", "content": f"用户问题：{prompt}\n\nAgent 回复：{reply}"},
        ])
        # _chat 契约允许返回 dict（工具调用路径）；评分场景强制 str
        return result if isinstance(result, str) else str(result)

    async def close(self) -> None:
        await self._agent.close()


def _parse_judge_reply(raw: str) -> dict[str, float]:
    """解析 LLM judge 回复 → 0-1 分数（0-5 归一化）。解析失败返回 0.0。"""
    text = (raw or "").strip()
    data: dict = {}
    try:
        start = text.find("{")
        end = text.rfind("}")
        if start != -1 and end != -1 and end > start:
            data = json.loads(text[start:end + 1])
        else:
            data = json.loads(text)
    except (json.JSONDecodeError, TypeError):
        return {d: 0.0 for d in LLM_JUDGE_DIMENSIONS}
    scores: dict[str, float] = {}
    for dim in LLM_JUDGE_DIMENSIONS:
        try:
            scores[dim] = round(
                max(0.0, min(5.0, float(data.get(dim, 0)))) / 5.0, 4,
            )
        except (TypeError, ValueError):
            scores[dim] = 0.0
    return scores


async def judge_reply(
    prompt: str, reply: str, agent: _JudgeAgent | None = None,
) -> dict[str, float]:
    """对单条 Agent 回复做 LLM 语义评分（三要素 0-1）。

    Args:
        prompt: 用户问题原文
        reply: Agent 回复原文
        agent: 可注入的 _JudgeAgent（测试用 mock）

    Returns:
        {"faithfulness": 0-1, "completeness": 0-1, "sufficiency": 0-1}

    诚实标注：LLM 评分非确定性、有成本，仅用于抽样金标准对比。
    """
    own = False
    if agent is None:
        agent = _JudgeAgent()
        own = True
    try:
        raw = await agent.chat(prompt, reply)
        return _parse_judge_reply(raw)
    finally:
        if own:
            await agent.close()


# 三要素 → 关键词基线（与 IHomeEvalRunner._compute_dimension_scores 对齐）
_KEYWORD_BASELINE: dict[str, tuple[str, ...]] = {
    "faithfulness": ("来源", "根据", "依据", "参考", "标注", "数据来源"),
    "completeness": ("总结", "综上", "第1", "第一", "最后", "1.", "2.", "3."),
}


def _keyword_baseline_score(dim: str, reply: str) -> float:
    """确定性关键词基线（0/1），用于与 LLM judge 对比；sufficiency 用长度代理。"""
    if dim == "sufficiency":
        return 1.0 if 40 <= len(reply or "") <= 2000 else 0.0
    keywords = _KEYWORD_BASELINE.get(dim, ())
    return 1.0 if any(k in (reply or "") for k in keywords) else 0.0


async def evaluate_llm_judge(
    samples: list[dict] | None = None,
    sample_size: int = 12,
    random_seed: int | None = None,
    judge=None,
) -> dict:
    """LLM-as-judge 语义正确性抽样评估（v1.13.6）。

    对给定样本（[{prompt, reply}]）抽样并逐条 LLM 评分，聚合三要素均值，
    与确定性关键词基线并列对比。

    Args:
        samples: [{prompt, reply}]；None 时为空（诚实返回 0 样本）
        sample_size: 抽样条数（LLM 调用成本 = sample_size 次）
        random_seed: 抽样随机种子（可复现；None 每次不同）
        judge: 可注入的异步评分器 f(prompt, reply) -> dict（测试用）

    Returns:
        {report_type, sample_size, dimensions: {dim: {llm_judge, keyword_baseline}},
         notes}
    """
    pool = list(samples or [])
    if random_seed is not None:
        random.seed(random_seed)
    if len(pool) > sample_size:
        pool = random.sample(pool, sample_size)

    judge = judge or judge_reply
    per_dim_llm: dict[str, list[float]] = {d: [] for d in LLM_JUDGE_DIMENSIONS}
    per_dim_kw: dict[str, list[float]] = {d: [] for d in LLM_JUDGE_DIMENSIONS}

    for s in pool:
        prompt = s.get("prompt", "")
        reply = s.get("reply", "")
        scores = await judge(prompt, reply)
        for dim in LLM_JUDGE_DIMENSIONS:
            per_dim_llm[dim].append(float(scores.get(dim, 0.0)))
            per_dim_kw[dim].append(_keyword_baseline_score(dim, reply))

    def _avg(vals: list[float]) -> float:
        return round(sum(vals) / len(vals), 4) if vals else 0.0

    return {
        "report_type": "llm_judge_semantic_quality",
        "sample_size": len(pool),
        "dimensions": {
            d: {
                "llm_judge": _avg(per_dim_llm[d]),
                "keyword_baseline": _avg(per_dim_kw[d]),
            } for d in LLM_JUDGE_DIMENSIONS
        },
        "notes": [
            "LLM-as-judge 语义评分（非确定性、有成本），抽样金标准对比",
            "keyword_baseline 为确定性关键词代理（0/1），二者并列非互替",
            "受 llm_judge_enabled 门控（默认关闭）；样本不足时诚实标注 0 样本",
        ],
    }

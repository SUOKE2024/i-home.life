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

    def __init__(self, system_prompt: str | None = None) -> None:
        from app.agents.base import BaseAgent

        self._agent = BaseAgent()
        self._agent.agent_name = "llm_judge_eval"
        self._agent.system_prompt = system_prompt or _JUDGE_SYSTEM_PROMPT

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


async def judge_reply_pass_k(
    prompt: str, reply: str, k: int = 3, judge=None,
) -> dict:
    """pass^k 一致性评分（v1.13.7，对齐 2026 LLM-as-judge 控噪前沿）。

    同题跑 k 次 LLM judge，取均值作为最终分，agreement 度量 k 次的一致性
    （各维归一化分极差 ≤0.2 视为一致，对应 0-5 分差 ≤1 分）。k=1 退化为单次
    judge（旧行为）。k 越大噪声越低但成本 k 倍。

    Args:
        judge: 可注入的异步评分器 f(prompt, reply) -> dict（测试用），
               None 时默认 judge_reply。

    Returns:
        {"scores": {dim: 0-1}, "agreement": 0-1, "k": k, "runs": [...]}
    """
    judge = judge or judge_reply
    if k <= 1:
        scores = await judge(prompt, reply)
        return {"scores": scores, "agreement": 1.0, "k": 1, "runs": [scores]}

    runs = [await judge(prompt, reply) for _ in range(k)]
    agg: dict[str, float] = {}
    agreed_dims = 0
    for dim in LLM_JUDGE_DIMENSIONS:
        vals = [r.get(dim, 0.0) for r in runs]
        agg[dim] = round(sum(vals) / len(vals), 4)
        if max(vals) - min(vals) <= 0.2:
            agreed_dims += 1
    return {
        "scores": agg,
        "agreement": round(agreed_dims / len(LLM_JUDGE_DIMENSIONS), 4),
        "k": k,
        "runs": runs,
    }


# 人类标注金标样本（v1.13.7）：用于校准 LLM judge 与人类判断的对齐度。
# 样本选取语义明确、答案无歧义的典型问答，gold 为 0-1 分（与 judge 归一化对齐）。
LLM_JUDGE_GOLD_DATASET: list[dict] = [
    {
        "prompt": "120 平北欧风全屋装修，帮我做个预算",
        "reply": (
            "根据市场均价，您的全屋装修预算约为 20 万（含税、含 3% 质保金）。\n"
            "1. 水电改造：3 万\n2. 墙面工程：2 万\n3. 地面工程：3 万\n"
            "总结：以上为估算，具体以报价单为准。"
        ),
        "gold": {"faithfulness": 1.0, "completeness": 1.0, "sufficiency": 1.0},
    },
    {
        "prompt": "帮我设计一个厨房布局",
        "reply": "好的。",
        "gold": {"faithfulness": 0.0, "completeness": 0.0, "sufficiency": 0.0},
    },
    {
        "prompt": "客厅用什么地板环保？",
        "reply": (
            "建议选 E0 级环保地板，实木复合或强化地板均可。\n"
            "注意事项：E0 级甲醛释放量 ≤0.5mg/L，需认准检测报告。"
        ),
        "gold": {"faithfulness": 1.0, "completeness": 1.0, "sufficiency": 1.0},
    },
]


async def evaluate_judge_alignment(
    judge=None, gold_dataset: list[dict] | None = None,
) -> dict:
    """LLM judge 与人类标注金标的对齐度（v1.13.7）。

    度量 judge 对金标样本的评分与人类标注的偏差：MAE（平均绝对误差，0-1）越低、
    agreement_rate（容差 0.2 内一致占比）越高，说明 judge 与人类判断越对齐。
    诚实标注：金标为少量人工样本，非全量权威基准；judge 非确定性，仅抽样校准用。

    Returns:
        {"available", "sample_size", "mae_per_dimension", "overall_mae",
         "agreement_rate", "notes"}
    """
    gold = gold_dataset if gold_dataset is not None else LLM_JUDGE_GOLD_DATASET
    if not gold:
        return {"available": False, "reason": "无金标数据", "sample_size": 0}

    judge = judge or judge_reply
    per_dim_err: dict[str, list[float]] = {d: [] for d in LLM_JUDGE_DIMENSIONS}
    agreed = 0
    total = 0
    for item in gold:
        scores = await judge(item["prompt"], item["reply"])
        g = item["gold"]
        for dim in LLM_JUDGE_DIMENSIONS:
            err = abs(float(scores.get(dim, 0.0)) - float(g.get(dim, 0.0)))
            per_dim_err[dim].append(err)
            total += 1
            if err <= 0.2:
                agreed += 1

    mae = {
        d: round(sum(errs) / len(errs), 4)
        for d, errs in per_dim_err.items() if errs
    }
    overall_mae = round(
        sum(sum(errs) for errs in per_dim_err.values()) / max(total, 1), 4,
    )
    return {
        "available": True,
        "sample_size": len(gold),
        "mae_per_dimension": mae,
        "overall_mae": overall_mae,
        "agreement_rate": round(agreed / max(total, 1), 4),
        "notes": [
            "容差 0.2（0-1 分）判定一致；MAE 越低 judge 与人类标注越对齐",
            "金标为少量人工样本，非全量权威基准；judge 非确定性，仅抽样校准",
        ],
    }


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
    pass_k: int | None = None,
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
    k = pass_k if pass_k is not None else 1  # 默认单次（旧行为），API 层按 config 传 k
    per_dim_llm: dict[str, list[float]] = {d: [] for d in LLM_JUDGE_DIMENSIONS}
    per_dim_kw: dict[str, list[float]] = {d: [] for d in LLM_JUDGE_DIMENSIONS}
    agreements: list[float] = []

    for s in pool:
        prompt = s.get("prompt", "")
        reply = s.get("reply", "")
        if k > 1:
            result = await judge_reply_pass_k(prompt, reply, k=k, judge=judge)
            scores = result["scores"]
            agreements.append(result["agreement"])
        else:
            scores = await judge(prompt, reply)
        for dim in LLM_JUDGE_DIMENSIONS:
            per_dim_llm[dim].append(float(scores.get(dim, 0.0)))
            per_dim_kw[dim].append(_keyword_baseline_score(dim, reply))

    def _avg(vals: list[float]) -> float:
        return round(sum(vals) / len(vals), 4) if vals else 0.0

    agreement = round(sum(agreements) / len(agreements), 4) if agreements else 1.0
    notes = [
        "LLM-as-judge 语义评分（非确定性、有成本），抽样金标准对比",
        "keyword_baseline 为确定性关键词代理（0/1），二者并列非互替",
        "受 llm_judge_enabled 门控（默认关闭）；样本不足时诚实标注 0 样本",
    ]
    if k > 1:
        notes.append(
            f"pass^k={k} 控噪：同题跑 k 次取均值，agreement 为各维一致性占比（0-1，越高越稳定）"
        )
    return {
        "report_type": "llm_judge_semantic_quality",
        "sample_size": len(pool),
        "pass_k": k,
        "agreement": agreement,
        "dimensions": {
            d: {
                "llm_judge": _avg(per_dim_llm[d]),
                "keyword_baseline": _avg(per_dim_kw[d]),
            } for d in LLM_JUDGE_DIMENSIONS
        },
        "notes": notes,
    }


# ════════════════════════════════════════════════════════════════
# 终端任务成功率评测（v1.15.8，P2-4：ITBench-AA 式用户目标达成率）
# ════════════════════════════════════════════════════════════════

# 任务达成判定 prompt（独立于三要素评分）：判定回复是否达成用户目标
_TASK_SUCCESS_SYSTEM_PROMPT = (
    "你是一个 Agent 任务完成度评估器。根据用户问题与 Agent 回复，判定 Agent "
    "是否成功达成了用户的请求目标。注意：回复明确指出无法完成、仅给出占位/"
    "降级说明（未提供任何实际结果）的视为未达成。\n"
    '只返回 JSON 对象（形如 {"task_success": 1}），其中 task_success 为整数 '
    "0（未达成）或 1（达成），不要输出任何其他内容。"
)


def _parse_task_success_reply(raw: str) -> int | None:
    """解析任务达成判定回复 → 0/1；解析失败返回 None（诚实标注 unknown）。"""
    text = (raw or "").strip()
    try:
        start = text.find("{")
        end = text.rfind("}")
        if start != -1 and end != -1 and end > start:
            data = json.loads(text[start:end + 1])
        else:
            data = json.loads(text)
        val = int(data.get("task_success", -1))
        return val if val in (0, 1) else None
    except (json.JSONDecodeError, TypeError, ValueError):
        return None


async def judge_task_success(
    prompt: str, reply: str, agent: _JudgeAgent | None = None,
) -> dict:
    """LLM 判定单条回复是否达成用户目标（0/1，解析失败 → success=None）。

    Args:
        agent: 可注入的 _JudgeAgent（测试用 mock；system_prompt 复用达成判定）

    Returns:
        {"success": bool | None}——None 表示 LLM 输出解析失败（unknown）
    """
    own = False
    if agent is None:
        agent = _JudgeAgent(system_prompt=_TASK_SUCCESS_SYSTEM_PROMPT)
        own = True
    try:
        raw = await agent.chat(prompt, reply)
        parsed = _parse_task_success_reply(raw)
        return {"success": bool(parsed) if parsed is not None else None}
    finally:
        if own:
            await agent.close()


async def evaluate_task_success_rate(
    samples: list[dict] | None = None,
    sample_size: int = 12,
    random_seed: int | None = None,
    judge=None,
) -> dict:
    """终端任务成功率抽样评估（v1.15.8 P2-4，ITBench-AA 式用户目标达成率）。

    对样本（[{prompt, reply}]）逐条用 LLM 判定「用户目标是否达成」，
    聚合达成率。unknown（LLM 输出解析失败）不计入达成率分母，诚实标注。

    Args:
        samples: [{prompt, reply}]；None 时为空（诚实返回 0 样本）
        sample_size: 抽样条数（LLM 调用成本 = sample_size 次）
        random_seed: 抽样随机种子（可复现；None 每次不同）
        judge: 可注入的异步判定器 f(prompt, reply) -> {"success": bool|None}

    Returns:
        {report_type, sample_size, success_count, failure_count, unknown_count,
         success_rate, notes}
    """
    pool = list(samples or [])
    if random_seed is not None:
        random.seed(random_seed)
    if len(pool) > sample_size:
        pool = random.sample(pool, sample_size)

    judge = judge or judge_task_success
    success = failure = unknown = 0
    for s in pool:
        result = await judge(s.get("prompt", ""), s.get("reply", ""))
        if result.get("success") is None:
            unknown += 1
        elif result["success"]:
            success += 1
        else:
            failure += 1

    judged = success + failure
    return {
        "report_type": "llm_judge_task_success_rate",
        "sample_size": len(pool),
        "success_count": success,
        "failure_count": failure,
        "unknown_count": unknown,
        "success_rate": round(success / judged, 4) if judged else 0.0,
        "notes": [
            "ITBench-AA 式「用户目标达成率」：LLM 判定回复是否达成用户目标（抽样金标准，非确定性、有成本）",
            "unknown 为 LLM 输出解析失败样本，不计入达成率分母（诚实标注）",
            "受 llm_judge_enabled 门控（默认关闭）；样本不足时诚实标注 0 样本",
        ],
    }

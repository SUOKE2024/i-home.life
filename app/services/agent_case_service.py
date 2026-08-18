"""Agent Case 提取与检索服务 — 自进化管线的经验沉淀层

借鉴 EverMind EverOS Agent Memory（2026-04 公测）：
  Agent 执行轨迹 → 压缩去噪 → 判定是否目标导向 → LLM 提取为 Case
  → 持久化（task_intent + approach + quality_score）→ 未来 Agent 检索复用

核心流程（extract_case_from_trace）：
  1. 从 AgentTrace（harness.py 运行时 dataclass）取 user_message + response + tool_calls
  2. 压缩长轨迹（>2000 字符启发式截断 + 关键步骤保留）
  3. 过滤非目标导向对话（闲聊/简单 Q&A 不入 Case）
  4. LLM 提取 task_intent（自包含意图陈述）/ approach（分步压缩）/ quality_score / outcome
  5. 持久化为 AgentCase

检索流程（search_cases）：
  按 task_intent 语义相似度 + scope 隔离检索同类 Case，供 Agent 执行前注入。

设计约束（对齐 CLAUDE.md）：
- feature flag agent_case_extraction_enabled 门控（默认 False，诚实降级）
- best-effort：提取失败仅 log debug，不影响主流程（harness.run 已捕获）
- user_id 强隔离（scope=personal 必须传 owner_id）
- 不引入外部记忆服务（模块化单体红线）
- LLM 调用走 BaseAgent._chat fallback chain（不绕过多 LLM 降级）
"""
from __future__ import annotations

import json
import logging
import uuid
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import select, desc, and_
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.models.agent_case import AgentCase

logger = logging.getLogger(__name__)

# 非目标导向对话的过滤关键词（不入 Case）
_NON_GOAL_DIRECTED_PATTERNS = (
    "你好", "hello", "hi", "谢谢", "thanks", "再见", "bye",
    "你是谁", "who are you", "能做什么", "what can you do",
)

# 长轨迹压缩阈值（字符数）
_COMPRESS_THRESHOLD = 2000

# v1.13.5: token 估算换算系数（len//2——中文≈1字/token 与英文≈4字符/token 的中间值）
TOKEN_ESTIMATE_DIVISOR = 2

# v1.15.5 失败学习：失败轨迹确定性分类（借鉴 EdgeBench——失败是最贵的学习信号，
# ITBench-AA 显示 agentic 任务失败率 >50%，失败样本比成功样本更稀缺更有价值）
_FAILURE_STATUSES = ("failed", "fallback")
_FAILURE_TYPE_TIMEOUT = "timeout"
_FAILURE_TYPE_EMPTY_REPLY = "empty_reply"
_FAILURE_TYPE_FALLBACK = "fallback"
_FAILURE_TYPE_LLM_ERROR = "llm_error"
_FAILURE_TYPE_TOOL_LOOP = "tool_loop"
_FAILURE_TYPE_UNKNOWN = "unknown"

# 失败信号特征词 → failure_type（确定性，无 LLM 成本）
_TIMEOUT_HINTS = ("timeout", "超时", "asyncio.TimeoutError", "all_retries_exhausted")
_EMPTY_REPLY_HINTS = ("empty", "空回复", "no content", "finish=tool_calls")
_TOOL_LOOP_HINTS = ("tool_loop", "max_tool", "token_budget_hit", "工具循环")


def _classify_failure_type(trace_dict: dict) -> str:
    """确定性失败分类（无 LLM 成本）→ failure_type。

    信号优先级：timeout > tool_loop > empty_reply(显式空回复信号) > fallback(状态)
    > llm_error(有错误信息) > unknown（仅有 failed 状态、无任何诊断信息）。
    （借鉴 HarnessBank「诊断-归因分离」：以病理为键而非任务为键，抗过拟合）
    """
    status = str(trace_dict.get("status") or "")
    fallback_reason = str(trace_dict.get("fallback_reason") or "")
    error_type = str(trace_dict.get("error_type") or "")
    error_message = str(trace_dict.get("error_message") or "")
    blob = f"{fallback_reason}|{error_type}|{error_message}|{status}".lower()
    if any(h in blob for h in _TIMEOUT_HINTS):
        return _FAILURE_TYPE_TIMEOUT
    if any(h in blob for h in _TOOL_LOOP_HINTS):
        return _FAILURE_TYPE_TOOL_LOOP
    if any(h in blob for h in _EMPTY_REPLY_HINTS):
        return _FAILURE_TYPE_EMPTY_REPLY
    if status == "fallback":
        return _FAILURE_TYPE_FALLBACK
    if error_type or error_message:
        return _FAILURE_TYPE_LLM_ERROR
    return _FAILURE_TYPE_UNKNOWN


async def extract_failure_case_from_trace(
    trace_dict: dict,
    db: AsyncSession,
    *,
    owner_id: str,
    scope: str = "personal",
    created_by: str = "",
) -> AgentCase | None:
    """v1.15.5 失败学习：从失败轨迹确定性提取失败 Case（零 LLM 成本）。

    此前 extract_case_from_trace 只走 LLM 成功路径，失败轨迹（harness FAILED/
    FALLBACK）完全不沉淀——失败信号被丢弃（CLAUDE.md「只记成功不记失败」遗留
    的 Case 层对应物）。本函数：

      - 判定：trace status ∈ (failed, fallback) 或 error_message 非空
      - 分类：_classify_failure_type 确定性病理分类（timeout/empty_reply/fallback/…）
      - 持久化：outcome="failed" + quality_score=0.0 + failure_type + approach 失败记录
      - 防双提取：同 trace_id 已沉淀则跳过

    失败 Case 供 run_skill_evolution_cycle 按 (agent_name, failure_type) 聚类
    蒸馏「反模式 Skill」（避免重复错误），受 agent_failure_learning_enabled 门控。
    """
    settings = get_settings()
    if not settings.agent_failure_learning_enabled:
        return None

    status = str(trace_dict.get("status") or "")
    if status not in _FAILURE_STATUSES and not trace_dict.get("error_message"):
        logger.debug("extract_failure_case: 非失败轨迹（status=%s），跳过", status)
        return None

    trace_id = trace_dict.get("trace_id")
    if trace_id:
        existing = await db.execute(
            select(AgentCase.id).where(AgentCase.trace_id == trace_id).limit(1)
        )
        if existing.scalar_one_or_none():
            logger.debug("extract_failure_case: trace_id=%s 已提取过，跳过", trace_id)
            return None

    failure_type = _classify_failure_type(trace_dict)
    user_message = trace_dict.get("user_message_truncated") or trace_dict.get("user_message", "") or "(无用户消息)"
    fallback_reason = trace_dict.get("fallback_reason") or trace_dict.get("error_message") or failure_type
    approach = json.dumps(
        [{
            "step": 1,
            "attempted": user_message[:300],
            "tool": "harness",
            "result": f"{failure_type}: {fallback_reason}"[:500],
            "revised": False,
        }],
        ensure_ascii=False,
    )

    agent_case = AgentCase(
        id=str(uuid.uuid4()),
        scope=scope,
        owner_id=owner_id,
        agent_name=trace_dict.get("agent_name", "base"),
        session_id=None,
        trace_id=trace_id,
        task_intent=user_message[:200],
        approach=approach,
        outcome="failed",
        quality_score=0.0,
        failure_type=failure_type,
        created_by=created_by or owner_id,
    )
    db.add(agent_case)
    await db.flush()
    logger.info(
        "extract_failure_case: 已沉淀失败 Case %s (agent=%s, failure_type=%s)",
        agent_case.id, agent_case.agent_name, failure_type,
    )
    return agent_case


def _is_goal_directed(user_message: str) -> bool:
    """判定是否目标导向对话（闲聊/简单 Q&A 不入 Case）。

    启发式：消息过短或命中闲聊模式则判定为非目标导向。
    """
    stripped = user_message.strip()
    if len(stripped) < 8:
        return False
    lower = stripped.lower()
    for pattern in _NON_GOAL_DIRECTED_PATTERNS:
        if pattern in lower:
            return False
    return True


def _compress_trajectory(trace_dict: dict) -> str:
    """压缩 AgentTrace 为 LLM 可处理的轨迹摘要。

    策略（借鉴 EverOS pre-compression）：heuristic 截断 + 关键步骤保留。
    保留：user_message（截断 500 字）+ tool_calls 摘要 + response（截断 800 字）。
    """
    parts: list[str] = []
    user_msg = trace_dict.get("user_message_truncated") or trace_dict.get("user_message", "")
    if user_msg:
        parts.append(f"[用户请求] {user_msg[:500]}")

    tool_calls = trace_dict.get("tool_calls", [])
    if tool_calls and isinstance(tool_calls, list):
        tc_summary = []
        for tc in tool_calls[:10]:  # 最多保留 10 个工具调用
            if isinstance(tc, dict):
                name = tc.get("name", tc.get("function", {}).get("name", ""))
            else:
                name = str(tc)
            tc_summary.append(f"  - {name}")
        parts.append("[工具调用]\n" + "\n".join(tc_summary))

    response = trace_dict.get("response_truncated") or trace_dict.get("response", "")
    if response:
        parts.append(f"[Agent回复] {response[:800]}")

    compressed = "\n".join(parts)
    if len(compressed) > _COMPRESS_THRESHOLD:
        compressed = compressed[:_COMPRESS_THRESHOLD] + "...[已截断]"
    return compressed


_CASE_EXTRACTION_PROMPT = """你是 Agent 经验提取器。从以下 Agent 执行轨迹中提取结构化 Case。

执行轨迹：
{trajectory}

请提取并返回严格 JSON（不要 markdown 代码块）：
{{
  "task_intent": "自包含的任务意图陈述（50-200字，描述 Agent 试图完成什么，不含代词）",
  "approach": [
    {{"step": 1, "attempted": "尝试了什么", "tool": "用了什么工具或推理", "result": "结果", "revised": false}}
  ],
  "outcome": "success|partial|failed|unknown",
  "quality_score": 0.0到1.0的浮点数（任务完成质量自评）
}}

规则：
- task_intent 必须自包含（不依赖上下文也能理解），它是未来检索的键
- approach 只记录关键步骤（最多 8 步），失败重试也要记录
- quality_score: 成功完成=0.8-1.0, 部分完成=0.4-0.7, 失败=0.0-0.3
"""


async def extract_case_from_trace(
    trace: Any,
    db: AsyncSession,
    *,
    owner_id: str,
    scope: str = "personal",
    created_by: str = "",
) -> AgentCase | None:
    """从 AgentTrace 提取 Case 并持久化。

    Args:
        trace: harness.AgentTrace dataclass（或 to_dict() 后的 dict）
        db: 异步数据库会话
        owner_id: 归属 ID（personal→user_id）
        scope: 作用域（personal/project/team/org）
        created_by: 创建者 user_id

    Returns:
        AgentCase 或 None（过滤掉/提取失败/flag 关闭）
    """
    settings = get_settings()
    if not settings.agent_case_extraction_enabled:
        return None

    # 统一为 dict
    if hasattr(trace, "to_dict"):
        trace_dict = trace.to_dict()
    elif isinstance(trace, dict):
        trace_dict = trace
    else:
        logger.debug("extract_case: trace 类型不支持（%s），跳过", type(trace))
        return None

    user_message = trace_dict.get("user_message_truncated") or trace_dict.get("user_message", "")
    if not _is_goal_directed(user_message):
        logger.debug("extract_case: 非目标导向对话，跳过")
        return None

    # v1.15.5 失败学习：失败轨迹走确定性失败提取（零 LLM 成本、病理分类、
    # 聚类蒸馏反模式），成功轨迹走 LLM 结构化提取
    status = str(trace_dict.get("status") or "")
    if status in _FAILURE_STATUSES or trace_dict.get("error_message"):
        return await extract_failure_case_from_trace(
            trace_dict, db, owner_id=owner_id, scope=scope, created_by=created_by,
        )

    # 压缩轨迹
    trajectory = _compress_trajectory(trace_dict)

    # v1.10.x 防双提取：同一 trace_id 已沉淀过 Case 则跳过（如 harness.run 与
    # BaseAgent 内建 hook 边界异常时，避免同一次执行沉淀两条 Case）
    trace_id = trace_dict.get("trace_id")
    if trace_id:
        existing = await db.execute(
            select(AgentCase.id).where(AgentCase.trace_id == trace_id).limit(1)
        )
        if existing.scalar_one_or_none():
            logger.debug("extract_case: trace_id=%s 已提取过，跳过", trace_id)
            return None

    # LLM 提取 Case 结构
    case_data = await _llm_extract_case(trajectory, trace_dict.get("agent_name", "unknown"))
    if case_data is None:
        logger.debug("extract_case: LLM 提取失败，跳过")
        return None

    # 持久化
    agent_case = AgentCase(
        id=str(uuid.uuid4()),
        scope=scope,
        owner_id=owner_id,
        agent_name=trace_dict.get("agent_name", "base"),
        session_id=None,  # trace_dict 不含 session_id，由调用方补充
        trace_id=trace_dict.get("trace_id"),
        task_intent=case_data.get("task_intent", user_message[:200]),
        approach=json.dumps(case_data.get("approach", []), ensure_ascii=False),
        outcome=case_data.get("outcome", "unknown"),
        quality_score=float(case_data.get("quality_score", 0.0)),
        created_by=created_by or owner_id,
    )
    db.add(agent_case)
    await db.flush()
    logger.info(
        "extract_case: 已沉淀 Case %s (agent=%s, quality=%.2f)",
        agent_case.id, agent_case.agent_name, agent_case.quality_score,
    )
    return agent_case


async def _llm_extract_case(trajectory: str, agent_name: str) -> dict | None:
    """调用 LLM 从轨迹提取 Case 结构（走 BaseAgent fallback chain）。

    best-effort：任何失败返回 None，不影响主流程。
    """
    prompt = _CASE_EXTRACTION_PROMPT.format(trajectory=trajectory)
    messages = [
        {"role": "system", "content": "你是 Agent 经验提取器，只返回严格 JSON。"},
        {"role": "user", "content": prompt},
    ]
    try:
        from app.agents.base import BaseAgent

        agent = BaseAgent()
        agent.agent_name = "case_extractor"
        agent.system_prompt = "你是 Agent 经验提取器，只返回严格 JSON。"
        reply = await agent._chat(messages)
        await agent.close()
    except Exception as e:
        logger.debug("_llm_extract_case: LLM 调用失败: %s", e)
        return None

    return _parse_case_json(reply)


def _parse_case_json(reply: str) -> dict | None:
    """安全解析 LLM 返回的 Case JSON。"""
    if not reply or not isinstance(reply, str):
        return None
    # 去除可能的 markdown 代码块包裹
    text = reply.strip()
    if text.startswith("```"):
        lines = text.split("\n")
        lines = [ln for ln in lines if not ln.strip().startswith("```")]
        text = "\n".join(lines)
    try:
        data = json.loads(text)
    except (json.JSONDecodeError, TypeError):
        # 尝试提取第一个 JSON 对象
        start = text.find("{")
        end = text.rfind("}")
        if start >= 0 and end > start:
            try:
                data = json.loads(text[start : end + 1])
            except (json.JSONDecodeError, TypeError):
                return None
        else:
            return None

    if not isinstance(data, dict) or "task_intent" not in data:
        return None
    # 校验 quality_score 范围
    try:
        qs = float(data.get("quality_score", 0.0))
        data["quality_score"] = max(0.0, min(1.0, qs))
    except (TypeError, ValueError):
        data["quality_score"] = 0.0
    # 校验 outcome 枚举
    if data.get("outcome") not in ("success", "partial", "failed", "unknown"):
        data["outcome"] = "unknown"
    return data


async def search_cases(
    db: AsyncSession,
    *,
    task_intent: str,
    owner_id: str,
    scope: str = "personal",
    limit: int = 5,
    min_quality: float = 0.3,
) -> list[AgentCase]:
    """检索同类 Case（供 Agent 执行前注入）。

    策略：按 quality_score 降序 + retrieval_count 加权，取 top-N。
    （语义检索需 vector_db；未配置时降级为关键词 LIKE 匹配，诚实降级。）
    """
    settings = get_settings()
    if not settings.agent_skill_distillation_enabled:
        return []

    # 空 task_intent 不检索（避免无关键词过滤时返回全量 Case）
    if not task_intent or not task_intent.strip():
        return []

    # 作用域隔离查询
    conditions = [
        AgentCase.scope == scope,
        AgentCase.owner_id == owner_id,
        AgentCase.deleted_at.is_(None),
        AgentCase.quality_score >= min_quality,
        AgentCase.distilled_to_skill_id.is_(None),  # 未被蒸馏的原始 Case
    ]

    # 关键词匹配（task_intent LIKE）—— 向量库未配置时的诚实降级
    keywords = [w for w in task_intent.split() if len(w) > 1][:3]
    if keywords:
        keyword_conditions = [AgentCase.task_intent.ilike(f"%{kw}%") for kw in keywords]
        conditions.append(and_(*keyword_conditions) if len(keyword_conditions) > 1 else keyword_conditions[0])

    stmt = (
        select(AgentCase)
        .where(and_(*conditions))
        # v1.10.x 时间感知：quality/热度相同时，近期经验优先（recency 排序键，
        # 避免陈旧高分 Case 永久压制新沉淀的经验）
        .order_by(
            desc(AgentCase.quality_score),
            desc(AgentCase.retrieval_count),
            desc(AgentCase.created_at),
        )
        # v1.15.7 时间衰减：取 limit×4 候选池供 Python 侧衰减重排
        # （SQL 无法表达指数衰减；候选池放大保证衰减后仍有足量新鲜样本）
        .limit(max(limit * 4, 20))
    )
    result = await db.execute(stmt)
    cases = list(result.scalars().all())

    # v1.15.7 记忆时间衰减（MobileMem 2026 借鉴）：effective = quality ×
    # exp(-age_days / half_life)——陈旧经验自然降权，防旧高分 Case 压制新经验。
    # 确定性纯计算（无 LLM 成本）；关闭 flag 回退 quality-only 排序（旧行为）。
    if settings.memory_time_decay_enabled and cases:
        half_life = max(float(settings.memory_decay_half_life_days), 0.1)
        now = datetime.now(timezone.utc)

        def _decayed(case: AgentCase) -> float:
            created = case.created_at
            if created is None:
                return float(case.quality_score)
            if created.tzinfo is None:  # SQLite server_default 返回 naive UTC
                created = created.replace(tzinfo=timezone.utc)
            age_days = max((now - created).total_seconds() / 86400.0, 0.0)
            import math
            return float(case.quality_score) * math.exp(-age_days / half_life)

        cases.sort(key=_decayed, reverse=True)
    cases = cases[:limit]

    # 更新检索计数（best-effort）
    for case in cases:
        case.retrieval_count += 1
        case.last_retrieved_at = datetime.now(timezone.utc)
    if cases:
        await db.flush()

    return cases


def build_case_context(cases: list[AgentCase], max_chars: int | None = None, max_tokens: int | None = None) -> str:
    """将检索到的 Case 构建为上下文注入文本。

    max_chars（v1.13.5 Context Engineering）：注入预算上限（字符数）。
    - None = 不限制（旧行为全量注入）
    - 超预算：从末尾 Case 开始丢弃（cases 已按 quality 降序，低优先级先裁）并标注
      省略条数；预算过小连一条 Case 都放不下时返回 ""（诚实降级，不注入残片噪音）

    max_tokens（v1.13.5 token 估算，闭环字符估算遗留）：按估算 token 预算截断，
    换算系数 TOKEN_ESTIMATE_DIVISOR（len//2——中文≈1字/token 与英文≈4字符/token
    的中间值）。max_tokens 优先于 max_chars。
    """
    if max_tokens is not None and max_tokens > 0:
        max_chars = max_tokens * TOKEN_ESTIMATE_DIVISOR
    if not cases:
        return ""
    header = "[历史经验 Case —— 借鉴 EverOS Agent Memory，同类任务历史执行记录]"
    footer = "[/历史经验 Case —— 优先采用高质量步骤，避免已记录的失败路径]"
    if max_chars is not None and max_chars <= len(header):
        return ""
    parts = [header]
    total = len(header)
    injected = 0
    for i, case in enumerate(cases, 1):
        approach_steps = []
        try:
            steps = json.loads(case.approach) if case.approach else []
            for s in steps[:5]:
                attempted = s.get("attempted", "")
                result = s.get("result", "")
                approach_steps.append(f"    {s.get('step', '?')}. {attempted} → {result}")
        except (json.JSONDecodeError, TypeError):
            approach_steps.append("    (步骤解析失败)")
        block = (
            f"Case {i} [质量={case.quality_score:.1f}, 结果={case.outcome}, case_id={case.id}]:\n"
            f"  意图: {case.task_intent}\n"
            f"  步骤:\n" + "\n".join(approach_steps)
        )
        if max_chars is not None and total + len(block) > max_chars:
            break
        parts.append(block)
        total += len(block)
        injected += 1
    if injected < len(cases):
        note = f"[其余 {len(cases) - injected} 条 Case 已按上下文预算省略]"
        if max_chars is None or total + len(note) <= max_chars:
            parts.append(note)
            total += len(note)
    if max_chars is not None and total + len(footer) > max_chars:
        # 预算紧到连收尾都放不下 → 整块不注入（诚实降级）
        return ""
    parts.append(footer)
    return "\n".join(parts)

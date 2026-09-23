"""AI Token 用量计量口径（v1.17.4）

政策依据：工信厅科函〔2026〕414号 任务三——"加大**大模型、智能体、Token**
三类服务采购力度"，构建"能力—应用—计量"三位一体采购图谱，要求 Token 用量
**可量化、可核算、可审计**（人民邮电报解读：加快形成统一 Token 计量口径与
结算是扩大采购规模的前提）。

本模块基于 `agent_traces`（v1.12.x 轨迹落库）聚合 per-user / per-project 的
Token 用量口径，端点：
- `GET /api/ai-usage/tokens`（本人；传 project_id 走 verify_project_access）
- `GET /api/admin/ai-usage/tokens`（平台管理员）

诚实红线（不可绕过）：
- 计量 ≠ 计费。`agent_traces` 是按 `agent_trace_sample_rate` 采样落库的
  **可观测数据**，不是完整计费账本；接口恒带 `metering_only=True` /
  `billing_ready=False` 与 `billing_note`，禁止对外宣称 "Token 账单"。
- `agent_trace_persist_enabled=False` 时如实标注 `data_source_available=False`
  并说明原因，**不返回 0 伪装成「无用量」**。
- 纯确定性实现：零 LLM 调用、零外部网络调用、只读无副作用。
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.models.agent_trace import AgentTraceRecord

METERING_NOTE = (
    "仅提供 Token 用量计量口径，未接入计费结算闭环——"
    "统一 Token 计量口径与结算规范尚未落地，本平台不提供对外计价承诺。"
)

DATA_SOURCE = "agent_traces"

# 允许的分组维度（单源：端点参数校验与服务实现共用）
TOKEN_GROUP_BY: tuple[str, ...] = ("agent_name", "model", "provider")

LIMITATIONS: list[str] = [
    "采样落库：agent_traces 受 agent_trace_sample_rate 控制，非全量调用账本",
    "口径来源为 Agent 执行轨迹的 LLM usage 统计，未经财务对账",
    "无统一 Token 结算规范，故不提供计价金额（metering_only=True / billing_ready=False）",
]


def _now_iso() -> str:
    _bj_tz = timezone(timedelta(hours=8), name="Asia/Shanghai")
    return datetime.now(_bj_tz).isoformat()


def _unavailable_payload(
    window_days: int, group_by: str, reason: str,
) -> dict:
    return {
        "data_source": DATA_SOURCE,
        "data_source_available": False,
        "data_source_note": reason,
        "metering_only": True,
        "billing_ready": False,
        "billing_note": METERING_NOTE,
        "window_days": window_days,
        "group_by": group_by,
        "totals": None,
        "items": [],
        "limitations": LIMITATIONS,
    }


async def aggregate_token_usage(
    db: AsyncSession,
    *,
    user_id: str | None = None,
    project_id: str | None = None,
    window_days: int = 30,
    group_by: str = "agent_name",
) -> dict:
    """按 `group_by` 聚合 Token 用量（确定性 SQL 聚合，只读）。

    Args:
        user_id: 限定归属用户（用户端点传 current_user.id；管理端可选）
        project_id: 限定归属项目（可选）
        window_days: 时间窗（天，按 created_at 过滤）
        group_by: agent_name | model | provider
    """
    settings = get_settings()

    if group_by not in TOKEN_GROUP_BY:
        raise ValueError(f"group_by 不合法：{group_by}（允许 {list(TOKEN_GROUP_BY)}）")

    # 数据源不可用：诚实标注，不返回 0 伪装
    if not settings.agent_trace_persist_enabled:
        return _unavailable_payload(
            window_days, group_by,
            "agent_trace_persist_enabled=False：轨迹未落库，无 Token 计量数据源"
            "（不代表用量为 0）",
        )

    key_col = {
        "agent_name": AgentTraceRecord.agent_name,
        "model": AgentTraceRecord.model,
        "provider": AgentTraceRecord.provider,
    }[group_by]

    cutoff = datetime.now(timezone.utc) - timedelta(days=window_days)
    total_expr = func.sum(AgentTraceRecord.total_tokens)
    stmt = (
        select(
            key_col.label("group_key"),
            func.count().label("executions"),
            func.coalesce(func.sum(AgentTraceRecord.prompt_tokens), 0).label("prompt_tokens"),
            func.coalesce(func.sum(AgentTraceRecord.completion_tokens), 0).label("completion_tokens"),
            func.coalesce(total_expr, 0).label("total_tokens"),
        )
        .where(AgentTraceRecord.created_at >= cutoff)
        .group_by(key_col)
        .order_by(total_expr.desc())
    )
    if user_id:
        stmt = stmt.where(AgentTraceRecord.user_id == user_id)
    if project_id:
        stmt = stmt.where(AgentTraceRecord.project_id == project_id)

    rows = (await db.execute(stmt)).all()

    items: list[dict] = []
    t_exec = t_prompt = t_completion = t_total = 0
    for group_key, executions, prompt_tokens, completion_tokens, total_tokens in rows:
        executions = int(executions or 0)
        prompt_tokens = int(prompt_tokens or 0)
        completion_tokens = int(completion_tokens or 0)
        total_tokens = int(total_tokens or 0)
        items.append({
            # 轨迹未记录 model/provider 时如实标 unknown，不猜测
            "key": group_key or "unknown",
            "executions": executions,
            "prompt_tokens": prompt_tokens,
            "completion_tokens": completion_tokens,
            "total_tokens": total_tokens,
        })
        t_exec += executions
        t_prompt += prompt_tokens
        t_completion += completion_tokens
        t_total += total_tokens

    return {
        "generated_at": _now_iso(),
        "data_source": DATA_SOURCE,
        "data_source_available": True,
        "metering_only": True,
        "billing_ready": False,
        "billing_note": METERING_NOTE,
        "sampling_note": (
            f"agent_trace_sample_rate={settings.agent_trace_sample_rate}"
            "（采样落库，非全量调用账本）"
        ),
        "window_days": window_days,
        "cutoff": cutoff.isoformat(),
        "group_by": group_by,
        "filters": {"user_id": user_id, "project_id": project_id},
        "totals": {
            "executions": t_exec,
            "prompt_tokens": t_prompt,
            "completion_tokens": t_completion,
            "total_tokens": t_total,
        },
        "items": items,
        "limitations": LIMITATIONS,
    }

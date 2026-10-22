"""Agent Harness 管理 API（v1.2.0）

提供 Harness 运行时指标、轨迹查询、Agent 状态监控等端点。
"""

import logging
from datetime import timedelta
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy import func, select

from app.agents.harness import AgentRunStatus, get_harness
from app.auth import get_current_user
from app.database import get_db
from app.models.agent_trace import AgentTraceRecord
from app.models.user import User
from app.rbac import require_admin

router = APIRouter(prefix="/harness", tags=["Agent Harness"])
logger = logging.getLogger(__name__)


def _serialize_db_trace(record: AgentTraceRecord) -> dict:
    """把持久化轨迹序列化为与内存轨迹一致的字段（前端 snake_case 契约）。

    诚实边界：user_message 不落库（防 PII），故 user_message_truncated 恒为空；
    response_preview 为落库时的截断预览。
    """
    started = record.started_at
    finished = None
    if started is not None:
        finished = (started + timedelta(milliseconds=record.latency_ms or 0)).isoformat()
    return {
        "trace_id": record.id,
        "agent_name": record.agent_name,
        "agent_version": record.agent_version or "",
        "provider": record.provider or "",
        "model": record.model or "",
        "started_at": started.isoformat() if started else None,
        "finished_at": finished,
        "status": record.status,
        "user_message_truncated": "",  # 不落库（防 PII）
        "response_truncated": record.response_preview or "",
        "prompt_tokens": record.prompt_tokens,
        "completion_tokens": record.completion_tokens,
        "total_tokens": record.total_tokens,
        "tool_call_count": record.tool_call_count,
        "tool_call_rounds": record.tool_call_rounds,
        "fallback_used": record.fallback_used,
        "fallback_reason": record.fallback_reason or "",
        "retry_count": record.retry_count,
        "token_budget_hit": record.token_budget_hit,
        "latency_ms": round(record.latency_ms or 0.0, 2),
        "first_token_latency_ms": round(record.first_token_latency_ms or 0.0, 2),
        "error_message": record.error_message or "",
        "error_type": record.error_type or "",
        "user_id": record.user_id or "",
        "project_id": record.project_id or "",
        "scope": record.scope or "",
        "workflow_id": record.workflow_id or "",
        "context_source": record.context_source or "",
        "created_at": record.created_at.isoformat() if record.created_at else None,
    }


class HarnessMetricsResponse(BaseModel):
    total_runs: int = 0
    success_runs: int = 0
    fallback_runs: int = 0
    failed_runs: int = 0
    success_rate: float = 0.0
    fallback_rate: float = 0.0
    avg_latency_ms: float = 0.0
    total_tokens: int = 0
    trace_count: int = 0
    registered_agents: list[str] = []
    # 2026-10-22：指标为进程内计数（重启归零），显式标注口径，避免被读作持久化统计
    metrics_scope: str = "process"


class HarnessEvalResponse(BaseModel):
    status: str
    sample_size: int = 0
    metrics: dict = {}


@router.get("/metrics", response_model=HarnessMetricsResponse)
async def get_harness_metrics(
    current_user: User = Depends(get_current_user),
):
    """获取 Harness 运行时指标。

    需要登录但不需要管理员权限（普通用户可查看全局运行状况）。
    """
    harness = get_harness()
    metrics = harness.get_metrics()
    return HarnessMetricsResponse(**metrics, metrics_scope="process")


@router.get("/traces")
async def get_traces(
    agent_name: str | None = Query(None, description="Agent 名称过滤"),
    status: str | None = Query(None, description="状态过滤: success/failed/fallback"),
    limit: int = Query(50, ge=1, le=200),
    source: Literal["db", "memory"] = Query(
        "db",
        description="db=持久化轨迹（agent_traces，默认，重启不丢）；memory=进程内轨迹（重启归零）",
    ),
    current_user: User = Depends(require_admin),
    db=Depends(get_db),
):
    """查询 Agent 执行轨迹（管理员权限）。

    2026-10-22：默认改读 ``agent_traces`` 持久化表（此前只读 harness 进程内列表，
    服务重启后管理员看到空列表）；``source=memory`` 保留原进程内口径用于排障对比。
    两种来源均在响应里显式标注 ``source`` / ``note``，不做数据源伪装。
    """
    harness = get_harness()
    run_status = None
    if status:
        try:
            run_status = AgentRunStatus(status)
        except ValueError:
            pass

    if source == "memory":
        return {
            "source": "memory",
            "traces": harness.get_traces(agent_name=agent_name, status=run_status, limit=limit),
            "total": len(harness._traces),
            "note": "进程内轨迹：服务重启后归零；持久化轨迹请用 source=db（默认）",
        }

    conditions = []
    if agent_name:
        conditions.append(AgentTraceRecord.agent_name == agent_name)
    if run_status is not None:
        conditions.append(AgentTraceRecord.status == run_status.value)

    stmt = select(AgentTraceRecord)
    count_stmt = select(func.count()).select_from(AgentTraceRecord)
    if conditions:
        stmt = stmt.where(*conditions)
        count_stmt = count_stmt.where(*conditions)
    stmt = stmt.order_by(
        AgentTraceRecord.created_at.desc(), AgentTraceRecord.started_at.desc(),
    ).limit(limit)

    rows = (await db.execute(stmt)).scalars().all()
    total = (await db.execute(count_stmt)).scalar() or 0
    return {
        "source": "db",
        "traces": [_serialize_db_trace(r) for r in rows],
        "total": int(total),
        "note": "持久化轨迹（agent_traces，重启不丢）；user_message 不落库（防 PII）",
    }


@router.get("/traces/{trace_id}/replay")
async def replay_trace(
    trace_id: str,
    current_user: User = Depends(require_admin),
    db=Depends(get_db),
):
    """轨迹回放（管理员；P1，对齐 DeepSeek Harness「Every run is traceable」）。

    从 agent_traces 持久化表读取单条轨迹，重建「工具调用链 + 回复」决策路径。
    诚实边界：user_message 不落库（防 PII），仅回放系统上下文/工具调用/回复预览。
    """
    import json

    result = await db.execute(
        select(AgentTraceRecord).where(AgentTraceRecord.id == trace_id)
    )
    record = result.scalars().first()
    if record is None:
        raise HTTPException(status_code=404, detail=f"轨迹不存在: {trace_id}")

    tool_calls = []
    if record.tool_calls:
        try:
            tool_calls = json.loads(record.tool_calls)
        except (json.JSONDecodeError, TypeError):
            tool_calls = []

    logger.info(
        "trace_replayed: user=%s trace_id=%s agent=%s tool_calls=%d",
        current_user.id, trace_id, record.agent_name, len(tool_calls),
    )
    return {
        "trace_id": record.id,
        "agent_name": record.agent_name,
        "agent_version": record.agent_version,
        "status": record.status,
        "workflow_id": record.workflow_id,
        "provider": record.provider,
        "model": record.model,
        "latency_ms": record.latency_ms,
        "total_tokens": record.total_tokens,
        "tool_call_count": record.tool_call_count,
        "token_budget_hit": record.token_budget_hit,
        "fallback_used": record.fallback_used,
        "replay": {
            "system_context_preview": record.prompt_preview,
            "tool_calls": tool_calls,
            "response_preview": record.response_preview,
        },
        "note": "轨迹可回放（工具调用链）；user_message 不落库（防 PII），仅回放系统上下文/工具调用/回复预览",
    }


@router.get("/eval", response_model=HarnessEvalResponse)
async def run_eval(
    current_user: User = Depends(require_admin),
):
    """运行离线评估（管理员权限）。

    返回最近 100 条轨迹的成功率、降级率、延迟等指标。
    """
    harness = get_harness()
    result = harness.run_eval()
    return HarnessEvalResponse(**result)


@router.get("/health")
async def harness_health():
    """Harness 健康检查（公开端点）。"""
    harness = get_harness()
    metrics = harness.get_metrics()
    return {
        "status": "healthy",
        "registered_agents": metrics["registered_agents"],
        "trace_count": metrics["trace_count"],
        "total_runs": metrics["total_runs"],
        # 2026-10-22：明确口径——健康检查里的计数是进程内指标（重启归零），
        # 持久化轨迹以 /api/harness/traces（source=db）为准。
        "metrics_scope": "process",
        "persistent_trace_source": "agent_traces",
        "note": "trace_count/total_runs 为进程内计数（重启归零）；持久化轨迹查询 /api/harness/traces",
    }

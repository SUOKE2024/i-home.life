"""Agent Harness 管理 API（v1.2.0）

提供 Harness 运行时指标、轨迹查询、Agent 状态监控等端点。
"""

import logging

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel

from app.agents.harness import AgentRunStatus, get_harness
from app.auth import get_current_user
from app.database import get_db
from app.models.user import User
from app.rbac import require_admin

router = APIRouter(prefix="/harness", tags=["Agent Harness"])
logger = logging.getLogger(__name__)


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
    return HarnessMetricsResponse(**metrics)


@router.get("/traces")
async def get_traces(
    agent_name: str | None = Query(None, description="Agent 名称过滤"),
    status: str | None = Query(None, description="状态过滤: success/failed/fallback"),
    limit: int = Query(50, ge=1, le=200),
    current_user: User = Depends(require_admin),
):
    """查询 Agent 执行轨迹（管理员权限）。"""
    harness = get_harness()
    run_status = None
    if status:
        try:
            run_status = AgentRunStatus(status)
        except ValueError:
            pass
    return {
        "traces": harness.get_traces(agent_name=agent_name, status=run_status, limit=limit),
        "total": len(harness._traces),
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

    from sqlalchemy import select

    from app.models.agent_trace import AgentTraceRecord

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
    }

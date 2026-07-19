"""Agent Harness 管理 API（v1.2.0）

提供 Harness 运行时指标、轨迹查询、Agent 状态监控等端点。
"""

import logging

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel

from app.agents.harness import AgentRunStatus, get_harness
from app.auth import get_current_user
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

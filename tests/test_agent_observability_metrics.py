"""v1.12.x 编排可观测性指标上报测试。

覆盖：
- /metrics 端点暴露 v1.12.x 新增编排/轨迹指标（agent_orchestration_* / agent_trace_persisted_total）
- 真实编排调用后指标自增（不依赖精确计数，仅断言存在性，兼容 -n auto 并行 worker）
"""
import pytest
from httpx import AsyncClient

from app.metrics import (
    agent_orchestration_total,
    agent_orchestration_duration_seconds,
    agent_orchestration_task_total,
    agent_trace_persisted_total,
)
from tests.test_agent_orchestration import _register


@pytest.mark.asyncio
async def test_metrics_exposes_orchestration_indicators(client: AsyncClient):
    """打点后 /metrics 暴露 v1.12.x 编排/轨迹指标名。"""
    agent_orchestration_total.labels(engine="orchestration_pipeline", status="success").inc()
    agent_orchestration_duration_seconds.labels(engine="orchestration_pipeline").observe(1.5)
    agent_orchestration_task_total.labels(agent="designer", status="success").inc()
    agent_trace_persisted_total.labels(agent="designer", status="success").inc()

    resp = await client.get("/metrics")
    assert resp.status_code == 200
    text = resp.text
    for name in (
        "agent_orchestration_total",
        "agent_orchestration_duration_seconds",
        "agent_orchestration_task_total",
        "agent_trace_persisted_total",
    ):
        assert name in text, f"指标 {name} 未在 /metrics 暴露"


@pytest.mark.asyncio
async def test_orchestrate_flow_updates_metrics(client: AsyncClient):
    """真实编排调用后 agent_orchestration_total / task_total 指标可见。"""
    token = await _register(client)
    headers = {"Authorization": f"Bearer {token}"}
    resp = await client.post(
        "/api/agents/orchestrate",
        json={"message": "帮我算一下120平米装修预算"},
        headers=headers,
    )
    assert resp.status_code == 200

    resp = await client.get("/metrics")
    assert resp.status_code == 200
    text = resp.text
    assert 'agent_orchestration_total{engine="orchestration_pipeline"' in text
    assert "agent_orchestration_duration_seconds" in text
    # 子任务指标：本次至少有一个子任务执行并计数
    assert 'agent_orchestration_task_total{' in text

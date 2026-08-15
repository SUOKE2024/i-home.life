"""Agent Harness 管理 API 测试

覆盖端点:
- GET /api/harness/metrics
- GET /api/harness/traces
- GET /api/harness/eval
- GET /api/harness/health
"""
import json
import uuid

import pytest
from httpx import AsyncClient

from app.models.agent_trace import AgentTraceRecord


@pytest.mark.asyncio
async def test_harness_health_public(client: AsyncClient):
    """Harness 健康检查无需认证"""
    resp = await client.get("/api/harness/health")
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "healthy"


@pytest.mark.asyncio
async def test_harness_metrics_requires_auth(client: AsyncClient):
    """获取指标需要认证"""
    resp = await client.get("/api/harness/metrics")
    assert resp.status_code in (401, 403)


@pytest.mark.asyncio
async def test_harness_metrics_authenticated(auth_headers: dict, client: AsyncClient):
    """已认证用户可获取指标"""
    resp = await client.get("/api/harness/metrics", headers=auth_headers)
    assert resp.status_code == 200
    data = resp.json()
    assert "total_runs" in data
    assert "registered_agents" in data


@pytest.mark.asyncio
async def test_harness_traces_requires_admin(auth_headers: dict, client: AsyncClient):
    """查询轨迹需要管理员权限（普通用户 403）"""
    resp = await client.get("/api/harness/traces", headers=auth_headers)
    assert resp.status_code in (401, 403)


@pytest.mark.asyncio
async def test_harness_eval_requires_admin(auth_headers: dict, client: AsyncClient):
    """运行评估需要管理员权限（普通用户 403）"""
    resp = await client.get("/api/harness/eval", headers=auth_headers)
    assert resp.status_code in (401, 403)


@pytest.mark.asyncio
async def test_harness_health_structure(client: AsyncClient):
    """健康检查响应结构正确"""
    resp = await client.get("/api/harness/health")
    data = resp.json()
    assert "registered_agents" in data
    assert "trace_count" in data
    assert "total_runs" in data


async def _register_admin(client: AsyncClient) -> str:
    """注册管理员并返回 access_token。"""
    phone = f"138{uuid.uuid4().hex[:8]}"
    resp = await client.post(
        "/api/auth/register",
        json={"phone": phone, "name": "轨迹管理员", "password": "test123456", "role": "admin"},
    )
    assert resp.status_code == 201, resp.json()
    return resp.json()["access_token"]


@pytest.mark.asyncio
async def test_trace_replay_requires_admin(auth_headers: dict, client: AsyncClient):
    """轨迹回放需要管理员权限（普通用户 401/403）"""
    resp = await client.get("/api/harness/traces/xxx/replay", headers=auth_headers)
    assert resp.status_code in (401, 403)


@pytest.mark.asyncio
async def test_trace_replay_not_found(client: AsyncClient):
    """轨迹不存在 → 404"""
    token = await _register_admin(client)
    headers = {"Authorization": f"Bearer {token}"}
    resp = await client.get("/api/harness/traces/nonexistent/replay", headers=headers)
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_trace_replay_reconstructs(client: AsyncClient, db_session):
    """轨迹回放重建「工具调用链 + 回复」决策路径"""
    token = await _register_admin(client)
    headers = {"Authorization": f"Bearer {token}"}

    trace_id = str(uuid.uuid4())
    db_session.add(AgentTraceRecord(
        id=trace_id,
        agent_name="designer",
        status="success",
        workflow_id="wf-replay-1",
        tool_calls=json.dumps([
            {"tool": "get_budget", "arguments": {"area": 100}, "result": {"source": "db"}},
            {"tool": "get_design_layout", "arguments": {"style": "nordic"}, "result": {"source": "catalog"}},
        ]),
        tool_call_count=2,
        prompt_preview="你是室内设计师...",
        response_preview="已生成 3 套方案...",
    ))
    await db_session.commit()

    resp = await client.get(f"/api/harness/traces/{trace_id}/replay", headers=headers)
    assert resp.status_code == 200
    body = resp.json()
    assert body["trace_id"] == trace_id
    assert body["agent_name"] == "designer"
    assert body["workflow_id"] == "wf-replay-1"
    assert body["tool_call_count"] == 2
    assert len(body["replay"]["tool_calls"]) == 2
    assert body["replay"]["tool_calls"][0]["tool"] == "get_budget"
    assert body["replay"]["tool_calls"][0]["arguments"]["area"] == 100
    assert body["replay"]["response_preview"] == "已生成 3 套方案..."
    assert "user_message 不落库" in body["note"]


@pytest.mark.asyncio
async def test_trace_replay_malformed_tool_calls(client: AsyncClient, db_session):
    """tool_calls 非法 JSON → 空列表（诚实降级，不 500）"""
    token = await _register_admin(client)
    headers = {"Authorization": f"Bearer {token}"}

    trace_id = str(uuid.uuid4())
    db_session.add(AgentTraceRecord(
        id=trace_id,
        agent_name="designer",
        status="success",
        tool_calls="not-valid-json",
        tool_call_count=0,
    ))
    await db_session.commit()

    resp = await client.get(f"/api/harness/traces/{trace_id}/replay", headers=headers)
    assert resp.status_code == 200
    assert resp.json()["replay"]["tool_calls"] == []

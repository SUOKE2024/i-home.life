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
    assert data["metrics_scope"] == "process"


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
    """健康检查响应结构正确（明确标注指标口径为进程内）"""
    resp = await client.get("/api/harness/health")
    data = resp.json()
    assert "registered_agents" in data
    assert "trace_count" in data
    assert "total_runs" in data
    assert data["metrics_scope"] == "process"
    assert data["persistent_trace_source"] == "agent_traces"
    assert "重启归零" in data["note"]


async def _register_admin(client: AsyncClient) -> str:
    """直接通过 DB 创建管理员并签发 token（register 已禁止自注册 admin）"""
    from app.database import async_session
    from app.models.user import User
    from app.auth.paseto_handler import create_token

    user_id = str(uuid.uuid4())
    async with async_session() as db:
        db.add(User(id=user_id, phone=f"138{uuid.uuid4().hex[:8]}", name="轨迹管理员", role="admin", hashed_password="x"))
        await db.commit()
    return create_token(user_id, "admin")


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


# ── 轨迹列表数据源（2026-10-22：默认 DB 持久化，memory 为排障对照）──


@pytest.mark.asyncio
async def test_harness_traces_default_db_source(client: AsyncClient, db_session):
    """默认 source=db：读 agent_traces 持久化表（重启不丢），非进程内列表"""
    token = await _register_admin(client)
    headers = {"Authorization": f"Bearer {token}"}

    trace_id = str(uuid.uuid4())
    db_session.add(AgentTraceRecord(
        id=trace_id,
        agent_name="designer-db",
        status="success",
        workflow_id="wf-db-1",
        tool_call_count=1,
        total_tokens=120,
        latency_ms=88.5,
        response_preview="已生成方案...",
    ))
    await db_session.commit()

    resp = await client.get(
        "/api/harness/traces", params={"agent_name": "designer-db"}, headers=headers,
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["source"] == "db"
    assert body["total"] == 1
    assert body["traces"][0]["trace_id"] == trace_id
    assert body["traces"][0]["workflow_id"] == "wf-db-1"
    assert body["traces"][0]["total_tokens"] == 120
    assert body["traces"][0]["response_truncated"] == "已生成方案..."
    assert body["traces"][0]["user_message_truncated"] == ""
    assert "user_message 不落库" in body["note"]


@pytest.mark.asyncio
async def test_harness_traces_db_status_filter(client: AsyncClient, db_session):
    """DB 来源同样支持 status / agent_name 过滤"""
    token = await _register_admin(client)
    headers = {"Authorization": f"Bearer {token}"}

    db_session.add_all([
        AgentTraceRecord(id=str(uuid.uuid4()), agent_name="filter-agent", status="success"),
        AgentTraceRecord(id=str(uuid.uuid4()), agent_name="filter-agent", status="failed"),
    ])
    await db_session.commit()

    resp = await client.get(
        "/api/harness/traces",
        params={"agent_name": "filter-agent", "status": "failed"},
        headers=headers,
    )
    body = resp.json()
    assert body["source"] == "db"
    assert body["total"] == 1
    assert body["traces"][0]["status"] == "failed"


@pytest.mark.asyncio
async def test_harness_traces_memory_source(client: AsyncClient):
    """显式 source=memory：保留进程内口径并标注重启归零"""
    token = await _register_admin(client)
    headers = {"Authorization": f"Bearer {token}"}

    resp = await client.get(
        "/api/harness/traces", params={"source": "memory"}, headers=headers,
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["source"] == "memory"
    assert "重启" in body["note"]

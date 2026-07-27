"""A2A 协议 API 测试

覆盖端点:
- GET  /.well-known/agent-card
- GET  /api/a2a/agents
- POST /api/a2a/tasks/send
- GET  /api/a2a/tasks/{id}
- GET  /api/a2a/tasks/{id}/status
"""
import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_agent_card_public(client: AsyncClient):
    """Agent Card 公开端点无需认证"""
    resp = await client.get("/.well-known/agent-card")
    assert resp.status_code == 200
    data = resp.json()
    assert "name" in data or "description" in data or "url" in data


@pytest.mark.asyncio
async def test_list_agents_requires_auth(client: AsyncClient):
    """列出 Agent 需要认证"""
    resp = await client.get("/api/a2a/agents")
    assert resp.status_code in (401, 403)


@pytest.mark.asyncio
async def test_list_agents_authenticated(auth_headers: dict, client: AsyncClient):
    """已认证用户可列出 Agent（序列化 bug 已修复：注册表类对象转为名称/描述结构）"""
    resp = await client.get("/api/a2a/agents", headers=auth_headers)
    assert resp.status_code == 200
    data = resp.json()
    assert isinstance(data["agents"], list)
    assert data["count"] == len(data["agents"])
    if data["agents"]:
        assert {"name", "class_name", "description"} <= set(data["agents"][0].keys())


@pytest.mark.asyncio
async def test_send_task_requires_auth(client: AsyncClient):
    """下发任务需要认证"""
    resp = await client.post("/api/a2a/tasks/send", json={"agent_name": "OrchestratorAgent", "message": "测试任务"})
    assert resp.status_code in (401, 403)


@pytest.mark.asyncio
async def test_send_task_authenticated(auth_headers: dict, client: AsyncClient):
    """已认证用户可下发 A2A 任务"""
    resp = await client.post(
        "/api/a2a/tasks/send",
        json={"agent_name": "DesignerAgent", "message": "设计吧台"},
        headers=auth_headers,
    )
    assert resp.status_code in (200, 201, 503)


@pytest.mark.asyncio
async def test_get_task_not_found(auth_headers: dict, client: AsyncClient):
    """查询不存在的任务返回 404"""
    resp = await client.get("/api/a2a/tasks/nonexistent-123", headers=auth_headers)
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_get_task_status_not_found(auth_headers: dict, client: AsyncClient):
    """查询不存在的任务状态返回 404"""
    resp = await client.get("/api/a2a/tasks/nonexistent-123/status", headers=auth_headers)
    assert resp.status_code == 404

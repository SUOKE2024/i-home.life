"""Agent 管理 API 测试

v1.2.x：Agent 列表能力迁移至 A2A 协议端点 /api/a2a/agents；
/api/agents 仅保留 chat/design/sessions 等业务动作端点。

覆盖端点:
- GET /api/a2a/agents
- GET /api/agents/sessions
"""
import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_agents_unauthorized(client: AsyncClient):
    """未认证用户无法访问 Agent 列表"""
    resp = await client.get("/api/a2a/agents")
    assert resp.status_code in (401, 403)


@pytest.mark.asyncio
async def test_list_agents(auth_headers: dict, client: AsyncClient):
    """已认证用户获取 Agent 列表（A2A）"""
    resp = await client.get("/api/a2a/agents", headers=auth_headers)
    assert resp.status_code == 200
    data = resp.json()
    assert isinstance(data["agents"], list)
    assert data["count"] == len(data["agents"])


@pytest.mark.asyncio
async def test_list_agents_has_registered_names(auth_headers: dict, client: AsyncClient):
    """Agent 列表应包含已注册的 Agent 名称"""
    resp = await client.get("/api/a2a/agents", headers=auth_headers)
    agent_names = [a.get("name", "") for a in resp.json()["agents"]]
    # 至少有 orchestrator/designer 等核心 Agent
    assert len(agent_names) > 0
    assert "orchestrator" in agent_names


@pytest.mark.asyncio
async def test_get_agent_not_found(auth_headers: dict, client: AsyncClient):
    """获取不存在的 Agent 会话返回 404"""
    resp = await client.get("/api/agents/sessions/nonexistent-session-id", headers=auth_headers)
    assert resp.status_code in (403, 404)


@pytest.mark.asyncio
async def test_get_agent_by_name(auth_headers: dict, client: AsyncClient):
    """按名称获取 Agent 信息（A2A 列表含 class_name/description）"""
    resp = await client.get("/api/a2a/agents", headers=auth_headers)
    agents = resp.json()["agents"]
    assert len(agents) > 0
    first = agents[0]
    assert first["name"]
    assert first["class_name"]
    assert isinstance(first["description"], str)

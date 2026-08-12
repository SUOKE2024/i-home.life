"""IM 协作 API 测试（F40 三方协作群组）

覆盖端点:
- GET  /api/chat/rooms/{project_id}
- POST /api/chat/messages
- GET  /api/chat/messages/{project_id}
"""
import uuid
import pytest
from httpx import AsyncClient


async def _create_project(client: AsyncClient, headers: dict) -> str:
    resp = await client.post(
        "/api/projects",
        json={"name": f"IM测试项目-{uuid.uuid4().hex[:6]}", "total_area": 100.0},
        headers=headers,
    )
    return resp.json()["id"]


@pytest.mark.asyncio
async def test_rooms_unauthorized(client: AsyncClient):
    """未认证用户无法获取聊天室列表"""
    resp = await client.get("/api/chat/rooms/fake-id")
    assert resp.status_code in (401, 403)


@pytest.mark.asyncio
async def test_get_rooms(auth_headers: dict, client: AsyncClient):
    """获取项目聊天室"""
    project_id = await _create_project(client, auth_headers)
    resp = await client.get(f"/api/chat/rooms/{project_id}", headers=auth_headers)
    assert resp.status_code == 200


@pytest.mark.asyncio
async def test_send_message(auth_headers: dict, client: AsyncClient):
    """发送聊天消息"""
    project_id = await _create_project(client, auth_headers)
    resp = await client.post(
        "/api/chat/messages",
        json={
            "project_id": project_id,
            "content": "水电验收已完成",
            "content_type": "text",
        },
        headers=auth_headers,
    )
    assert resp.status_code == 201


@pytest.mark.asyncio
async def test_get_messages(auth_headers: dict, client: AsyncClient):
    """获取聊天消息列表"""
    project_id = await _create_project(client, auth_headers)
    await client.post(
        "/api/chat/messages",
        json={"project_id": project_id, "content": "测试消息", "content_type": "text"},
        headers=auth_headers,
    )
    resp = await client.get(f"/api/chat/messages/{project_id}", headers=auth_headers)
    assert resp.status_code == 200


@pytest.mark.asyncio
async def test_empty_message_rejected(auth_headers: dict, client: AsyncClient):
    """空消息应被拒绝"""
    project_id = await _create_project(client, auth_headers)
    resp = await client.post(
        "/api/chat/messages",
        json={"project_id": project_id, "content": "", "content_type": "text"},
        headers=auth_headers,
    )
    assert resp.status_code in (400, 422)


@pytest.mark.asyncio
async def test_cross_user_chat_access(auth_headers: dict, client: AsyncClient):
    """其他用户无法访问非自己项目的聊天室"""
    project_id = await _create_project(client, auth_headers)
    reg = await client.post(
        "/api/auth/register",
        json={"phone": f"1394401{uuid.uuid4().int % 10000:04d}", "name": "他人", "password": "test123456"},
    )
    other_headers = {"Authorization": f"Bearer {reg.json()['access_token']}"}
    resp = await client.get(f"/api/chat/rooms/{project_id}", headers=other_headers)
    assert resp.status_code in (403, 404)


# ── F40 Agent 群成员 + 自动回复 ──


async def _add_agent(client: AsyncClient, headers: dict, room_id: str, agent_name: str):
    return await client.post(
        f"/api/chat/rooms/{room_id}/agents",
        json={"agent_name": agent_name},
        headers=headers,
    )


@pytest.mark.asyncio
async def test_add_agent_to_room(auth_headers: dict, client: AsyncClient):
    """F40: Agent 加入聊天室 + 重复加入去重"""
    project_id = await _create_project(client, auth_headers)
    room_id = (await client.get(f"/api/chat/rooms/{project_id}", headers=auth_headers)).json()["id"]

    resp = await _add_agent(client, auth_headers, room_id, "qa_inspector")
    assert resp.status_code == 201
    assert resp.json()["agent_members"] == ["qa_inspector"]

    # 重复加入去重
    await _add_agent(client, auth_headers, room_id, "qa_inspector")
    list_resp = await client.get(f"/api/chat/rooms/{room_id}/agents", headers=auth_headers)
    assert list_resp.status_code == 200
    assert list_resp.json()["agent_members"] == ["qa_inspector"]


@pytest.mark.asyncio
async def test_add_unknown_agent_rejected(auth_headers: dict, client: AsyncClient):
    """F40: 未知 Agent 名称被拒绝（AGENT_ROSTER 校验）"""
    project_id = await _create_project(client, auth_headers)
    room_id = (await client.get(f"/api/chat/rooms/{project_id}", headers=auth_headers)).json()["id"]
    resp = await _add_agent(client, auth_headers, room_id, "not_a_real_agent")
    assert resp.status_code == 400


@pytest.mark.asyncio
async def test_agent_auto_reply_rule_based(auth_headers: dict, client: AsyncClient, monkeypatch):
    """F40: 业主发消息 + 房间有 Agent 成员 → 自动回复（规则路径 engine=rule_based）"""
    from app.services import chat_service
    monkeypatch.setattr(chat_service, "_resolve_agent_class", lambda name: None)

    project_id = await _create_project(client, auth_headers)
    room_id = (await client.get(f"/api/chat/rooms/{project_id}", headers=auth_headers)).json()["id"]
    await _add_agent(client, auth_headers, room_id, "concierge")

    resp = await client.post(
        "/api/chat/messages",
        json={"project_id": project_id, "content": "你好，装修进度怎么样了？"},
        headers=auth_headers,
    )
    assert resp.status_code == 201  # 原消息创建不被自动回复阻塞

    msgs = await client.get(f"/api/chat/messages/{project_id}", headers=auth_headers)
    agent_msgs = [m for m in msgs.json() if m.get("agent_mode") == "auto_reply"]
    assert len(agent_msgs) == 1
    assert agent_msgs[0]["generated_by"] == "agent:concierge"
    assert agent_msgs[0]["agent_mode"] == "auto_reply"
    assert agent_msgs[0]["engine"] == "rule_based"
    assert agent_msgs[0]["sender_role"] == "agent"


@pytest.mark.asyncio
async def test_agent_auto_reply_real_agent_success(auth_headers: dict, client: AsyncClient, monkeypatch):
    """F40: 真实 Agent 路径 — harness 成功返回 → generated_by 标注（无 engine）"""
    from app.services import chat_service

    class _StubAgent:
        agent_name = "qa_inspector"
        provider = "deepseek"
        tools = []

        async def think(self, message, context="", db=None, project_id="", user_id=""):
            return "已收到，我将安排质检复核。"

        async def close(self):
            pass

    monkeypatch.setattr(chat_service, "_resolve_agent_class", lambda name: _StubAgent)

    project_id = await _create_project(client, auth_headers)
    room_id = (await client.get(f"/api/chat/rooms/{project_id}", headers=auth_headers)).json()["id"]
    await _add_agent(client, auth_headers, room_id, "qa_inspector")

    await client.post(
        "/api/chat/messages",
        json={"project_id": project_id, "content": "帮我检查一下瓷砖空鼓"},
        headers=auth_headers,
    )

    msgs = await client.get(f"/api/chat/messages/{project_id}", headers=auth_headers)
    agent_msgs = [m for m in msgs.json() if m.get("agent_mode") == "auto_reply"]
    assert len(agent_msgs) == 1
    assert agent_msgs[0]["content"] == "已收到，我将安排质检复核。"
    assert agent_msgs[0]["generated_by"] == "agent:qa_inspector"
    assert agent_msgs[0]["engine"] is None


@pytest.mark.asyncio
async def test_agent_auto_reply_honest_placeholder_on_failure(auth_headers: dict, client: AsyncClient, monkeypatch):
    """F40: Agent 处理失败 → 诚实降级占位消息（Agent 暂时无法响应（服务降级））"""
    from app.services import chat_service

    class _FailingAgent:
        agent_name = "qa_inspector"
        provider = "deepseek"
        tools = []

        async def think(self, message, context=""):
            raise RuntimeError("LLM unavailable")

        async def close(self):
            pass

    monkeypatch.setattr(chat_service, "_resolve_agent_class", lambda name: _FailingAgent)

    project_id = await _create_project(client, auth_headers)
    room_id = (await client.get(f"/api/chat/rooms/{project_id}", headers=auth_headers)).json()["id"]
    await _add_agent(client, auth_headers, room_id, "qa_inspector")

    await client.post(
        "/api/chat/messages",
        json={"project_id": project_id, "content": "检查墙面裂缝"},
        headers=auth_headers,
    )

    msgs = await client.get(f"/api/chat/messages/{project_id}", headers=auth_headers)
    agent_msgs = [m for m in msgs.json() if m.get("agent_mode") == "auto_reply"]
    assert len(agent_msgs) == 1
    assert "服务降级" in agent_msgs[0]["content"]
    assert agent_msgs[0]["generated_by"] == "agent:qa_inspector"
    assert agent_msgs[0]["engine"] == "rule_based"
    assert agent_msgs[0]["is_placeholder"] is True

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

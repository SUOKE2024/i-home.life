"""F32 场景编辑 API 测试

覆盖端点:
- POST /api/scene-automation/scenes
- GET  /api/scene-automation/scenes/{project_id}
- PATCH /api/scene-automation/scenes/{id}
- DELETE /api/scene-automation/scenes/{id}
"""
import uuid
import pytest
from httpx import AsyncClient


async def _create_project(client: AsyncClient, headers: dict) -> str:
    resp = await client.post(
        "/api/projects",
        json={"name": f"场景测试项目-{uuid.uuid4().hex[:6]}", "total_area": 100.0},
        headers=headers,
    )
    return resp.json()["id"]


@pytest.mark.asyncio
async def test_scenes_unauthorized(client: AsyncClient):
    """未认证用户无法访问场景"""
    resp = await client.get("/api/scene-automation/scenes/fake-id")
    assert resp.status_code in (401, 403)


@pytest.mark.asyncio
async def test_create_scene(auth_headers: dict, client: AsyncClient):
    """创建场景自动化"""
    project_id = await _create_project(client, auth_headers)
    resp = await client.post(
        "/api/scene-automation/scenes",
        json={
            "project_id": project_id,
            "name": "回家模式",
            "trigger_type": "schedule",
            "trigger_config": {"time": "18:00", "days": ["mon", "tue", "wed", "thu", "fri"]},
            "actions": [{"device": "light", "command": "on", "params": {"brightness": 80}}],
        },
        headers=auth_headers,
    )
    assert resp.status_code in (200, 201)


@pytest.mark.asyncio
async def test_list_scenes(auth_headers: dict, client: AsyncClient):
    """列出项目场景"""
    project_id = await _create_project(client, auth_headers)
    await client.post(
        "/api/scene-automation/scenes",
        json={
            "project_id": project_id, "name": "离家模式",
            "trigger_type": "manual", "actions": [{"device": "all", "command": "off"}],
        },
        headers=auth_headers,
    )
    resp = await client.get(f"/api/scene-automation/scenes/project/{project_id}", headers=auth_headers)
    assert resp.status_code == 200


@pytest.mark.asyncio
async def test_update_scene(auth_headers: dict, client: AsyncClient):
    """更新场景"""
    project_id = await _create_project(client, auth_headers)
    create_resp = await client.post(
        "/api/scene-automation/scenes",
        json={
            "project_id": project_id, "name": "睡眠模式",
            "trigger_type": "manual", "actions": [{"device": "curtain", "command": "close"}],
        },
        headers=auth_headers,
    )
    scene_id = create_resp.json()["id"]
    resp = await client.patch(
        f"/api/scene-automation/scenes/{scene_id}",
        json={"name": "深度睡眠模式"},
        headers=auth_headers,
    )
    assert resp.status_code == 200


@pytest.mark.asyncio
async def test_delete_scene(auth_headers: dict, client: AsyncClient):
    """删除场景"""
    project_id = await _create_project(client, auth_headers)
    create_resp = await client.post(
        "/api/scene-automation/scenes",
        json={
            "project_id": project_id, "name": "待删除场景",
            "trigger_type": "manual", "actions": [],
        },
        headers=auth_headers,
    )
    scene_id = create_resp.json()["id"]
    resp = await client.delete(f"/api/scene-automation/scenes/{scene_id}", headers=auth_headers)
    assert resp.status_code in (200, 204)


@pytest.mark.asyncio
async def test_cross_user_scene_access(auth_headers: dict, client: AsyncClient):
    """其他用户无法操作非自己项目的场景"""
    project_id = await _create_project(client, auth_headers)
    create_resp = await client.post(
        "/api/scene-automation/scenes",
        json={
            "project_id": project_id, "name": "观影模式",
            "trigger_type": "manual", "actions": [],
        },
        headers=auth_headers,
    )
    scene_id = create_resp.json()["id"]
    reg = await client.post(
        "/api/auth/register",
        json={"phone": f"1395501{uuid.uuid4().int % 10000:04d}", "name": "他人", "password": "test123456"},
    )
    other_headers = {"Authorization": f"Bearer {reg.json()['access_token']}"}
    resp = await client.patch(
        f"/api/scene-automation/scenes/{scene_id}",
        json={"name": "hacked"},
        headers=other_headers,
    )
    assert resp.status_code in (403, 404)

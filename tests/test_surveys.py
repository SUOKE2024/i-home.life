"""测量 (Survey) 功能测试"""

import pytest
from httpx import AsyncClient


async def _register_and_get_project(client: AsyncClient) -> tuple[str, str]:
    """注册用户并创建项目，返回 (token, project_id)"""
    resp = await client.post(
        "/api/auth/register",
        json={"phone": "13900006001", "name": "测量测试", "password": "test123456"},
    )
    token = resp.json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}
    proj = await client.post(
        "/api/projects",
        headers=headers,
        json={"name": "测量测试项目", "address": "测试地址", "total_area": 100.0, "floors": []},
    )
    pid = proj.json()["id"]
    return token, pid


@pytest.mark.asyncio
async def test_create_survey(client: AsyncClient):
    token, pid = await _register_and_get_project(client)
    headers = {"Authorization": f"Bearer {token}"}
    resp = await client.post(
        "/api/surveys",
        headers=headers,
        json={
            "project_id": pid,
            "name": "现场实测",
            "surveyor": "测量员小王",
            "method": "manual",
            "wall_height": 2.8,
            "rooms": [
                {"name": "客厅", "room_type": "living_room", "width": 6.0, "length": 6.0},
                {"name": "主卧", "room_type": "bedroom", "width": 4.0, "length": 5.0},
            ],
        },
    )
    assert resp.status_code == 201
    data = resp.json()
    assert data["name"] == "现场实测"
    assert data["method"] == "manual"
    assert data["wall_height"] == 2.8
    assert data["total_area"] == 56.0   # 36 + 20
    assert data["status"] == "draft"
    assert data["surveyor"] == "测量员小王"


@pytest.mark.asyncio
async def test_list_surveys_empty(client: AsyncClient):
    token, pid = await _register_and_get_project(client)
    headers = {"Authorization": f"Bearer {token}"}
    resp = await client.get(f"/api/surveys/project/{pid}", headers=headers)
    assert resp.status_code == 200
    assert resp.json() == []


@pytest.mark.asyncio
async def test_list_surveys(client: AsyncClient):
    token, pid = await _register_and_get_project(client)
    headers = {"Authorization": f"Bearer {token}"}
    await client.post(
        "/api/surveys",
        headers=headers,
        json={
            "project_id": pid,
            "name": "测量1",
            "method": "manual",
            "rooms": [{"name": "客厅", "room_type": "living_room", "width": 5.0, "length": 6.0}],
        },
    )
    resp = await client.get(f"/api/surveys/project/{pid}", headers=headers)
    assert resp.status_code == 200
    assert len(resp.json()) == 1


@pytest.mark.asyncio
async def test_get_survey(client: AsyncClient):
    token, pid = await _register_and_get_project(client)
    headers = {"Authorization": f"Bearer {token}"}
    create = await client.post(
        "/api/surveys",
        headers=headers,
        json={
            "project_id": pid,
            "name": "查看测试",
            "method": "manual",
            "rooms": [{"name": "厨房", "room_type": "kitchen", "width": 3.0, "length": 4.0}],
        },
    )
    sid = create.json()["id"]
    resp = await client.get(f"/api/surveys/{sid}", headers=headers)
    assert resp.status_code == 200
    assert resp.json()["total_area"] == 12.0


@pytest.mark.asyncio
async def test_get_survey_not_found(client: AsyncClient):
    token, _ = await _register_and_get_project(client)
    headers = {"Authorization": f"Bearer {token}"}
    resp = await client.get("/api/surveys/nonexistent-id", headers=headers)
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_update_survey(client: AsyncClient):
    token, pid = await _register_and_get_project(client)
    headers = {"Authorization": f"Bearer {token}"}
    create = await client.post(
        "/api/surveys",
        headers=headers,
        json={
            "project_id": pid,
            "name": "原始",
            "method": "manual",
            "rooms": [{"name": "客厅", "room_type": "living_room", "width": 3.0, "length": 3.0}],
        },
    )
    sid = create.json()["id"]
    resp = await client.put(
        f"/api/surveys/{sid}",
        headers=headers,
        json={
            "name": "已更新",
            "surveyor": "李工",
            "rooms": [{"name": "客厅", "room_type": "living_room", "width": 4.0, "length": 4.0}],
        },
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["name"] == "已更新"
    assert data["surveyor"] == "李工"
    assert data["total_area"] == 16.0


@pytest.mark.asyncio
async def test_delete_survey(client: AsyncClient):
    token, pid = await _register_and_get_project(client)
    headers = {"Authorization": f"Bearer {token}"}
    create = await client.post(
        "/api/surveys",
        headers=headers,
        json={
            "project_id": pid,
            "name": "待删除",
            "method": "manual",
            "rooms": [{"name": "卫生间", "room_type": "bathroom", "width": 2.0, "length": 3.0}],
        },
    )
    sid = create.json()["id"]
    resp = await client.delete(f"/api/surveys/{sid}", headers=headers)
    assert resp.status_code == 204
    get_resp = await client.get(f"/api/surveys/{sid}", headers=headers)
    assert get_resp.status_code == 404


@pytest.mark.asyncio
async def test_apply_survey_to_project(client: AsyncClient):
    """测试一键应用到项目"""
    token, pid = await _register_and_get_project(client)
    headers = {"Authorization": f"Bearer {token}"}
    create = await client.post(
        "/api/surveys",
        headers=headers,
        json={
            "project_id": pid,
            "name": "应用测试",
            "method": "manual",
            "wall_height": 2.9,
            "rooms": [
                {"name": "客厅", "room_type": "living_room", "width": 6.0, "length": 7.0},
                {"name": "卧室", "room_type": "bedroom", "width": 4.0, "length": 5.0},
            ],
        },
    )
    sid = create.json()["id"]
    resp = await client.post(f"/api/surveys/{sid}/apply", headers=headers)
    assert resp.status_code == 200
    result = resp.json()
    assert result["total_area"] == 62.0   # 42 + 20
    assert result["added"] + result["updated"] >= 2

    # 验证项目已更新
    proj = await client.get(f"/api/projects/{pid}", headers=headers)
    assert proj.status_code == 200
    assert proj.json()["total_area"] == 62.0

    # 验证测量状态变为 completed
    survey = await client.get(f"/api/surveys/{sid}", headers=headers)
    assert survey.json()["status"] == "completed"


@pytest.mark.asyncio
async def test_create_survey_requires_auth(client: AsyncClient):
    resp = await client.post(
        "/api/surveys",
        json={"project_id": "test", "rooms": [{"name": "客厅", "room_type": "living_room", "width": 5, "length": 5}]},
    )
    assert resp.status_code == 401

import pytest
from httpx import AsyncClient


async def _register_and_get_token(client: AsyncClient, phone: str = "13900001001") -> str:
    resp = await client.post(
        "/api/auth/register",
        json={
            "phone": phone,
            "name": "项目测试用户",
            "password": "test123456",
        },
    )
    return resp.json()["access_token"]


@pytest.mark.asyncio
async def test_create_project(client: AsyncClient):
    token = await _register_and_get_token(client)
    headers = {"Authorization": f"Bearer {token}"}

    response = await client.post(
        "/api/projects",
        json={
            "name": "测试项目-朝阳小区",
            "address": "北京市朝阳区xx路xx号",
            "total_area": 126.0,
            "floors": [
                {
                    "name": "1层",
                    "floor_number": 1,
                    "area": 126.0,
                    "rooms": [
                        {"name": "客厅", "room_type": "living_room", "area": 35.0},
                        {"name": "主卧", "room_type": "bedroom", "area": 20.0},
                        {"name": "厨房", "room_type": "kitchen", "area": 10.0},
                    ],
                }
            ],
        },
        headers=headers,
    )
    assert response.status_code == 201
    data = response.json()
    assert data["name"] == "测试项目-朝阳小区"
    assert data["total_area"] == 126.0
    assert len(data["floors"]) == 1
    assert len(data["floors"][0]["rooms"]) == 3


@pytest.mark.asyncio
async def test_list_projects(client: AsyncClient):
    token = await _register_and_get_token(client)
    headers = {"Authorization": f"Bearer {token}"}

    await client.post(
        "/api/projects",
        json={"name": "项目A", "total_area": 80.0},
        headers=headers,
    )
    await client.post(
        "/api/projects",
        json={"name": "项目B", "total_area": 120.0},
        headers=headers,
    )

    response = await client.get("/api/projects", headers=headers)
    assert response.status_code == 200
    data = response.json()
    assert len(data) == 2


@pytest.mark.asyncio
async def test_update_project(client: AsyncClient):
    token = await _register_and_get_token(client)
    headers = {"Authorization": f"Bearer {token}"}

    create_resp = await client.post(
        "/api/projects",
        json={"name": "原始项目", "total_area": 100.0},
        headers=headers,
    )
    project_id = create_resp.json()["id"]

    response = await client.patch(
        f"/api/projects/{project_id}",
        json={"name": "已更新项目", "status": "in_progress"},
        headers=headers,
    )
    assert response.status_code == 200
    data = response.json()
    assert data["name"] == "已更新项目"
    assert data["status"] == "in_progress"


@pytest.mark.asyncio
async def test_delete_project(client: AsyncClient):
    token = await _register_and_get_token(client)
    headers = {"Authorization": f"Bearer {token}"}

    create_resp = await client.post(
        "/api/projects",
        json={"name": "待删除项目", "total_area": 80.0},
        headers=headers,
    )
    project_id = create_resp.json()["id"]

    response = await client.delete(f"/api/projects/{project_id}", headers=headers)
    assert response.status_code == 204

    response = await client.get(f"/api/projects/{project_id}", headers=headers)
    assert response.status_code == 404

import pytest
from httpx import AsyncClient


async def _register_and_login(client: AsyncClient) -> str:
    resp = await client.post(
        "/api/auth/register",
        json={"phone": "13900003001", "name": "户型测试用户", "password": "test123456"},
    )
    return resp.json()["access_token"]


async def _create_project(client: AsyncClient, headers: dict) -> str:
    resp = await client.post(
        "/api/projects",
        json={"name": "户型测试项目", "total_area": 100.0},
        headers=headers,
    )
    return resp.json()["id"]


async def _create_plan(
    client: AsyncClient,
    headers: dict,
    project_id: str,
    name: str = "测试方案",
) -> str:
    resp = await client.post(
        "/api/floorplans",
        json={
            "project_id": project_id,
            "name": name,
            "data": '{"walls":[]}',
            "wall_height": 2.8,
            "total_area": 80.0,
            "room_count": 2,
        },
        headers=headers,
    )
    return resp.json()["id"]


@pytest.mark.asyncio
async def test_create_floorplan(client: AsyncClient):
    token = await _register_and_login(client)
    headers = {"Authorization": f"Bearer {token}"}
    project_id = await _create_project(client, headers)

    response = await client.post(
        "/api/floorplans",
        json={
            "project_id": project_id,
            "name": "两室一厅",
            "data": '{"walls":[],"rooms":[]}',
            "wall_height": 2.8,
            "total_area": 80.0,
            "room_count": 3,
        },
        headers=headers,
    )
    assert response.status_code == 201
    data = response.json()
    assert data["name"] == "两室一厅"
    assert data["project_id"] == project_id
    assert data["room_count"] == 3
    assert data["wall_height"] == 2.8
    assert data["is_active"] is True


@pytest.mark.asyncio
async def test_list_floorplans(client: AsyncClient):
    token = await _register_and_login(client)
    headers = {"Authorization": f"Bearer {token}"}
    project_id = await _create_project(client, headers)

    await _create_plan(client, headers, project_id, "方案A")
    await _create_plan(client, headers, project_id, "方案B")

    response = await client.get(f"/api/floorplans/project/{project_id}", headers=headers)
    assert response.status_code == 200
    assert len(response.json()) == 2


@pytest.mark.asyncio
async def test_get_floorplan(client: AsyncClient):
    token = await _register_and_login(client)
    headers = {"Authorization": f"Bearer {token}"}
    project_id = await _create_project(client, headers)
    plan_id = await _create_plan(client, headers, project_id, "查找方案")

    response = await client.get(f"/api/floorplans/{plan_id}", headers=headers)
    assert response.status_code == 200
    assert response.json()["name"] == "查找方案"


@pytest.mark.asyncio
async def test_get_floorplan_not_found(client: AsyncClient):
    token = await _register_and_login(client)
    headers = {"Authorization": f"Bearer {token}"}

    response = await client.get("/api/floorplans/nonexistent-id", headers=headers)
    assert response.status_code == 404


@pytest.mark.asyncio
async def test_update_floorplan(client: AsyncClient):
    token = await _register_and_login(client)
    headers = {"Authorization": f"Bearer {token}"}
    project_id = await _create_project(client, headers)
    plan_id = await _create_plan(client, headers, project_id, "原方案")

    response = await client.put(
        f"/api/floorplans/{plan_id}",
        json={
            "project_id": project_id,
            "name": "更新方案",
            "data": '{"walls":[],"rooms":[]}',
            "wall_height": 3.0,
            "total_area": 90.0,
            "room_count": 4,
        },
        headers=headers,
    )
    assert response.status_code == 200
    data = response.json()
    assert data["name"] == "更新方案"
    assert data["wall_height"] == 3.0
    assert data["total_area"] == 90.0
    assert data["room_count"] == 4


@pytest.mark.asyncio
async def test_delete_floorplan(client: AsyncClient):
    token = await _register_and_login(client)
    headers = {"Authorization": f"Bearer {token}"}
    project_id = await _create_project(client, headers)
    plan_id = await _create_plan(client, headers, project_id, "删除方案")

    response = await client.delete(f"/api/floorplans/{plan_id}", headers=headers)
    assert response.status_code == 204

    # 软删除：列表接口不再返回该方案
    list_resp = await client.get(f"/api/floorplans/project/{project_id}", headers=headers)
    assert list_resp.status_code == 200
    assert len(list_resp.json()) == 0

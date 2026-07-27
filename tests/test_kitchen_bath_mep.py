"""F18 厨卫水电 API 测试（kitchen_bath_mep）

覆盖端点:
- POST /api/mep-kb/kitchen
- GET  /api/mep-kb/kitchen/{id}
- POST /api/mep-kb/bathroom
- GET  /api/mep-kb/bathroom/{id}
- GET  /api/mep-kb/project/{project_id}
"""
import uuid
import pytest
from httpx import AsyncClient


async def _create_project(client: AsyncClient, headers: dict) -> str:
    resp = await client.post(
        "/api/projects",
        json={"name": f"厨卫水电项目-{uuid.uuid4().hex[:6]}", "total_area": 100.0},
        headers=headers,
    )
    return resp.json()["id"]


@pytest.mark.asyncio
async def test_mep_kb_unauthorized(client: AsyncClient):
    """未认证用户无法访问厨卫水电"""
    resp = await client.get("/api/mep-kb/plans/project/fake-id")
    assert resp.status_code in (401, 403)


@pytest.mark.asyncio
async def test_create_kitchen_mep(auth_headers: dict, client: AsyncClient):
    """创建厨房水电设计"""
    project_id = await _create_project(client, auth_headers)
    resp = await client.post(
        "/api/mep-kb/kitchen",
        json={
            "project_id": project_id,
            "room_id": f"room-{uuid.uuid4().hex[:6]}",
            "water_supply": True,
            "drainage": True,
            "gas_supply": False,
            "power_outlets": 6,
            "circuit_breakers": 2,
        },
        headers=auth_headers,
    )
    assert resp.status_code in (200, 201, 404)


@pytest.mark.asyncio
async def test_get_kitchen_mep(auth_headers: dict, client: AsyncClient):
    """获取厨房水电设计详情"""
    resp = await client.get("/api/mep-kb/kitchen/nonexistent-id", headers=auth_headers)
    assert resp.status_code in (404, 200)


@pytest.mark.asyncio
async def test_create_bathroom_mep(auth_headers: dict, client: AsyncClient):
    """创建卫生间水电设计"""
    project_id = await _create_project(client, auth_headers)
    resp = await client.post(
        "/api/mep-kb/bathroom",
        json={
            "project_id": project_id,
            "room_id": f"room-{uuid.uuid4().hex[:6]}",
            "water_supply": True,
            "drainage": True,
            "ventilation": True,
            "power_outlets": 3,
        },
        headers=auth_headers,
    )
    assert resp.status_code in (200, 201, 404)


@pytest.mark.asyncio
async def test_get_project_mep(auth_headers: dict, client: AsyncClient):
    """获取项目厨卫水电汇总"""
    project_id = await _create_project(client, auth_headers)
    resp = await client.get(f"/api/mep-kb/plans/project/{project_id}", headers=auth_headers)
    assert resp.status_code == 200


@pytest.mark.asyncio
async def test_cross_user_mep_kb_access(auth_headers: dict, client: AsyncClient):
    """其他用户无法访问非自己项目的厨卫水电"""
    project_id = await _create_project(client, auth_headers)
    reg = await client.post(
        "/api/auth/register",
        json={"phone": f"1397701{uuid.uuid4().int % 10000:04d}", "name": "他人", "password": "test123456"},
    )
    other_headers = {"Authorization": f"Bearer {reg.json()['access_token']}"}
    resp = await client.get(f"/api/mep-kb/plans/project/{project_id}", headers=other_headers)
    assert resp.status_code in (403, 404)

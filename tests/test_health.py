"""A2 智能家居健康监测 API 测试

覆盖端点:
- POST /api/health-monitor/records
- GET  /api/health-monitor/records/project/{project_id}
- GET  /api/health-monitor/report/{project_id}
- POST /api/health-monitor/air-quality
- GET  /api/health-monitor/air-quality/{project_id}
"""
import uuid
import pytest
from httpx import AsyncClient


async def _create_project(client: AsyncClient, headers: dict) -> str:
    resp = await client.post(
        "/api/projects",
        json={"name": f"健康监测项目-{uuid.uuid4().hex[:6]}", "total_area": 100.0},
        headers=headers,
    )
    return resp.json()["id"]


async def _create_scheme(client: AsyncClient, headers: dict, project_id: str) -> str:
    """创建智能家居方案（健康记录需关联 scheme_id，FK 到 smart_home_schemes）"""
    resp = await client.post(
        "/api/smart-home/schemes",
        json={
            "project_id": project_id, "room_name": "客厅",
            "room_type": "living_room", "protocol": "zigbee", "hub_brand": "xiaomi",
        },
        headers=headers,
    )
    assert resp.status_code == 201
    return resp.json()["id"]


@pytest.mark.asyncio
async def test_records_unauthorized(client: AsyncClient):
    """未认证用户无法访问健康监测记录"""
    resp = await client.get("/api/health-monitor/records/project/fake-id")
    assert resp.status_code in (401, 403, 404)


@pytest.mark.asyncio
async def test_record_health_data(auth_headers: dict, client: AsyncClient):
    """创建健康监测记录"""
    project_id = await _create_project(client, auth_headers)
    scheme_id = await _create_scheme(client, auth_headers, project_id)
    resp = await client.post(
        "/api/health-monitor/records",
        json={
            "project_id": project_id,
            "scheme_id": scheme_id,
            "monitor_type": "air_quality",
            "value": {
                "temperature_c": 25.5,
                "humidity_percent": 55.0,
                "pm25_ugm3": 35,
                "co2_ppm": 600,
                "tvoc_ppb": 200,
            },
        },
        headers=auth_headers,
    )
    assert resp.status_code in (200, 201)


@pytest.mark.asyncio
async def test_list_health_records(auth_headers: dict, client: AsyncClient):
    """列出项目健康监测记录"""
    project_id = await _create_project(client, auth_headers)
    scheme_id = await _create_scheme(client, auth_headers, project_id)
    create = await client.post(
        "/api/health-monitor/records",
        json={
            "project_id": project_id,
            "scheme_id": scheme_id,
            "monitor_type": "air_quality",
            "value": {"temperature_c": 22.0, "humidity_percent": 50.0},
        },
        headers=auth_headers,
    )
    assert create.status_code in (200, 201)
    resp = await client.get(f"/api/health-monitor/records/project/{project_id}", headers=auth_headers)
    assert resp.status_code == 200


@pytest.mark.asyncio
async def test_health_report(auth_headers: dict, client: AsyncClient):
    """获取健康监测报告"""
    project_id = await _create_project(client, auth_headers)
    scheme_id = await _create_scheme(client, auth_headers, project_id)
    create = await client.post(
        "/api/health-monitor/records",
        json={
            "project_id": project_id,
            "scheme_id": scheme_id,
            "monitor_type": "air_quality",
            "value": {"temperature_c": 23.0, "humidity_percent": 45.0},
        },
        headers=auth_headers,
    )
    assert create.status_code in (200, 201)
    resp = await client.get(f"/api/health-monitor/report/{project_id}", headers=auth_headers)
    assert resp.status_code == 200


@pytest.mark.asyncio
async def test_record_air_quality(auth_headers: dict, client: AsyncClient):
    """创建空气质量记录"""
    project_id = await _create_project(client, auth_headers)
    scheme_id = await _create_scheme(client, auth_headers, project_id)
    resp = await client.post(
        "/api/health-monitor/air-quality",
        json={
            "project_id": project_id,
            "scheme_id": scheme_id,
            "room_name": "客厅",
            "pm25": 25,
            "co2": 500,
            "tvoc": 150,
            "formaldehyde": 0.05,
        },
        headers=auth_headers,
    )
    assert resp.status_code in (200, 201)


@pytest.mark.asyncio
async def test_cross_user_health_access(auth_headers: dict, client: AsyncClient):
    """其他用户无法访问非自己项目的健康数据"""
    project_id = await _create_project(client, auth_headers)
    reg = await client.post(
        "/api/auth/register",
        json={"phone": f"1393301{uuid.uuid4().int % 10000:04d}", "name": "他人", "password": "test123456"},
    )
    other_headers = {"Authorization": f"Bearer {reg.json()['access_token']}"}
    resp = await client.get(f"/api/health-monitor/records/project/{project_id}", headers=other_headers)
    assert resp.status_code in (403, 404)

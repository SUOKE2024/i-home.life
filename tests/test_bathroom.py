"""Tests for bathroom API endpoints.

覆盖端点:
- POST /api/bathroom/designs              (创建卫生间设计)
- GET  /api/bathroom/designs/project/{id}
- GET  /api/bathroom/designs/{id}
- POST /api/bathroom/designs/{id}/auto-layout
- GET  /api/bathroom/designs/{id}/drain
- GET  /api/bathroom/designs/{id}/waterproof
- GET  /api/bathroom/designs/{id}/ventilation
- POST /api/bathroom/designs/{id}/fixtures
- GET  /api/bathroom/designs/{id}/fixtures
- DELETE /api/bathroom/fixtures/{id}
- DELETE /api/bathroom/designs/{id}
"""
import uuid

import pytest
from httpx import AsyncClient


async def _create_project(client: AsyncClient, headers: dict, name: str = "卫生间设计项目") -> str:
    resp = await client.post(
        "/api/projects", json={"name": name, "total_area": 100.0}, headers=headers,
    )
    return resp.json()["id"]


async def _register_user(client: AsyncClient, phone: str) -> dict:
    resp = await client.post(
        "/api/auth/register",
        json={"phone": phone, "name": "卫生间测试用户", "password": "test123456"},
    )
    assert resp.status_code == 201
    return {"Authorization": f"Bearer {resp.json()['access_token']}"}


@pytest.mark.asyncio
async def test_bathroom_requires_auth(client: AsyncClient):
    """未认证请求卫生间设计接口返回 401"""
    resp = await client.get("/api/bathroom/designs/project/fake-id")
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_create_bathroom_design(client: AsyncClient, auth_headers: dict):
    """创建卫生间设计方案"""
    project_id = await _create_project(client, auth_headers)

    resp = await client.post(
        "/api/bathroom/designs",
        json={
            "project_id": project_id,
            "room_name": "主卫",
            "layout_type": "dry_wet_separation",
            "room_width": 2.5,
            "room_length": 3.0,
            "ceiling_height": 2.6,
            "floor_drain_count": 2,
            "has_natural_window": True,
        },
        headers=auth_headers,
    )
    assert resp.status_code == 201
    data = resp.json()
    assert "id" in data
    assert data["layout_type"] == "dry_wet_separation"
    assert data["room_name"] == "主卫"


@pytest.mark.asyncio
async def test_list_bathroom_designs(client: AsyncClient, auth_headers: dict):
    """列出项目卫生间设计"""
    project_id = await _create_project(client, auth_headers)

    for layout in ("dry_wet_separation", "three_separation"):
        await client.post(
            "/api/bathroom/designs",
            json={
                "project_id": project_id,
                "room_name": f"卫生间-{layout}",
                "layout_type": layout,
                "room_width": 2.0,
                "room_length": 3.0,
            },
            headers=auth_headers,
        )

    resp = await client.get(
        f"/api/bathroom/designs/project/{project_id}",
        headers=auth_headers,
    )
    assert resp.status_code == 200
    designs = resp.json()
    assert len(designs) >= 2


@pytest.mark.asyncio
async def test_get_bathroom_design_detail(client: AsyncClient, auth_headers: dict):
    """获取卫生间设计详情"""
    project_id = await _create_project(client, auth_headers)
    create_resp = await client.post(
        "/api/bathroom/designs",
        json={
            "project_id": project_id,
            "room_name": "次卫",
            "layout_type": "dry_wet_separation",
            "room_width": 2.0,
            "room_length": 2.5,
            "floor_drain_count": 1,
            "waterproof_height_mm": 1800,
        },
        headers=auth_headers,
    )
    design_id = create_resp.json()["id"]

    resp = await client.get(
        f"/api/bathroom/designs/{design_id}",
        headers=auth_headers,
    )
    assert resp.status_code == 200
    assert resp.json()["id"] == design_id


@pytest.mark.asyncio
async def test_bathroom_foreign_project_blocked(client: AsyncClient, auth_headers: dict, auth_token: str):
    """用户不能访问他人项目的卫生间设计"""
    project_id_a = await _create_project(client, auth_headers)

    phone_b = f"1392{str(uuid.uuid4().int)[:7]}"
    headers_b = await _register_user(client, phone_b)

    resp = await client.get(
        f"/api/bathroom/designs/project/{project_id_a}",
        headers=headers_b,
    )
    assert resp.status_code == 403


@pytest.mark.asyncio
async def test_bathroom_auto_layout(client: AsyncClient, auth_headers: dict):
    """自动布局生成卫浴设备"""
    project_id = await _create_project(client, auth_headers)
    create_resp = await client.post(
        "/api/bathroom/designs",
        json={
            "project_id": project_id,
            "room_name": "主卫",
            "layout_type": "dry_wet_separation",
            "room_width": 2.5,
            "room_length": 3.0,
        },
        headers=auth_headers,
    )
    design_id = create_resp.json()["id"]

    resp = await client.post(
        f"/api/bathroom/designs/{design_id}/auto-layout",
        headers=auth_headers,
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["design_id"] == design_id
    assert "fixtures" in data
    assert data["total"] > 0


@pytest.mark.asyncio
async def test_bathroom_drain_slope(client: AsyncClient, auth_headers: dict):
    """地漏坡度计算"""
    project_id = await _create_project(client, auth_headers)
    create_resp = await client.post(
        "/api/bathroom/designs",
        json={
            "project_id": project_id,
            "room_name": "主卫",
            "layout_type": "dry_wet_separation",
            "room_width": 2.5,
            "room_length": 3.0,
            "drain_slope_percent": 1.5,
        },
        headers=auth_headers,
    )
    design_id = create_resp.json()["id"]

    resp = await client.get(
        f"/api/bathroom/designs/{design_id}/drain",
        headers=auth_headers,
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["design_id"] == design_id


@pytest.mark.asyncio
async def test_bathroom_waterproof_validation(client: AsyncClient, auth_headers: dict):
    """防水规范校验"""
    project_id = await _create_project(client, auth_headers)
    create_resp = await client.post(
        "/api/bathroom/designs",
        json={
            "project_id": project_id,
            "room_name": "主卫",
            "layout_type": "dry_wet_separation",
            "room_width": 2.5,
            "room_length": 3.0,
            "waterproof_height_mm": 1800,
        },
        headers=auth_headers,
    )
    design_id = create_resp.json()["id"]

    resp = await client.get(
        f"/api/bathroom/designs/{design_id}/waterproof",
        headers=auth_headers,
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["design_id"] == design_id


@pytest.mark.asyncio
async def test_bathroom_ventilation(client: AsyncClient, auth_headers: dict):
    """通风分析"""
    project_id = await _create_project(client, auth_headers)
    create_resp = await client.post(
        "/api/bathroom/designs",
        json={
            "project_id": project_id,
            "room_name": "主卫",
            "layout_type": "dry_wet_separation",
            "room_width": 2.5,
            "room_length": 3.0,
            "has_natural_window": True,
            "window_area_m2": 0.6,
            "mechanical_vent_airflow": 80.0,
        },
        headers=auth_headers,
    )
    design_id = create_resp.json()["id"]

    resp = await client.get(
        f"/api/bathroom/designs/{design_id}/ventilation",
        headers=auth_headers,
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["design_id"] == design_id


@pytest.mark.asyncio
async def test_bathroom_fixture_crud(client: AsyncClient, auth_headers: dict):
    """卫浴设备 CRUD"""
    project_id = await _create_project(client, auth_headers)
    create_resp = await client.post(
        "/api/bathroom/designs",
        json={
            "project_id": project_id,
            "room_name": "主卫",
            "layout_type": "dry_wet_separation",
            "room_width": 2.5,
            "room_length": 3.0,
        },
        headers=auth_headers,
    )
    design_id = create_resp.json()["id"]

    # 添加设备
    add_resp = await client.post(
        f"/api/bathroom/designs/{design_id}/fixtures",
        json={
            "design_id": design_id,
            "fixture_type": "toilet",
            "width": 400.0,
            "depth": 700.0,
            "height": 480.0,
            "brand": "测试品牌",
            "model": "TH-400",
        },
        headers=auth_headers,
    )
    assert add_resp.status_code == 201
    fixture = add_resp.json()
    assert fixture["fixture_type"] == "toilet"

    # 列出设备
    list_resp = await client.get(
        f"/api/bathroom/designs/{design_id}/fixtures",
        headers=auth_headers,
    )
    assert list_resp.status_code == 200
    assert len(list_resp.json()) >= 1

    # 删除设备
    del_resp = await client.delete(
        f"/api/bathroom/fixtures/{fixture['id']}",
        headers=auth_headers,
    )
    assert del_resp.status_code == 204


@pytest.mark.asyncio
async def test_delete_bathroom_design(client: AsyncClient, auth_headers: dict):
    """删除卫生间设计"""
    project_id = await _create_project(client, auth_headers)
    create_resp = await client.post(
        "/api/bathroom/designs",
        json={
            "project_id": project_id,
            "room_name": "客卫",
            "layout_type": "dry_wet_separation",
            "room_width": 2.0,
            "room_length": 2.5,
        },
        headers=auth_headers,
    )
    design_id = create_resp.json()["id"]

    del_resp = await client.delete(
        f"/api/bathroom/designs/{design_id}",
        headers=auth_headers,
    )
    assert del_resp.status_code == 204

    get_resp = await client.get(
        f"/api/bathroom/designs/{design_id}",
        headers=auth_headers,
    )
    assert get_resp.status_code == 404


@pytest.mark.asyncio
async def test_bathroom_design_not_found(client: AsyncClient, auth_headers: dict):
    """查询不存在的卫生间设计返回 404"""
    resp = await client.get(
        f"/api/bathroom/designs/non-existent-id",
        headers=auth_headers,
    )
    assert resp.status_code == 404

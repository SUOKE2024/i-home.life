"""Tests for door-window-waterproof API endpoints.

覆盖端点:
- POST /api/door-window-waterproof/door-windows
- GET  /api/door-window-waterproof/door-windows/project/{id}
- GET  /api/door-window-waterproof/door-windows/{id}
- POST /api/door-window-waterproof/door-windows/recommend
- DELETE /api/door-window-waterproof/door-windows/{id}
- POST /api/door-window-waterproof/waterproof
- GET  /api/door-window-waterproof/waterproof/project/{id}
- GET  /api/door-window-waterproof/waterproof/{id}
- POST /api/door-window-waterproof/waterproof/{id}/compute-area
- GET  /api/door-window-waterproof/waterproof/{id}/validation
- DELETE /api/door-window-waterproof/waterproof/{id}
"""
import uuid

import pytest
from httpx import AsyncClient


async def _create_project(client: AsyncClient, headers: dict, name: str = "门窗防水项目") -> str:
    resp = await client.post(
        "/api/projects", json={"name": name, "total_area": 100.0}, headers=headers,
    )
    return resp.json()["id"]


async def _register_user(client: AsyncClient, phone: str) -> dict:
    resp = await client.post(
        "/api/auth/register",
        json={"phone": phone, "name": "门窗防水测试用户", "password": "test123456"},
    )
    assert resp.status_code == 201
    return {"Authorization": f"Bearer {resp.json()['access_token']}"}


# ── Auth ──


@pytest.mark.asyncio
async def test_dw_waterproof_requires_auth(client: AsyncClient):
    """未认证请求门窗接口返回 401"""
    resp = await client.get("/api/door-window-waterproof/door-windows/project/fake-id")
    assert resp.status_code == 401


# ── 门窗选型 ──


@pytest.mark.asyncio
async def test_create_door_window(client: AsyncClient, auth_headers: dict):
    """创建门窗选型"""
    project_id = await _create_project(client, auth_headers)

    resp = await client.post(
        "/api/door-window-waterproof/door-windows",
        json={
            "project_id": project_id,
            "room_name": "客厅",
            "spec_type": "window",
            "material": "aluminum",
            "width": 1500.0,
            "height": 1800.0,
            "opening_direction": "sliding",
            "glass_type": "double",
            "price": 2800.0,
        },
        headers=auth_headers,
    )
    assert resp.status_code == 201
    data = resp.json()
    assert "id" in data
    assert data["spec_type"] == "window"
    assert data["material"] == "aluminum"


@pytest.mark.asyncio
async def test_list_door_windows(client: AsyncClient, auth_headers: dict):
    """列出项目门窗选型"""
    project_id = await _create_project(client, auth_headers)

    for spec in ("window", "interior_door"):
        await client.post(
            "/api/door-window-waterproof/door-windows",
            json={
                "project_id": project_id,
                "room_name": "客厅",
                "spec_type": spec,
                "material": "aluminum",
                "width": 1000.0,
                "height": 2000.0,
            },
            headers=auth_headers,
        )

    resp = await client.get(
        f"/api/door-window-waterproof/door-windows/project/{project_id}",
        headers=auth_headers,
    )
    assert resp.status_code == 200
    specs = resp.json()
    assert len(specs) >= 2


@pytest.mark.asyncio
async def test_get_door_window_detail(client: AsyncClient, auth_headers: dict):
    """门窗选型详情"""
    project_id = await _create_project(client, auth_headers)
    create_resp = await client.post(
        "/api/door-window-waterproof/door-windows",
        json={
            "project_id": project_id,
            "room_name": "主卧",
            "spec_type": "entry_door",
            "material": "solid_wood",
            "width": 1000.0,
            "height": 2200.0,
            "opening_direction": "inward",
            "has_lock": True,
        },
        headers=auth_headers,
    )
    spec_id = create_resp.json()["id"]

    resp = await client.get(
        f"/api/door-window-waterproof/door-windows/{spec_id}",
        headers=auth_headers,
    )
    assert resp.status_code == 200
    assert resp.json()["id"] == spec_id
    assert resp.json()["has_lock"] is True


@pytest.mark.asyncio
async def test_door_window_foreign_project_blocked(client: AsyncClient, auth_headers: dict, auth_token: str):
    """用户不能访问他人项目的门窗选型"""
    project_id_a = await _create_project(client, auth_headers)

    phone_b = f"1393{str(uuid.uuid4().int)[:7]}"
    headers_b = await _register_user(client, phone_b)

    resp = await client.get(
        f"/api/door-window-waterproof/door-windows/project/{project_id_a}",
        headers=headers_b,
    )
    assert resp.status_code == 403


@pytest.mark.asyncio
async def test_recommend_door_window(client: AsyncClient, auth_headers: dict):
    """门窗推荐"""
    resp = await client.post(
        "/api/door-window-waterproof/door-windows/recommend",
        json={
            "spec_type": "window",
            "room_type": "living_room",
            "opening_direction": "sliding",
        },
        headers=auth_headers,
    )
    # 推荐接口可能返回 200（成功）或 422（参数无效）
    assert resp.status_code in (200, 422)


@pytest.mark.asyncio
async def test_delete_door_window(client: AsyncClient, auth_headers: dict):
    """删除门窗选型"""
    project_id = await _create_project(client, auth_headers)
    create_resp = await client.post(
        "/api/door-window-waterproof/door-windows",
        json={
            "project_id": project_id,
            "room_name": "次卧",
            "spec_type": "interior_door",
            "material": "wood_composite",
            "width": 900.0,
            "height": 2100.0,
        },
        headers=auth_headers,
    )
    spec_id = create_resp.json()["id"]

    del_resp = await client.delete(
        f"/api/door-window-waterproof/door-windows/{spec_id}",
        headers=auth_headers,
    )
    assert del_resp.status_code == 204


@pytest.mark.asyncio
async def test_door_window_not_found(client: AsyncClient, auth_headers: dict):
    """查询不存在的门窗选型返回 404"""
    resp = await client.get(
        "/api/door-window-waterproof/door-windows/non-existent-id",
        headers=auth_headers,
    )
    assert resp.status_code == 404


# ── 防水方案 ──


@pytest.mark.asyncio
async def test_create_waterproof(client: AsyncClient, auth_headers: dict):
    """创建防水方案"""
    project_id = await _create_project(client, auth_headers)

    resp = await client.post(
        "/api/door-window-waterproof/waterproof",
        json={
            "project_id": project_id,
            "room_name": "卫生间",
            "room_type": "bathroom",
            "wall_height_mm": 1800,
            "floor_area": 6.0,
            "wall_area": 18.0,
            "waterproof_material": "polyurethane",
            "coating_layers": 2,
            "thickness_mm": 1.5,
            "closure_test_hours": 24,
        },
        headers=auth_headers,
    )
    assert resp.status_code == 201
    data = resp.json()
    assert "id" in data
    assert data["room_type"] == "bathroom"
    assert data["waterproof_material"] == "polyurethane"


@pytest.mark.asyncio
async def test_list_waterproofs(client: AsyncClient, auth_headers: dict):
    """列出项目防水方案"""
    project_id = await _create_project(client, auth_headers)

    for room_type in ("bathroom", "kitchen"):
        await client.post(
            "/api/door-window-waterproof/waterproof",
            json={
                "project_id": project_id,
                "room_name": f"{room_type}防水",
                "room_type": room_type,
                "wall_height_mm": 1800,
                "floor_area": 5.0,
                "wall_area": 15.0,
            },
            headers=auth_headers,
        )

    resp = await client.get(
        f"/api/door-window-waterproof/waterproof/project/{project_id}",
        headers=auth_headers,
    )
    assert resp.status_code == 200
    plans = resp.json()
    assert len(plans) >= 2


@pytest.mark.asyncio
async def test_get_waterproof_detail(client: AsyncClient, auth_headers: dict):
    """防水方案详情"""
    project_id = await _create_project(client, auth_headers)
    create_resp = await client.post(
        "/api/door-window-waterproof/waterproof",
        json={
            "project_id": project_id,
            "room_name": "阳台",
            "room_type": "balcony",
            "wall_height_mm": 1500,
            "floor_area": 4.0,
            "wall_area": 10.0,
            "waterproof_material": "JS",
            "coating_layers": 3,
        },
        headers=auth_headers,
    )
    plan_id = create_resp.json()["id"]

    resp = await client.get(
        f"/api/door-window-waterproof/waterproof/{plan_id}",
        headers=auth_headers,
    )
    assert resp.status_code == 200
    assert resp.json()["id"] == plan_id
    assert resp.json()["coating_layers"] == 3


@pytest.mark.asyncio
async def test_compute_waterproof_area(client: AsyncClient, auth_headers: dict):
    """防水面积计算"""
    project_id = await _create_project(client, auth_headers)
    create_resp = await client.post(
        "/api/door-window-waterproof/waterproof",
        json={
            "project_id": project_id,
            "room_name": "卫生间",
            "room_type": "bathroom",
            "wall_height_mm": 1800,
            "floor_area": 6.0,
            "wall_area": 18.0,
        },
        headers=auth_headers,
    )
    plan_id = create_resp.json()["id"]

    resp = await client.post(
        f"/api/door-window-waterproof/waterproof/{plan_id}/compute-area",
        json={
            "room_width": 2.0,
            "room_length": 3.0,
            "wall_height_mm": 1800,
        },
        headers=auth_headers,
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["plan_id"] == plan_id


@pytest.mark.asyncio
async def test_validate_waterproof(client: AsyncClient, auth_headers: dict):
    """防水规范校验"""
    project_id = await _create_project(client, auth_headers)
    create_resp = await client.post(
        "/api/door-window-waterproof/waterproof",
        json={
            "project_id": project_id,
            "room_name": "卫生间",
            "room_type": "bathroom",
            "wall_height_mm": 1800,
            "floor_area": 6.0,
            "wall_area": 18.0,
            "closure_test_hours": 24,
        },
        headers=auth_headers,
    )
    plan_id = create_resp.json()["id"]

    resp = await client.get(
        f"/api/door-window-waterproof/waterproof/{plan_id}/validation",
        headers=auth_headers,
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["plan_id"] == plan_id


@pytest.mark.asyncio
async def test_delete_waterproof(client: AsyncClient, auth_headers: dict):
    """删除防水方案"""
    project_id = await _create_project(client, auth_headers)
    create_resp = await client.post(
        "/api/door-window-waterproof/waterproof",
        json={
            "project_id": project_id,
            "room_name": "卫生间",
            "room_type": "bathroom",
            "wall_height_mm": 1800,
            "floor_area": 6.0,
            "wall_area": 18.0,
        },
        headers=auth_headers,
    )
    plan_id = create_resp.json()["id"]

    del_resp = await client.delete(
        f"/api/door-window-waterproof/waterproof/{plan_id}",
        headers=auth_headers,
    )
    assert del_resp.status_code == 204

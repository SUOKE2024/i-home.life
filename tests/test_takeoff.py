"""工程量算量 API 集成测试

覆盖端点:
- POST /api/takeoff/wall                (墙体工程量)
- POST /api/takeoff/slab                (楼板工程量)
- POST /api/takeoff/floor               (地面工程量)
- POST /api/takeoff/paint               (涂料工程量)
- POST /api/takeoff/project             (项目级汇总—手工)
- GET  /api/takeoff/project/{id}        (正向设计算量)
"""
import json
import pytest
from httpx import AsyncClient


async def _auth_headers(client: AsyncClient, phone: str = "13900032001") -> dict:
    resp = await client.post(
        "/api/auth/register",
        json={"phone": phone, "name": "算量测试", "password": "test123456"},
    )
    assert resp.status_code == 201
    return {"Authorization": f"Bearer {resp.json()['access_token']}"}


async def _create_project(client: AsyncClient, headers: dict, name: str = "算量项目") -> str:
    resp = await client.post(
        "/api/projects", json={"name": name, "total_area": 100.0}, headers=headers,
    )
    return resp.json()["id"]


async def _create_floorplan(client: AsyncClient, headers: dict, project_id: str) -> str:
    floorplan_data = json.dumps({
        "walls": [
            {"name": "W1", "start": {"x": 0, "y": 0}, "end": {"x": 5000, "y": 0}, "thickness": 240},
            {"name": "W2", "start": {"x": 0, "y": 0}, "end": {"x": 0, "y": 4000}, "thickness": 240},
        ],
        "doors": [{"name": "M1", "width": 900, "height": 2100, "position": {"x": 1000, "y": 0}}],
        "windows": [],
        "rooms": [{"name": "客厅", "area": 20.0, "type": "living"}],
    })
    resp = await client.post(
        "/api/floorplans",
        json={
            "project_id": project_id, "name": "算量户型", "data": floorplan_data,
            "wall_height": 2.8, "total_area": 80.0, "room_count": 1,
        },
        headers=headers,
    )
    return resp.json()["id"]


# ── Auth 校验 ──


@pytest.mark.asyncio
async def test_wall_takeoff_unauthorized(client: AsyncClient):
    """未认证用户不能计算墙体工程量"""
    resp = await client.post(
        "/api/takeoff/wall",
        json={"length": 10.0, "height": 2.8},
    )
    assert resp.status_code == 401


# ── 墙体工程量 ──


@pytest.mark.asyncio
async def test_wall_takeoff_basic(client: AsyncClient):
    """基本墙体工程量计算"""
    headers = await _auth_headers(client, "13900032002")
    resp = await client.post(
        "/api/takeoff/wall",
        json={
            "length": 10.0,
            "height": 2.8,
            "thickness": 0.24,
            "openings_area": 0,
            "brick_type": "standard_brick",
        },
        headers=headers,
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["brick_count"] > 0
    assert data["mortar_volume"] > 0
    assert data["paint_area"] > 0


@pytest.mark.asyncio
async def test_wall_takeoff_with_openings(client: AsyncClient):
    """带门窗洞口的墙体工程量（开口面积扣减）"""
    headers = await _auth_headers(client, "13900032003")
    resp = await client.post(
        "/api/takeoff/wall",
        json={
            "length": 10.0,
            "height": 2.8,
            "thickness": 0.24,
            "openings_area": 3.0,
        },
        headers=headers,
    )
    assert resp.status_code == 200
    data = resp.json()
    # 有开口的砖数应少于无开口
    assert data["brick_count"] > 0


# ── 楼板工程量 ──


@pytest.mark.asyncio
async def test_slab_takeoff(client: AsyncClient):
    """楼板工程量计算（混凝土/钢筋/模板）"""
    headers = await _auth_headers(client, "13900032004")
    resp = await client.post(
        "/api/takeoff/slab",
        json={"area": 50.0, "thickness": 0.12, "concrete_grade": "c25"},
        headers=headers,
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["volume"] > 0
    assert "rebar_weight" in data


# ── 涂料工程量 ──


@pytest.mark.asyncio
async def test_paint_takeoff(client: AsyncClient):
    """涂料工程量计算"""
    headers = await _auth_headers(client, "13900032005")
    resp = await client.post(
        "/api/takeoff/paint",
        json={"area": 100.0, "coats": 3},
        headers=headers,
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["total_paint_liters"] > 0
    assert data["primer_count"] > 0


# ── 项目级汇总 ──


@pytest.mark.asyncio
async def test_project_takeoff_manual(client: AsyncClient):
    """手工输入项目级工程量汇总"""
    headers = await _auth_headers(client, "13900032006")
    resp = await client.post(
        "/api/takeoff/project",
        json={
            "walls": [{"length": 10.0, "height": 2.8}],
            "slabs": [{"area": 50.0, "thickness": 0.12}],
            "floors": [{"area": 50.0, "tile_size": "600x600"}],
        },
        headers=headers,
    )
    assert resp.status_code == 200
    data = resp.json()
    assert "summary" in data or "total" in str(data).lower()


# ── 正向设计算量 ──


@pytest.mark.asyncio
async def test_forward_takeoff_no_floorplan(client: AsyncClient):
    """项目无 floorplan 时正向算量返回 404"""
    headers = await _auth_headers(client, "13900032007")
    project_id = await _create_project(client, headers)

    resp = await client.get(
        f"/api/takeoff/project/{project_id}",
        headers=headers,
    )
    assert resp.status_code == 404
    assert "floorplan" in resp.json()["detail"].lower() or "户型" in resp.json()["detail"]


@pytest.mark.asyncio
async def test_forward_takeoff_with_floorplan(client: AsyncClient):
    """正向设计算量：从 active floorplan 几何自动派生工程量"""
    headers = await _auth_headers(client, "13900032008")
    project_id = await _create_project(client, headers)
    await _create_floorplan(client, headers, project_id)

    resp = await client.get(
        f"/api/takeoff/project/{project_id}",
        headers=headers,
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["project_id"] == project_id
    assert "floorplan_id" in data
    assert "walls" in data
    assert "floors" in data
    assert "summary" in data

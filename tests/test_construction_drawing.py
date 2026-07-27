"""施工图自动生成 API 集成测试

覆盖端点:
- GET /api/construction-drawing/{project_id}/floor-plan  (平面布置图)
- GET /api/construction-drawing/{project_id}/elevation     (立面图)
- GET /api/construction-drawing/{project_id}/all           (全套施工图)
"""
import json
import pytest
from httpx import AsyncClient


async def _auth_headers(client: AsyncClient, phone: str = "13900031001") -> dict:
    resp = await client.post(
        "/api/auth/register",
        json={"phone": phone, "name": "施工图测试", "password": "test123456"},
    )
    assert resp.status_code == 201
    return {"Authorization": f"Bearer {resp.json()['access_token']}"}


async def _create_project(client: AsyncClient, headers: dict, name: str = "施工图项目") -> str:
    resp = await client.post(
        "/api/projects", json={"name": name, "total_area": 100.0}, headers=headers,
    )
    return resp.json()["id"]


async def _create_floorplan(client: AsyncClient, headers: dict, project_id: str, name: str = "户型A") -> str:
    floorplan_data = json.dumps({
        "walls": [
            {"name": "W1", "start": {"x": 0, "y": 0}, "end": {"x": 5000, "y": 0}, "thickness": 240},
            {"name": "W2", "start": {"x": 0, "y": 0}, "end": {"x": 0, "y": 4000}, "thickness": 240},
        ],
        "doors": [{"name": "M1", "width": 900, "height": 2100, "position": {"x": 1000, "y": 0}}],
        "windows": [{"name": "C1", "width": 1500, "height": 1500, "position": {"x": 3000, "y": 0}}],
        "rooms": [{"name": "客厅", "area": 20.0, "type": "living", "center": {"x": 2000, "y": 1500}}],
    })
    resp = await client.post(
        "/api/floorplans",
        json={
            "project_id": project_id, "name": name, "data": floorplan_data,
            "wall_height": 2.8, "total_area": 80.0, "room_count": 1,
        },
        headers=headers,
    )
    return resp.json()["id"]


# ── Auth 校验 ──


@pytest.mark.asyncio
async def test_floor_plan_unauthorized(client: AsyncClient):
    """未认证用户不能获取施工图"""
    resp = await client.get("/api/construction-drawing/fake-id/floor-plan")
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_all_drawings_unauthorized(client: AsyncClient):
    """未认证用户不能获取全套施工图"""
    resp = await client.get("/api/construction-drawing/fake-id/all")
    assert resp.status_code == 401


# ── 平面布置图 ──


@pytest.mark.asyncio
async def test_floor_plan_no_floorplan(client: AsyncClient):
    """项目无 floorplan 时返回 404"""
    headers = await _auth_headers(client, "13900031002")
    project_id = await _create_project(client, headers)

    resp = await client.get(
        f"/api/construction-drawing/{project_id}/floor-plan",
        headers=headers,
    )
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_floor_plan_with_floorplan(client: AsyncClient):
    """有 floorplan 时生成平面布置图"""
    headers = await _auth_headers(client, "13900031003")
    project_id = await _create_project(client, headers)
    await _create_floorplan(client, headers, project_id)

    resp = await client.get(
        f"/api/construction-drawing/{project_id}/floor-plan",
        headers=headers,
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["project_id"] == project_id
    assert data["drawing_type"] == "floor_plan"
    assert "svg" in data
    assert len(data["svg"]) > 0
    assert "element_count" in data


@pytest.mark.asyncio
async def test_floor_plan_as_svg(client: AsyncClient):
    """请求 SVG 格式平面图"""
    headers = await _auth_headers(client, "13900031004")
    project_id = await _create_project(client, headers)
    await _create_floorplan(client, headers, project_id)

    resp = await client.get(
        f"/api/construction-drawing/{project_id}/floor-plan?as_svg=true",
        headers=headers,
    )
    assert resp.status_code == 200
    assert resp.headers.get("content-type", "").startswith("image/svg+xml")


# ── 全套施工图 ──


@pytest.mark.asyncio
async def test_all_drawings(client: AsyncClient):
    """生成全套施工图（平面 + 立面列表）"""
    headers = await _auth_headers(client, "13900031005")
    project_id = await _create_project(client, headers)
    await _create_floorplan(client, headers, project_id)

    resp = await client.get(
        f"/api/construction-drawing/{project_id}/all",
        headers=headers,
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["project_id"] == project_id
    assert "floor_plan_svg" in data
    assert "elevation_svgs" in data
    assert isinstance(data["elevation_svgs"], list)


# ── 越权校验 ──


@pytest.mark.asyncio
async def test_foreign_project_blocked(client: AsyncClient):
    """用户不能访问不属于自己的项目的施工图"""
    headers_a = await _auth_headers(client, "13900031006")
    headers_b = await _auth_headers(client, "13900031007")
    project_id_a = await _create_project(client, headers_a)

    resp = await client.get(
        f"/api/construction-drawing/{project_id_a}/all",
        headers=headers_b,
    )
    assert resp.status_code == 403

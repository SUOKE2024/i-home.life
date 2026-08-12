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


# ── 剖面图 ──


@pytest.mark.asyncio
async def test_section_drawing(client: AsyncClient):
    """有 floorplan 时生成剖面图 SVG（含剖切标记）"""
    headers = await _auth_headers(client, "13900031008")
    project_id = await _create_project(client, headers)
    await _create_floorplan(client, headers, project_id)

    resp = await client.get(
        f"/api/construction-drawing/{project_id}/section",
        headers=headers,
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["drawing_type"] == "section"
    assert "svg" in data
    assert len(data["svg"]) > 0
    assert "剖面" in data["svg"]
    assert "剖切面" in data["svg"]  # 剖面标记


@pytest.mark.asyncio
async def test_section_drawing_with_plane_x(client: AsyncClient):
    """剖切面参数 section_plane={"x": ...} 生效"""
    headers = await _auth_headers(client, "13900031009")
    project_id = await _create_project(client, headers)
    await _create_floorplan(client, headers, project_id)

    resp = await client.get(
        f"/api/construction-drawing/{project_id}/section",
        params={"section_plane": json.dumps({"x": 2500.0})},
        headers=headers,
    )
    assert resp.status_code == 200
    assert "剖切面" in resp.json()["svg"]


@pytest.mark.asyncio
async def test_section_drawing_invalid_plane(client: AsyncClient):
    """非法剖切面参数返回 422"""
    headers = await _auth_headers(client, "13900031010")
    project_id = await _create_project(client, headers)
    await _create_floorplan(client, headers, project_id)

    resp = await client.get(
        f"/api/construction-drawing/{project_id}/section",
        params={"section_plane": "not-json"},
        headers=headers,
    )
    assert resp.status_code == 422


# ── 导出：DXF / PDF ──


@pytest.mark.asyncio
async def test_export_dxf(client: AsyncClient):
    """DXF 导出：返回 DXF 文本（含头与实体）+ 诚实标注（format/engine）"""
    headers = await _auth_headers(client, "13900031011")
    project_id = await _create_project(client, headers)
    await _create_floorplan(client, headers, project_id)

    resp = await client.get(
        f"/api/construction-drawing/{project_id}/floor-plan/export",
        params={"format": "dxf"},
        headers=headers,
    )
    assert resp.status_code == 200
    assert resp.headers.get("content-type", "").startswith("application/dxf")
    # 诚实标注：导出格式与转换引擎
    assert resp.headers.get("x-drawing-format") == "dxf"
    assert resp.headers.get("x-drawing-engine") == "svg_to_dxf"
    body = resp.text
    assert "SECTION" in body
    assert "ENTITIES" in body
    assert "EOF" in body
    assert "LINE" in body
    assert "LWPOLYLINE" in body


@pytest.mark.asyncio
async def test_export_pdf(client: AsyncClient):
    """PDF 导出：依赖缺失 → 501 诚实标注；依赖存在 → 有效 PDF"""
    from app.services.construction_drawing_service import is_pdf_export_available

    headers = await _auth_headers(client, "13900031012")
    project_id = await _create_project(client, headers)
    await _create_floorplan(client, headers, project_id)

    resp = await client.get(
        f"/api/construction-drawing/{project_id}/section/export",
        params={"format": "pdf"},
        headers=headers,
    )
    if is_pdf_export_available():
        assert resp.status_code == 200
        assert resp.headers.get("content-type", "").startswith("application/pdf")
        assert resp.headers.get("x-drawing-format") == "pdf"
        assert resp.headers.get("x-drawing-engine") == "svg_to_pdf"
        assert resp.content[:5] == b"%PDF-"
    else:
        assert resp.status_code == 501
        assert "依赖" in resp.json()["detail"]


@pytest.mark.asyncio
async def test_export_invalid_format(client: AsyncClient):
    """不支持的导出格式返回 422"""
    headers = await _auth_headers(client, "13900031013")
    project_id = await _create_project(client, headers)
    await _create_floorplan(client, headers, project_id)

    resp = await client.get(
        f"/api/construction-drawing/{project_id}/floor-plan/export",
        params={"format": "png"},
        headers=headers,
    )
    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_export_invalid_drawing_type(client: AsyncClient):
    """不支持的图纸类型返回 422"""
    headers = await _auth_headers(client, "13900031014")
    project_id = await _create_project(client, headers)
    await _create_floorplan(client, headers, project_id)

    resp = await client.get(
        f"/api/construction-drawing/{project_id}/bogus/export",
        params={"format": "dxf"},
        headers=headers,
    )
    assert resp.status_code == 422


# ── MEP 水电图叠加（v1.13.5 起默认开启）──


@pytest.mark.asyncio
async def test_all_drawings_mep_overlay_enabled(client: AsyncClient):
    """construction_drawing_mep_enabled=True（默认）时 /all 返回 MEP 叠加 SVG

    从 floorplan 几何派生（纯 Python，零外部依赖）；厨/卫湿区规则标注，
    SVG 内含「占位示意」诚实标注，不伪装真实 MEP 模型数据。
    """
    from app.config import get_settings
    assert get_settings().construction_drawing_mep_enabled is True

    headers = await _auth_headers(client, "13900031015")
    project_id = await _create_project(client, headers)
    # 户型含厨房（湿区）以触发给水/燃气标注
    floorplan_data = json.dumps({
        "walls": [
            {"name": "W1", "start": {"x": 0, "y": 0}, "end": {"x": 5000, "y": 0}, "thickness": 240},
            {"name": "W2", "start": {"x": 0, "y": 0}, "end": {"x": 0, "y": 4000}, "thickness": 240},
        ],
        "doors": [{"name": "M1", "width": 900, "height": 2100, "position": {"x": 1000, "y": 0}}],
        "windows": [{"name": "C1", "width": 1500, "height": 1500, "position": {"x": 3000, "y": 0}}],
        "rooms": [
            {"name": "厨房", "area": 8.0, "type": "kitchen", "center": {"x": 2000, "y": 1500}},
        ],
    })
    resp = await client.post(
        "/api/floorplans",
        json={
            "project_id": project_id, "name": "户型MEP", "data": floorplan_data,
            "wall_height": 2.8, "total_area": 60.0, "room_count": 1,
        },
        headers=headers,
    )
    assert resp.status_code == 201

    resp = await client.get(
        f"/api/construction-drawing/{project_id}/all",
        headers=headers,
    )
    assert resp.status_code == 200
    data = resp.json()
    mep_svg = data.get("mep_overlay_svg", "")
    assert mep_svg, "construction_drawing_mep_enabled=True 时 mep_overlay_svg 不应为空"
    assert "<svg" in mep_svg
    # 诚实标注：MEP 叠加为规则派生占位示意（不伪装真实 MEP 模型数据）
    assert "占位示意" in mep_svg
    assert "给水" in mep_svg


@pytest.mark.asyncio
async def test_all_drawings_mep_overlay_disabled(client: AsyncClient, monkeypatch):
    """construction_drawing_mep_enabled=False 时 /all 返回空串（诚实降级）"""
    from app.config import get_settings
    monkeypatch.setattr(get_settings(), "construction_drawing_mep_enabled", False)

    headers = await _auth_headers(client, "13900031016")
    project_id = await _create_project(client, headers)
    await _create_floorplan(client, headers, project_id)

    resp = await client.get(
        f"/api/construction-drawing/{project_id}/all",
        headers=headers,
    )
    assert resp.status_code == 200
    assert resp.json().get("mep_overlay_svg", "") == ""

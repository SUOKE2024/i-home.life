"""v1.2.0 专业性修复验证测试

P1 AI 渲染诚实降级：render_backend/reconstruction_available/detected_room_type 诚实化
P3 IFC 真实坐标：_wall_placement_point 用 floorplan 真实坐标
"""

import io
import json

import pytest
from httpx import AsyncClient


# ── 辅助 ──────────────────────────────────────────────────

async def _register(client: AsyncClient, phone: str) -> str:
    resp = await client.post(
        "/api/auth/register",
        json={"phone": phone, "name": "专业性测试", "password": "test123456"},
    )
    assert resp.status_code in (200, 201), resp.text
    return resp.json()["access_token"]


# ── P1: AI 渲染诚实降级 ────────────────────────────────────

@pytest.mark.asyncio
async def test_render_2d_honest_degradation(client: AsyncClient):
    """P1: 2D 渲染诚实降级 — render_backend 标识 mock（不再伪装为真实渲染）"""
    token = await _register(client, "13900007801")
    resp = await client.post(
        "/api/ai-render/2d",
        headers={"Authorization": f"Bearer {token}"},
        json={"layout_json": {"rooms": [{"name": "客厅"}]}, "style": "modern"},
    )
    assert resp.status_code == 200, resp.text
    data = resp.json()
    # v1.2.0 新增诚实标识字段
    assert "render_backend" in data
    assert data["render_backend"] == "mock"  # 未配置真实后端时诚实降级
    # 保留兼容字段
    assert "placehold.co" in data["placeholder_image_url"]


@pytest.mark.asyncio
async def test_render_3d_honest_degradation(client: AsyncClient):
    """P1: 3D 渲染诚实降级 — reconstruction_available=False（不再伪造参数为已执行）"""
    token = await _register(client, "13900007802")
    resp = await client.post(
        "/api/ai-render/3d",
        headers={"Authorization": f"Bearer {token}"},
        json={"floorplan": {"rooms": [{"name": "客厅"}]}, "style": "nordic"},
    )
    assert resp.status_code == 200, resp.text
    data = resp.json()
    # v1.2.0 诚实标识：未真实执行 3D 重建
    assert "reconstruction_available" in data
    assert data["reconstruction_available"] is False
    assert data["render_backend"] == "mock"
    # 保留 method 字段向后兼容，但 available=False 诚实标识
    assert data["reconstruction_params"]["method"] == "3dgs"
    assert data["reconstruction_params"]["available"] is False


@pytest.mark.asyncio
async def test_restage_detected_room_unknown(client: AsyncClient):
    """P1: 照片重布置房间检测诚实化 — 不再用 len(photo)%len 伪随机，返回 unknown"""
    token = await _register(client, "13900007803")
    resp = await client.post(
        "/api/ai-render/restage",
        headers={"Authorization": f"Bearer {token}"},
        data={"mode": "inpainting", "style": "japanese"},
        files={"photo": ("photo.jpg", io.BytesIO(b"fake-photo-bytes"), "image/jpeg")},
    )
    assert resp.status_code == 200, resp.text
    data = resp.json()
    # v1.2.0 诚实降级：未启用视觉模型时返回 unknown
    assert data["detected_room_type"] == "unknown"
    assert data["render_backend"] == "mock"


# ── P3: IFC 真实坐标 ────────────────────────────────────────

def test_wall_placement_real_coordinates():
    """P3: ifc_real_placement_enabled=True 时用 floorplan 真实 start 坐标"""
    from app.services.ifc_export_service import _wall_placement_point

    wall = {"start": {"x": 1500, "y": 2000}}
    point = _wall_placement_point(wall, index=0)
    # 真实坐标（mm）：start.x=1500, start.y=2000, z=0
    assert point == (1500.0, 2000.0, 0.0)


def test_wall_placement_fallback_when_disabled(monkeypatch):
    """P3: flag 关闭时回退 i*5000 占位坐标（向后兼容）"""
    from app.services import ifc_export_service

    class _FakeSettings:
        ifc_real_placement_enabled = False

    monkeypatch.setattr(ifc_export_service, "get_settings", lambda: _FakeSettings())

    wall = {"start": {"x": 1500, "y": 2000}}
    point = ifc_export_service._wall_placement_point(wall, index=3)
    # 回退：3 * 5000 = 15000
    assert point == (15000.0, 0.0, 0.0)


def test_opening_placement_real_coordinates():
    """P3: 门窗 placement 用 floorplan position 真实坐标"""
    from app.services.ifc_export_service import _opening_placement_point

    door = {"position": {"x": 3000, "y": 1000}}
    point = _opening_placement_point(door, index=0)
    assert point == (3000.0, 1000.0, 0.0)


def test_window_placement_includes_sill_height():
    """P3: 窗 placement 含窗台高（z 坐标）"""
    from app.services.ifc_export_service import _opening_placement_point

    window = {"position": {"x": 2000, "y": 0}, "sill_height": 900}
    point = _opening_placement_point(window, index=0)
    assert point[0] == 2000.0
    assert point[1] == 0.0
    assert point[2] == 900.0  # 窗台高


# ── P2/P4: 链路贯通端点验证 ────────────────────────────────

@pytest.mark.asyncio
async def test_takeoff_project_endpoint_unauth(client: AsyncClient):
    """P2: 正向算量端点需认证（401）"""
    resp = await client.get("/api/takeoff/project/fake-project-id")
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_construction_drawing_endpoint_unauth(client: AsyncClient):
    """P4: 施工图端点需认证（401）"""
    resp = await client.get("/api/construction-drawing/fake-project-id/all")
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_takeoff_project_no_floorplan(client: AsyncClient):
    """P2: 项目无 floorplan 时返回 404 + 提示"""
    from app.models.user import User
    from app.models.project import Project
    import uuid

    # 直接用 db_session 建项目（避免注册流程）
    token = await _register(client, "13900007804")
    # 通过 API 创建项目
    resp = await client.post(
        "/api/projects",
        json={"name": "算量端点测试", "total_area": 80.0},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 201
    project_id = resp.json()["id"]

    # 无 floorplan → 404
    resp = await client.get(
        f"/api/takeoff/project/{project_id}",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 404
    assert "floorplan" in resp.json()["detail"].lower() or "户型" in resp.json()["detail"]


@pytest.mark.asyncio
async def test_construction_drawing_full_linkage(client: AsyncClient):
    """P4: 端到端链路 — 创建 floorplan → 生成施工图（含墙体/门窗）"""
    token = await _register(client, "13900007805")
    # 创建项目
    resp = await client.post(
        "/api/projects",
        json={"name": "图纸端点测试", "total_area": 100.0},
        headers={"Authorization": f"Bearer {token}"},
    )
    project_id = resp.json()["id"]

    # 创建 floorplan（含墙体/门/窗几何）
    floorplan_data = json.dumps({
        "walls": [
            {"name": "W1", "start": {"x": 0, "y": 0}, "end": {"x": 6000, "y": 0}, "thickness": 240},
            {"name": "W2", "start": {"x": 0, "y": 0}, "end": {"x": 0, "y": 4000}, "thickness": 240},
        ],
        "doors": [{"name": "M1", "width": 900, "height": 2100, "position": {"x": 1000, "y": 0}}],
        "windows": [{"name": "C1", "width": 1500, "height": 1500, "position": {"x": 3000, "y": 0}}],
        "rooms": [{"name": "客厅", "area": 24.0, "type": "living", "center": {"x": 2000, "y": 1500}}],
    })
    resp = await client.post(
        "/api/floorplans",
        headers={"Authorization": f"Bearer {token}"},
        json={
            "project_id": project_id, "name": "端点户型",
            "data": floorplan_data, "wall_height": 2.8,
        },
    )
    assert resp.status_code in (200, 201), resp.text

    # 生成全套施工图
    resp = await client.get(
        f"/api/construction-drawing/{project_id}/all",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 200, resp.text
    data = resp.json()
    assert "<svg" in data["floor_plan_svg"]
    assert "客厅" in data["floor_plan_svg"]
    assert data["element_count"] == 4  # 2墙 + 1门 + 1窗

    # 验证平面图 SVG 端点
    resp = await client.get(
        f"/api/construction-drawing/{project_id}/floor-plan?as_svg=true",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 200
    assert "image/svg+xml" in resp.headers.get("content-type", "")

    # 验证正向算量端点
    resp = await client.get(
        f"/api/takeoff/project/{project_id}",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 200, resp.text
    takeoff = resp.json()
    assert takeoff["summary"]["total_brick_count"] > 0
    assert takeoff["geometry"]["wall_count"] == 2

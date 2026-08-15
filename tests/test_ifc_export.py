"""BIM IFC 导出测试 — structural / design 导出 + 鉴权"""

import json
import os

import pytest
from httpx import AsyncClient

from app.models.user import User
from app.models.project import Project
from app.models.structural import LoadBearingWall, Beam, Column, FloorSlab
from app.models.floorplan import FloorPlan
from app.services.ifc_export_service import _IFCOPENSHELL_AVAILABLE

# 检查 ifcopenshell 是否可用
pytestmark = pytest.mark.skipif(
    not _IFCOPENSHELL_AVAILABLE,
    reason="ifcopenshell 未安装，跳过 IFC 导出测试",
)


async def _create_test_user_and_project(db_session):
    """创建测试用户和项目"""
    user = User(
        phone="13900008002",
        name="IFC测试用户",
        role="homeowner",
        hashed_password="x",
    )
    db_session.add(user)
    await db_session.commit()
    await db_session.refresh(user)

    project = Project(
        name="IFC测试项目",
        owner_id=user.id,
        total_area=100.0,
    )
    db_session.add(project)
    await db_session.commit()
    await db_session.refresh(project)
    return user, project


async def _create_structural_data(db_session, project_id: str):
    """创建测试用结构数据"""
    wall = LoadBearingWall(
        project_id=project_id,
        wall_name="承重墙-A",
        thickness_mm=240,
        length_m=6.0,
        height_m=2.8,
        material="砖砌体",
    )
    db_session.add(wall)

    beam = Beam(
        project_id=project_id,
        beam_name="主梁-A",
        width_mm=250,
        height_mm=500,
        length_m=5.0,
    )
    db_session.add(beam)

    column = Column(
        project_id=project_id,
        column_name="柱-A",
        width_mm=400,
        depth_mm=400,
        height_m=2.8,
    )
    db_session.add(column)

    slab = FloorSlab(
        project_id=project_id,
        slab_name="楼板-1F",
        thickness_mm=120,
        area_m2=80.0,
    )
    db_session.add(slab)
    await db_session.commit()


async def _create_design_data(db_session, project_id: str):
    """创建测试用设计方案"""
    design_data = {
        "walls": [
            {
                "name": "外墙-南",
                "thickness": 240,
                "length": 10.0,
                "start": {"x": 0, "y": 0},
                "end": {"x": 10000, "y": 0},
            },
            {
                "name": "外墙-北",
                "thickness": 240,
                "length": 10.0,
                "start": {"x": 0, "y": 8000},
                "end": {"x": 10000, "y": 8000},
            },
            {
                "name": "内墙-隔断",
                "thickness": 120,
                "length": 8.0,
                "start": {"x": 5000, "y": 0},
                "end": {"x": 5000, "y": 8000},
            },
        ],
        "doors": [
            {"name": "入户门", "width": 900, "height": 2100},
            {"name": "卧室门", "width": 800, "height": 2100},
        ],
        "windows": [
            {"name": "客厅窗", "width": 1800, "height": 1500},
            {"name": "卧室窗", "width": 1200, "height": 1500},
        ],
    }
    plan = FloorPlan(
        project_id=project_id,
        name="IFC设计方案",
        data=json.dumps(design_data),
        wall_height=2.8,
        total_area=100.0,
        room_count=3,
    )
    db_session.add(plan)
    await db_session.commit()
    await db_session.refresh(plan)
    return plan


# ════════════════════════════════════════════════════════════════
# Structural IFC 导出
# ════════════════════════════════════════════════════════════════


@pytest.mark.asyncio
async def test_export_structural_ifc(client: AsyncClient, db_session, auth_headers):
    """测试 structural IFC 导出（有结构数据）"""
    # 通过 API 创建项目（归属于 auth_headers 用户）
    resp = await client.post(
        "/api/projects",
        json={"name": "IFC结构测试项目", "total_area": 100.0},
        headers=auth_headers,
    )
    assert resp.status_code == 201
    project_id = resp.json()["id"]

    await _create_structural_data(db_session, project_id)

    resp = await client.post(
        f"/api/bim/export/structural/{project_id}",
        headers=auth_headers,
        json={},
    )
    assert resp.status_code == 200
    assert resp.headers.get("content-type") == "application/x-ifc"
    assert 'attachment; filename=' in resp.headers.get("content-disposition", "")
    assert int(resp.headers.get("x-file-size", "0")) > 0
    content = resp.content
    # IFC 文件以 "ISO-10303-21;" 开头
    assert content.startswith(b"ISO-10303-21;")
    assert b"IFCWALLSTANDARDCASE" in content or b"IFCWALL" in content
    assert b"IFCBEAM" in content
    assert b"IFCCOLUMN" in content
    assert b"IFCSLAB" in content


@pytest.mark.asyncio
async def test_export_structural_ifc_empty_data(
    client: AsyncClient, db_session, auth_headers
):
    """测试空结构数据导出"""
    # 通过 API 创建项目（归属于 auth_headers 用户）
    resp = await client.post(
        "/api/projects",
        json={"name": "IFC空结构测试项目", "total_area": 100.0},
        headers=auth_headers,
    )
    assert resp.status_code == 201
    project_id = resp.json()["id"]

    resp = await client.post(
        f"/api/bim/export/structural/{project_id}",
        headers=auth_headers,
        json={},
    )
    assert resp.status_code == 200
    content = resp.content
    assert content.startswith(b"ISO-10303-21;")


# ════════════════════════════════════════════════════════════════
# Design IFC 导出
# ════════════════════════════════════════════════════════════════


@pytest.mark.asyncio
async def test_export_design_ifc(client: AsyncClient, db_session, auth_headers):
    """测试 design IFC 导出（有设计方案）"""
    # 通过 API 创建项目（归属于 auth_headers 用户）
    resp = await client.post(
        "/api/projects",
        json={"name": "IFC设计测试项目", "total_area": 100.0},
        headers=auth_headers,
    )
    assert resp.status_code == 201
    project_id = resp.json()["id"]

    plan = await _create_design_data(db_session, project_id)

    resp = await client.post(
        f"/api/bim/export/design/{plan.id}",
        headers=auth_headers,
        json={},
    )
    assert resp.status_code == 200
    assert resp.headers.get("content-type") == "application/x-ifc"
    content = resp.content
    assert content.startswith(b"ISO-10303-21;")
    assert b"IFCWALLSTANDARDCASE" in content
    assert b"IFCDOOR" in content
    assert b"IFCWINDOW" in content


# ════════════════════════════════════════════════════════════════
# 鉴权测试
# ════════════════════════════════════════════════════════════════


@pytest.mark.asyncio
async def test_export_structural_ifc_unauthorized(client: AsyncClient):
    """测试未登录鉴权拒绝"""
    resp = await client.post(
        "/api/bim/export/structural/fake-project-id",
        json={},
    )
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_export_structural_ifc_no_permission(
    client: AsyncClient, db_session, auth_headers
):
    """测试无项目权限拒绝"""
    user, project = await _create_test_user_and_project(db_session)

    # 创建另一个用户和项目
    other_user = User(
        phone="13900008003",
        name="其他用户",
        role="homeowner",
        hashed_password="x",
    )
    db_session.add(other_user)
    await db_session.commit()
    await db_session.refresh(other_user)

    other_project = Project(
        name="其他项目",
        owner_id=other_user.id,
        total_area=50.0,
    )
    db_session.add(other_project)
    await db_session.commit()
    await db_session.refresh(other_project)

    # 使用 auth_headers（属于第一个用户）访问其他用户的项目的 structure export
    resp = await client.post(
        f"/api/bim/export/structural/{other_project.id}",
        headers=auth_headers,
        json={},
    )
    assert resp.status_code == 403


@pytest.mark.asyncio
async def test_export_design_ifc_not_found(
    client: AsyncClient, db_session, auth_headers
):
    """测试设计方案不存在"""
    resp = await client.post(
        "/api/bim/export/design/nonexistent-plan-id",
        headers=auth_headers,
        json={},
    )
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_export_design_ifc_no_permission(
    client: AsyncClient, db_session, auth_headers
):
    """测试设计方案的所属项目无权限"""
    user, project = await _create_test_user_and_project(db_session)

    # 另一个用户的方案
    other_user = User(
        phone="13900008004",
        name="其他用户2",
        role="homeowner",
        hashed_password="x",
    )
    db_session.add(other_user)
    await db_session.commit()
    await db_session.refresh(other_user)

    other_project = Project(
        name="其他项目2",
        owner_id=other_user.id,
        total_area=50.0,
    )
    db_session.add(other_project)
    await db_session.commit()
    await db_session.refresh(other_project)

    plan = FloorPlan(
        project_id=other_project.id,
        name="其他方案",
        data="{}",
        wall_height=2.8,
    )
    db_session.add(plan)
    await db_session.commit()
    await db_session.refresh(plan)

    resp = await client.post(
        f"/api/bim/export/design/{plan.id}",
        headers=auth_headers,
        json={},
    )
    assert resp.status_code == 403


# ════════════════════════════════════════════════════════════════
# P1 方向 C：IFC 交付校验 / 模型对比（validate_ifc_file / diff_ifc_files）
# ════════════════════════════════════════════════════════════════


def test_validate_ifc_file_design_export():
    """导出 design IFC 后，交付校验统计构件类型 + Pset 覆盖"""
    from app.services.ifc_export_service import export_design_to_ifc, validate_ifc_file

    plan = {
        "name": "校验测试",
        "wall_height": 2.8,
        "data": {
            "walls": [
                {"name": "W1", "thickness": 240, "length": 4.0,
                 "start": {"x": 0, "y": 0}, "end": {"x": 4000, "y": 0}},
            ],
            "doors": [{"name": "D1", "width": 900, "height": 2100}],
            "windows": [],
        },
    }
    filepath = export_design_to_ifc(plan)
    try:
        report = validate_ifc_file(filepath)
        assert report["schema"] == "IFC4"
        assert report["source"] == "ifcopenshell_deterministic"
        assert report["elements"].get("wall", 0) >= 1
        assert report["elements"].get("door", 0) >= 1
        # ifc_real_placement_enabled=True 默认 → 墙体附 Pset
        assert report["pset_wall_coverage"] == 1.0
        assert report["issues"] == []
    finally:
        os.remove(filepath)


def test_diff_ifc_files_type_counts():
    """模型对比：构件类型计数差异（IfcWallStandardCase 1→2）"""
    from app.services.ifc_export_service import export_design_to_ifc, diff_ifc_files

    base = {
        "name": "diff",
        "wall_height": 2.8,
        "data": {
            "walls": [
                {"name": "W1", "thickness": 240, "length": 4.0,
                 "start": {"x": 0, "y": 0}, "end": {"x": 4000, "y": 0}},
            ],
            "doors": [], "windows": [],
        },
    }
    more = {
        "name": "diff",
        "wall_height": 2.8,
        "data": {
            "walls": [
                {"name": "W1", "thickness": 240, "length": 4.0,
                 "start": {"x": 0, "y": 0}, "end": {"x": 4000, "y": 0}},
                {"name": "W2", "thickness": 240, "length": 3.0,
                 "start": {"x": 0, "y": 4000}, "end": {"x": 3000, "y": 4000}},
            ],
            "doors": [], "windows": [],
        },
    }
    pa = export_design_to_ifc(base)
    pb = export_design_to_ifc(more)
    try:
        diff = diff_ifc_files(pa, pb)
        assert diff["a_element_count"] < diff["b_element_count"]
        assert diff["type_deltas"]["IfcWallStandardCase"]["delta"] == 1
    finally:
        os.remove(pa)
        os.remove(pb)

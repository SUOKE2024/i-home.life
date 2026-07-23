"""施工图自动生成服务测试 (v1.2.0 P4 修复)

验证 construction_drawing_service：
- generate_floor_plan_svg: 平面图 SVG 生成（含墙体/门窗/标注）
- generate_elevation_svg: 立面图 SVG 生成
- generate_drawings_for_project: 从 active floorplan 生成全套图纸（模型即图纸）
- 链路关联性：floorplan 变 → 图纸重生成
"""

import json
import re

import pytest

from app.services.construction_drawing_service import (
    generate_floor_plan_svg,
    generate_elevation_svg,
    generate_drawings_for_project,
    _escape,
)


# ── 纯函数单元测试 ──────────────────────────────────────────

def test_floor_plan_svg_contains_walls_and_title():
    """平面图 SVG 含墙体 line + 标题"""
    data = {
        "walls": [
            {"name": "W1", "start": {"x": 0, "y": 0}, "end": {"x": 5000, "y": 0}, "thickness": 240},
            {"name": "W2", "start": {"x": 0, "y": 0}, "end": {"x": 0, "y": 4000}, "thickness": 240},
        ],
        "doors": [{"name": "M1", "width": 900, "height": 2100, "position": {"x": 1000, "y": 0}}],
        "windows": [{"name": "C1", "width": 1200, "height": 1500, "position": {"x": 2000, "y": 0}}],
        "rooms": [{"name": "客厅", "area": 20.0, "type": "living", "center": {"x": 2500, "y": 2000}}],
    }
    svg = generate_floor_plan_svg(json.dumps(data), wall_height=2.8, plan_name="测试平面图")

    assert svg.startswith("<svg")
    assert svg.endswith("</svg>")
    assert "http://www.w3.org/2000/svg" in svg
    # 标题
    assert "测试平面图" in svg
    # 层高标注
    assert "2.8" in svg
    # 墙体（stroke-width 表示厚度）
    assert "<line" in svg
    # 房间名标注
    assert "客厅" in svg
    # 面积标注
    assert "20.0" in svg or "20" in svg
    # 比例尺
    assert "1m" in svg


def test_floor_plan_svg_empty_walls_returns_empty_svg():
    """无墙体数据返回空 SVG（不报错）"""
    svg = generate_floor_plan_svg({"walls": []}, plan_name="空图")
    assert "<svg" in svg
    assert "暂无墙体数据" in svg


def test_floor_plan_svg_has_valid_viewbox():
    """SVG viewBox 基于 bounding box 计算"""
    data = {
        "walls": [
            {"name": "W1", "start": {"x": 1000, "y": 2000}, "end": {"x": 6000, "y": 2000}, "thickness": 240},
        ],
        "doors": [], "windows": [], "rooms": [],
    }
    svg = generate_floor_plan_svg(data)
    # viewBox 应含 bounding box 坐标
    match = re.search(r'viewBox="([\d.\-]+ [\d.\-]+ [\d.\-]+ [\d.\-]+)"', svg)
    assert match is not None
    # 应包含 5000（墙长）+ 留白
    assert "5000" in svg or "6000" in svg


def test_elevation_svg_contains_wall_and_openings():
    """立面图 SVG 含墙体边框 + 门窗洞口"""
    data = {
        "walls": [{"name": "W1", "start": {"x": 0, "y": 0}, "end": {"x": 5000, "y": 0}, "thickness": 240}],
        "doors": [{"name": "M1", "width": 900, "height": 2100}],
        "windows": [{"name": "C1", "width": 1200, "height": 1500, "sill_height": 900}],
        "rooms": [],
    }
    svg = generate_elevation_svg(data, wall_name="W1", wall_height=2.8)

    assert svg.startswith("<svg")
    assert "立面图" in svg
    assert "W1" in svg
    # 门洞（白色填充矩形）
    assert "rect" in svg.lower()
    # 高度标注
    assert "2.8" in svg


def test_escape_xml_special_chars():
    """XML 转义"""
    assert _escape("a<b>c&d") == "a&lt;b&gt;c&amp;d"
    assert _escape('"quote"') == "&quot;quote&quot;"


# ── 集成测试：模型即图纸 ────────────────────────────────────

@pytest.mark.asyncio
async def test_generate_drawings_no_floorplan_raises(client, db_session):
    """无 active floorplan 抛 ValueError"""
    from app.models.user import User
    from app.models.project import Project
    import uuid

    user = User(phone="13900007711", name="图纸测试", hashed_password="x", role="homeowner")
    db_session.add(user)
    await db_session.commit()
    project = Project(id=str(uuid.uuid4()), name="无户型", owner_id=user.id)
    db_session.add(project)
    await db_session.commit()

    with pytest.raises(ValueError, match="PROJECT_HAS_NO_ACTIVE_FLOORPLAN"):
        await generate_drawings_for_project(db_session, project.id)


@pytest.mark.asyncio
async def test_generate_drawings_from_floorplan(client, db_session):
    """从 active floorplan 生成全套施工图"""
    from app.models.user import User
    from app.models.project import Project
    from app.models.floorplan import FloorPlan
    import uuid

    user = User(phone="13900007712", name="图纸测试2", hashed_password="x", role="homeowner")
    db_session.add(user)
    await db_session.commit()
    project = Project(id=str(uuid.uuid4()), name="图纸项目", owner_id=user.id)
    db_session.add(project)
    await db_session.commit()

    floorplan_data = {
        "walls": [
            {"name": "W1", "start": {"x": 0, "y": 0}, "end": {"x": 5000, "y": 0}, "thickness": 240},
            {"name": "W2", "start": {"x": 0, "y": 0}, "end": {"x": 0, "y": 4000}, "thickness": 240},
        ],
        "doors": [{"name": "M1", "width": 900, "height": 2100, "position": {"x": 1000, "y": 0}}],
        "windows": [{"name": "C1", "width": 1500, "height": 1500, "position": {"x": 2500, "y": 0}}],
        "rooms": [{"name": "主卧", "area": 20.0, "type": "bedroom"}],
    }
    plan = FloorPlan(
        project_id=project.id, name="图纸户型",
        data=json.dumps(floorplan_data), wall_height=2.8,
        total_area=20.0, room_count=1, is_active=True,
    )
    db_session.add(plan)
    await db_session.commit()

    drawings = await generate_drawings_for_project(db_session, project.id)

    assert drawings.floorplan_id == plan.id
    assert drawings.floorplan_name == "图纸户型"
    assert "<svg" in drawings.floor_plan_svg
    assert "</svg>" in drawings.floor_plan_svg
    # 立面图
    assert len(drawings.elevation_svgs) >= 1
    assert "<svg" in drawings.elevation_svgs[0]["svg"]
    # 元素计数 = 墙+门+窗
    assert drawings.element_count == 4  # 2墙 + 1门 + 1窗
    # 图纸版本基于 updated_at
    assert drawings.drawing_version


@pytest.mark.asyncio
async def test_model_is_drawing_regenerate_on_change(client, db_session):
    """模型即图纸：floorplan 变 → 图纸重生成（无人工干预）"""
    from app.models.user import User
    from app.models.project import Project
    from app.models.floorplan import FloorPlan
    import uuid

    user = User(phone="13900007713", name="模型即图纸测试", hashed_password="x", role="homeowner")
    db_session.add(user)
    await db_session.commit()
    project = Project(id=str(uuid.uuid4()), name="模型图纸项目", owner_id=user.id)
    db_session.add(project)
    await db_session.commit()

    data_v1 = {
        "walls": [{"name": "W1", "start": {"x": 0, "y": 0}, "end": {"x": 5000, "y": 0}, "thickness": 240}],
        "doors": [], "windows": [], "rooms": [],
    }
    plan = FloorPlan(
        project_id=project.id, name="模型图纸",
        data=json.dumps(data_v1), wall_height=2.8, total_area=10, room_count=1, is_active=True,
    )
    db_session.add(plan)
    await db_session.commit()

    drawings_v1 = await generate_drawings_for_project(db_session, project.id)
    assert drawings_v1.element_count == 1  # 1 墙

    # 修改：加一面墙 + 一扇门
    data_v2 = {
        "walls": [
            {"name": "W1", "start": {"x": 0, "y": 0}, "end": {"x": 5000, "y": 0}, "thickness": 240},
            {"name": "W2", "start": {"x": 0, "y": 0}, "end": {"x": 0, "y": 4000}, "thickness": 240},
        ],
        "doors": [{"name": "M1", "width": 900, "height": 2100, "position": {"x": 0, "y": 0}}],
        "windows": [], "rooms": [],
    }
    plan.data = json.dumps(data_v2)
    await db_session.commit()

    drawings_v2 = await generate_drawings_for_project(db_session, project.id)
    # 图纸自动反映新元素（无人工干预）
    assert drawings_v2.element_count == 3  # 2 墙 + 1 门
    assert drawings_v2.drawing_version != drawings_v1.drawing_version

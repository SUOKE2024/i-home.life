"""正向设计算量服务测试 (v1.2.0 P2 修复)

验证 quantity_takeoff_service：
- parse_floorplan_geometry: JSON 几何解析 + mm→m 转换 + 门窗洞口分摊
- forward_takeoff_for_project: 从 active floorplan 派生工程量（链路贯通）
- 链路贯通度：floorplan 几何变 → 工程量自动更新
"""

import json

import pytest

from app.services.quantity_takeoff_service import (
    parse_floorplan_geometry,
    forward_takeoff_for_project,
    FloorplanGeometry,
)


# ── 纯函数单元测试 ──────────────────────────────────────────

def test_parse_basic_floorplan():
    """解析基础户型：单墙 + 单房间"""
    data = {
        "walls": [
            {"name": "W1", "start": {"x": 0, "y": 0}, "end": {"x": 5000, "y": 0}, "thickness": 240},
        ],
        "doors": [{"name": "M1", "width": 900, "height": 2100}],
        "windows": [],
        "rooms": [{"name": "客厅", "area": 20.0, "type": "living"}],
    }
    geo = parse_floorplan_geometry(json.dumps(data), wall_height=2.8)

    assert isinstance(geo, FloorplanGeometry)
    assert len(geo.walls) == 1
    # mm → m 转换：5000mm = 5.0m
    assert geo.walls[0].length_m == 5.0
    assert geo.walls[0].thickness_mm == 240.0
    assert geo.walls[0].name == "W1"
    assert geo.wall_height_m == 2.8
    assert geo.door_count == 1
    assert geo.window_count == 0
    # 房间
    assert len(geo.rooms) == 1
    assert geo.rooms[0]["area"] == 20.0
    assert geo.rooms[0]["room_type"] == "living"
    assert geo.total_area_m2 == 20.0


def test_parse_length_from_explicit_field():
    """显式 length 字段优先于 start/end 计算"""
    data = {
        "walls": [{"name": "W1", "length": 4.5, "thickness": 200}],
        "doors": [], "windows": [], "rooms": [],
    }
    geo = parse_floorplan_geometry(data)
    assert geo.walls[0].length_m == 4.5


def test_parse_openings_apportioned_by_wall_length():
    """墙体未标注洞口时，按墙长比例分摊门窗总面积"""
    data = {
        "walls": [
            {"name": "W1", "start": {"x": 0, "y": 0}, "end": {"x": 6000, "y": 0}, "thickness": 240},
            {"name": "W2", "start": {"x": 0, "y": 0}, "end": {"x": 3000, "y": 0}, "thickness": 240},
        ],
        "doors": [{"width": 900, "height": 2100}],  # 1.89 m²
        "windows": [{"width": 1200, "height": 1500}],  # 1.8 m²
        "rooms": [],
    }
    geo = parse_floorplan_geometry(data)
    total_openings = sum(w.openings_area_m2 for w in geo.walls)
    # 总洞口 1.89 + 1.8 = 3.69，分摊到两墙
    assert abs(total_openings - 3.69) < 0.05
    # W1 长 6m，W2 长 3m，W1 应分摊 2/3
    w1_share = geo.walls[0].openings_area_m2 / total_openings
    assert abs(w1_share - 2 / 3) < 0.05


def test_parse_empty_data():
    """空数据返回空几何（不报错）"""
    geo = parse_floorplan_geometry(None)
    assert geo.walls == []
    assert geo.rooms == []
    assert geo.total_area_m2 == 0.0


def test_parse_invalid_json():
    """非法 JSON 降级为空几何"""
    geo = parse_floorplan_geometry("{invalid json}")
    assert geo.walls == []


def test_parse_no_rooms_estimate_from_walls():
    """无房间数据时，用墙长×层高/墙地比估算面积"""
    data = {
        "walls": [{"name": "W1", "length": 10.0, "thickness": 240}],
        "doors": [], "windows": [], "rooms": [],
    }
    geo = parse_floorplan_geometry(data, wall_height=2.8)
    # 10m × 2.8 / 2.8 = 10 m²
    assert geo.total_area_m2 == 10.0


# ── 集成测试：链路贯通（floorplan → forward_takeoff）───────────

@pytest.mark.asyncio
async def test_forward_takeoff_no_floorplan_raises(client, db_session):
    """项目无 active floorplan 时抛 ValueError"""
    from app.models.user import User
    from app.models.project import Project
    import uuid

    user = User(phone="13900007701", name="算量测试", hashed_password="x", role="homeowner")
    db_session.add(user)
    await db_session.commit()
    project = Project(id=str(uuid.uuid4()), name="无户型项目", owner_id=user.id)
    db_session.add(project)
    await db_session.commit()

    with pytest.raises(ValueError, match="PROJECT_HAS_NO_ACTIVE_FLOORPLAN"):
        await forward_takeoff_for_project(db_session, project.id)


@pytest.mark.asyncio
async def test_forward_takeoff_from_floorplan(client, db_session):
    """链路贯通：创建 floorplan → 正向算量自动派生工程量"""
    from app.models.user import User
    from app.models.project import Project
    from app.models.floorplan import FloorPlan
    import uuid

    user = User(phone="13900007702", name="算量测试2", hashed_password="x", role="homeowner")
    db_session.add(user)
    await db_session.commit()
    project = Project(id=str(uuid.uuid4()), name="算量项目", owner_id=user.id)
    db_session.add(project)
    await db_session.commit()

    floorplan_data = {
        "walls": [
            {"name": "W1", "start": {"x": 0, "y": 0}, "end": {"x": 5000, "y": 0}, "thickness": 240},
            {"name": "W2", "start": {"x": 0, "y": 0}, "end": {"x": 0, "y": 4000}, "thickness": 240},
        ],
        "doors": [{"name": "M1", "width": 900, "height": 2100}],
        "windows": [],
        "rooms": [{"name": "客厅", "area": 20.0, "type": "living", "tile_size": "600x600"}],
    }
    plan = FloorPlan(
        project_id=project.id, name="测试户型",
        data=json.dumps(floorplan_data), wall_height=2.8,
        total_area=20.0, room_count=1, is_active=True,
    )
    db_session.add(plan)
    await db_session.commit()

    result = await forward_takeoff_for_project(db_session, project.id)

    assert result.project_id == project.id
    assert result.floorplan_id == plan.id
    # 两面墙
    assert len(result.walls) == 2
    assert result.walls[0]["length"] == 5.0
    assert result.walls[1]["length"] == 4.0
    # 砖数 > 0
    assert result.summary["total_brick_count"] > 0
    # 地面瓷砖
    assert len(result.floors) == 1
    assert result.floors[0]["area"] == 20.0
    assert result.floors[0]["tile_count"] > 0
    # 吊顶
    assert len(result.ceilings) == 1
    # reply 文本含关键字
    assert "砖" in result.reply
    assert "瓷砖" in result.reply
    # 几何摘要
    assert result.geometry["wall_count"] == 2
    assert result.geometry["room_count"] == 1


@pytest.mark.asyncio
async def test_linkage_floorplan_change_updates_takeoff(client, db_session):
    """链路贯通度验收：修改 floorplan 墙长 → 工程量自动更新（SSOT 验证）"""
    from app.models.user import User
    from app.models.project import Project
    from app.models.floorplan import FloorPlan
    import uuid

    user = User(phone="13900007703", name="贯通测试", hashed_password="x", role="homeowner")
    db_session.add(user)
    await db_session.commit()
    project = Project(id=str(uuid.uuid4()), name="贯通项目", owner_id=user.id)
    db_session.add(project)
    await db_session.commit()

    # 初始：单墙 5m
    data_v1 = {
        "walls": [{"name": "W1", "start": {"x": 0, "y": 0}, "end": {"x": 5000, "y": 0}, "thickness": 240}],
        "doors": [], "windows": [],
        "rooms": [{"name": "客厅", "area": 15.0, "type": "living"}],
    }
    plan = FloorPlan(
        project_id=project.id, name="贯通户型",
        data=json.dumps(data_v1), wall_height=2.8,
        total_area=15.0, room_count=1, is_active=True,
    )
    db_session.add(plan)
    await db_session.commit()

    result_v1 = await forward_takeoff_for_project(db_session, project.id)
    brick_v1 = result_v1.summary["total_brick_count"]

    # 修改：墙长 5m → 10m（加长一倍）
    data_v2 = {
        "walls": [{"name": "W1", "start": {"x": 0, "y": 0}, "end": {"x": 10000, "y": 0}, "thickness": 240}],
        "doors": [], "windows": [],
        "rooms": [{"name": "客厅", "area": 15.0, "type": "living"}],
    }
    plan.data = json.dumps(data_v2)
    await db_session.commit()

    result_v2 = await forward_takeoff_for_project(db_session, project.id)
    brick_v2 = result_v2.summary["total_brick_count"]

    # 墙长翻倍 → 砖数应显著增加（SSOT 贯通验证）
    assert brick_v2 > brick_v1
    assert result_v2.walls[0]["length"] == 10.0

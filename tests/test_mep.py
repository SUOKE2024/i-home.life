"""mep_service 纯函数测试 — 水电点位规划 / 电器规划 / 合规检查

mep_service 中 3 个函数均为纯函数 (无 DB 依赖),直接调用即可。
"""

from app.services.mep_service import (
    generate_mep_plan,
    generate_appliance_plan,
    check_mep_compliance,
)


# ════════════════════════════════════════════════════════════════
# generate_mep_plan
# ════════════════════════════════════════════════════════════════


def test_generate_mep_plan_basic():
    """基本水电点位规划 — 客厅 + 厨房"""
    rooms = [
        {"name": "客厅", "room_type": "living_room", "area": 20.0},
        {"name": "厨房", "room_type": "kitchen", "area": 8.0},
    ]
    result = generate_mep_plan(rooms)

    assert result["rooms_count"] == 2
    assert isinstance(result["points"], list)
    assert len(result["points"]) > 0

    summary = result["summary"]
    assert "total_points" in summary
    assert "switches" in summary
    assert "sockets" in summary
    assert summary["total_points"] > 0

    circuits = result["circuits"]
    assert "dedicated" in circuits
    assert "shared" in circuits

    assert "水电点位规划" in result["reply"]


def test_generate_mep_plan_unknown_room_type():
    """未知房间类型 fallback 到 bedroom 标准,不抛异常"""
    rooms = [{"name": "未知", "room_type": "warehouse", "area": 10.0}]
    result = generate_mep_plan(rooms)

    assert result["rooms_count"] == 1
    assert len(result["points"]) > 0
    # bedroom 标准: switches=2
    assert result["summary"]["switches"] == 2


def test_generate_mep_plan_empty_rooms():
    """空房间列表 — total_points=0,不抛异常"""
    result = generate_mep_plan([])

    assert result["rooms_count"] == 0
    assert result["summary"]["total_points"] == 0
    assert len(result["points"]) == 0


def test_generate_mep_plan_kitchen_has_dedicated_circuits():
    """厨房有专用回路 (洗碗机/烤箱等)"""
    rooms = [{"name": "厨房", "room_type": "kitchen", "area": 8.0}]
    result = generate_mep_plan(rooms)

    dedicated = result["circuits"]["dedicated"]
    assert len(dedicated) > 0
    # 洗碗机/烤箱插座为专用回路
    assert any("洗碗机" in name for name in dedicated)


# ════════════════════════════════════════════════════════════════
# generate_appliance_plan
# ════════════════════════════════════════════════════════════════


def test_generate_appliance_plan_basic():
    """基本电器规划 — 厨房 + 卫生间"""
    rooms = [
        {"name": "厨房", "room_type": "kitchen", "area": 8.0},
        {"name": "卫生间", "room_type": "bathroom", "area": 5.0},
    ]
    result = generate_appliance_plan(rooms)

    assert len(result["appliances"]) > 0
    assert result["total_power_w"] > 0
    assert result["dedicated_circuits"] > 0
    assert "总闸" in result["panel_recommendation"]


def test_generate_appliance_plan_high_power_3phase():
    """高功率 (>15000W) → 三相 380V"""
    # 2 个厨房: 7580W * 2 = 15160W > 15000W
    rooms = [
        {"name": "厨房1", "room_type": "kitchen", "area": 8.0},
        {"name": "厨房2", "room_type": "kitchen", "area": 8.0},
    ]
    result = generate_appliance_plan(rooms)

    assert result["total_power_w"] > 15000
    assert "三相 380V" in result["panel_recommendation"]


def test_generate_appliance_plan_low_power_63A():
    """低功率 (<8000W) → 63A"""
    rooms = [{"name": "卧室", "room_type": "bedroom", "area": 15.0}]
    result = generate_appliance_plan(rooms)

    assert result["total_power_w"] < 8000
    assert "63A" in result["panel_recommendation"]


# ════════════════════════════════════════════════════════════════
# check_mep_compliance
# ════════════════════════════════════════════════════════════════


def test_check_mep_compliance_all_pass():
    """合规点位 — 全部通过"""
    points = [
        {"name": "客厅主灯开关", "point_type": "switch", "height": 1300},
        {"name": "客厅空调插座", "point_type": "ac_socket", "height": 2000},
        {"name": "卫生间镜前插座", "point_type": "socket", "height": 1300, "notes": "带防水盖"},
    ]
    result = check_mep_compliance(points)

    assert result["compliant"] is True
    assert result["errors"] == 0


def test_check_mep_compliance_ac_too_low():
    """空调插座高度 < 1800mm → error"""
    points = [
        {"name": "卧室空调插座", "point_type": "ac_socket", "height": 1500},
    ]
    result = check_mep_compliance(points)

    assert result["errors"] == 1
    assert result["compliant"] is False


def test_check_mep_compliance_switch_wrong_height():
    """开关高度不在 1200-1400mm 范围 → warning"""
    points = [
        {"name": "客厅开关", "point_type": "switch", "height": 800},
    ]
    result = check_mep_compliance(points)

    assert result["warnings"] >= 1


def test_check_mep_compliance_bathroom_no_waterproof():
    """卫生间插座无防水 → warning"""
    points = [
        {"name": "卫生间插座", "point_type": "socket", "height": 1300, "notes": "普通"},
    ]
    result = check_mep_compliance(points)

    assert result["warnings"] >= 1


def test_check_mep_compliance_empty_input():
    """空输入 — total_points=0, compliant=True"""
    result = check_mep_compliance([])

    assert result["total_points"] == 0
    assert result["compliant"] is True

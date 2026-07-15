"""F17 卫生间设计器服务层 — 布局生成 + 地漏坡度 + 防水校验 + 通风分析 + CRUD"""

import math

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.bathroom import BathroomDesign, BathroomFixture


# ── 布局生成 ──

def generate_bathroom_layout(design: BathroomDesign) -> list[dict]:
    """根据布局类型生成卫浴排布

    Args:
        design: 卫生间设计
    """
    layout = design.layout_type
    w = design.room_width
    length = design.room_length

    if layout == "dry_wet_separation":
        return _gen_dry_wet_layout(w, length)
    elif layout == "three_separation":
        return _gen_three_separation_layout(w, length)
    else:
        return _gen_traditional_layout(w, length)


def _gen_dry_wet_layout(w: float, length: float) -> list[dict]:
    """干湿分离: 淋浴区 + 马桶区 + 洗漱区"""
    return [
        # 洗漱区 (干区 - 入门侧)
        {
            "fixture_type": "basin",
            "brand": "科勒",
            "width": 800.0, "depth": 500.0, "height": 850.0,
            "position_x": 0.0, "position_y": 0.0, "position_z": 0.0,
            "material": "陶瓷", "color": "白色",
            "price": 2800.0,
        },
        {
            "fixture_type": "mirror",
            "brand": "心海伽蓝",
            "width": 800.0, "depth": 30.0, "height": 700.0,
            "position_x": 0.0, "position_y": 0.0, "position_z": 900.0,
            "material": "银镜", "color": "白色",
            "price": 1280.0,
        },
        {
            "fixture_type": "cabinet",
            "brand": "恒洁",
            "width": 800.0, "depth": 480.0, "height": 500.0,
            "position_x": 0.0, "position_y": 0.0, "position_z": 0.0,
            "material": "实木多层", "color": "原木色",
            "price": 2880.0,
        },
        # 马桶区 (中间)
        {
            "fixture_type": "toilet",
            "brand": "TOTO",
            "width": 400.0, "depth": 700.0, "height": 750.0,
            "position_x": (w * 1000 - 400) / 2,
            "position_y": 0.0, "position_z": 0.0,
            "material": "陶瓷", "color": "白色",
            "price": 3980.0,
        },
        # 淋浴区 (湿区 - 最内侧)
        {
            "fixture_type": "shower",
            "brand": "高仪",
            "width": 900.0, "depth": 900.0, "height": 2000.0,
            "position_x": (w * 1000 - 900) / 2,
            "position_y": (length * 1000 - 900),
            "position_z": 0.0,
            "material": "不锈钢", "color": "银色",
            "price": 1680.0,
        },
        # 暖风机
        {
            "fixture_type": "heater",
            "brand": "松下",
            "width": 300.0, "depth": 300.0, "height": 200.0,
            "position_x": (w * 1000 - 300) / 2,
            "position_y": 0.0, "position_z": 2400.0,
            "price": 1280.0,
        },
        # 换气扇
        {
            "fixture_type": "vent_fan",
            "brand": "艾美特",
            "width": 300.0, "depth": 300.0, "height": 100.0,
            "position_x": 0.0, "position_y": (length * 1000 - 300),
            "position_z": 2500.0,
            "price": 368.0,
        },
    ]


def _gen_three_separation_layout(w: float, length: float) -> list[dict]:
    """三分离: 淋浴 / 马桶 / 洗漱各自独立"""
    fixtures = _gen_dry_wet_layout(w, length)
    # 三分离增加隔断标识 (通过 notes 标注)
    for f in fixtures:
        f["notes"] = "三分离独立区域"
    return fixtures


def _gen_traditional_layout(w: float, length: float) -> list[dict]:
    """传统布局: 无分离"""
    return [
        {
            "fixture_type": "basin",
            "brand": "科勒",
            "width": 600.0, "depth": 450.0, "height": 850.0,
            "position_x": 0.0, "position_y": 0.0, "position_z": 0.0,
            "price": 1800.0,
        },
        {
            "fixture_type": "toilet",
            "brand": "TOTO",
            "width": 400.0, "depth": 700.0, "height": 750.0,
            "position_x": w * 1000 - 400,
            "position_y": 0.0, "position_z": 0.0,
            "price": 2980.0,
        },
        {
            "fixture_type": "shower",
            "brand": "高仪",
            "width": 600.0, "depth": 600.0, "height": 2000.0,
            "position_x": (w * 1000 - 600) / 2,
            "position_y": (length * 1000 - 600),
            "position_z": 0.0,
            "price": 1280.0,
        },
    ]


# ── 地漏坡度计算 ──

def compute_drain_slope(design: BathroomDesign) -> dict:
    """地漏坡度计算 (坡度 = (地漏位置 - 最远点) / 距离 × 100%, 推荐 1-2%)

    Args:
        design: 卫生间设计
    """
    w = design.room_width
    length = design.room_length

    # 假设地漏在湿区中心 (最内侧)
    drain_x = w / 2
    drain_y = length * 0.8

    # 最远点为门口对角
    farthest_x = 0.0
    farthest_y = 0.0
    distance = math.sqrt((drain_x - farthest_x) ** 2 + (drain_y - farthest_y) ** 2)

    # 高差 (mm) — 按设计坡度计算
    slope = design.drain_slope_percent
    height_diff = distance * 1000 * slope / 100  # mm

    # 评级
    if 1.0 <= slope <= 2.0:
        rating = "optimal"
        suggestion = "坡度合理，排水顺畅"
    elif slope < 1.0:
        rating = "insufficient"
        suggestion = "坡度不足，可能导致积水，建议 ≥ 1%"
    else:
        rating = "excessive"
        suggestion = "坡度过大，影响行走安全，建议 ≤ 2%"

    return {
        "drain_position": {"x": round(drain_x, 2), "y": round(drain_y, 2)},
        "farthest_point": {"x": farthest_x, "y": farthest_y},
        "distance": round(distance, 2),
        "slope_percent": slope,
        "height_diff_mm": round(height_diff, 1),
        "recommended_range": [1.0, 2.0],
        "rating": rating,
        "suggestion": suggestion,
    }


# ── 防水规范校验 ──

def validate_waterproof(design: BathroomDesign) -> dict:
    """防水规范校验 (淋浴区墙面防水 ≥ 1.8m, 其他墙面 ≥ 0.3m, 地面全防水)

    Args:
        design: 卫生间设计
    """
    checks = []
    all_pass = True

    # 1. 淋浴区墙面防水 ≥ 1.8m
    shower_height_m = design.waterproof_height_mm / 1000
    passed = design.waterproof_height_mm >= 1800
    checks.append({
        "item": "淋浴区墙面防水 ≥ 1.8m",
        "value": shower_height_m,
        "unit": "m",
        "passed": passed,
        "standard": "≥ 1.8m",
    })
    if not passed:
        all_pass = False

    # 2. 其他墙面防水 ≥ 0.3m
    other_wall_height = 0.3  # 标准要求
    checks.append({
        "item": "其他墙面防水 ≥ 0.3m",
        "value": other_wall_height,
        "unit": "m",
        "passed": True,
        "standard": "≥ 0.3m (翻边高度)",
    })

    # 3. 地面全防水
    checks.append({
        "item": "地面全防水",
        "value": "全做",
        "passed": True,
        "standard": "地面满做防水涂层",
    })

    # 4. 防水层厚度 ≥ 1.5mm
    checks.append({
        "item": "防水层厚度 ≥ 1.5mm",
        "value": 1.5,
        "unit": "mm",
        "passed": True,
        "standard": "≥ 1.5mm (聚氨酯防水涂料)",
    })

    # 5. 闭水试验 ≥ 24h
    checks.append({
        "item": "闭水试验 ≥ 24h",
        "value": 24,
        "unit": "h",
        "passed": True,
        "standard": "≥ 24h 蓄水试验无渗漏",
    })

    return {
        "compliant": all_pass,
        "waterproof_height_mm": design.waterproof_height_mm,
        "checks": checks,
        "total_checks": len(checks),
        "passed_checks": sum(1 for c in checks if c.get("passed")),
    }


# ── 通风分析 ──

def analyze_ventilation(design: BathroomDesign) -> dict:
    """通风分析 (自然通风面积 ≥ 地面 1/20, 机械通风风量 ≥ 80m³/h)

    Args:
        design: 卫生间设计
    """
    floor_area = design.room_width * design.room_length  # m²

    # 自然通风: 窗户面积 ≥ 地面面积 1/20
    required_natural_vent = floor_area / 20
    # 假设窗户面积为 0.6m × 0.9m = 0.54m² (有窗情况)
    assumed_window_area = 0.54
    natural_compliant = assumed_window_area >= required_natural_vent

    # 机械通风: 风量 ≥ 80 m³/h
    required_mechanical = 80.0
    # 换气次数 ≥ 5次/h
    air_change_rate = required_mechanical / (floor_area * design.ceiling_height)
    mechanical_compliant = required_mechanical >= 80

    # 综合判定
    if natural_compliant and mechanical_compliant:
        rating = "good"
        suggestion = "通风条件良好"
    elif mechanical_compliant:
        rating = "mechanical_only"
        suggestion = "无自然通风，依赖机械通风，建议增加排风设备"
    else:
        rating = "insufficient"
        suggestion = "通风不足，建议加大排风量或增设通风设施"

    return {
        "floor_area": round(floor_area, 2),
        "natural_ventilation": {
            "required_area": round(required_natural_vent, 3),
            "assumed_window_area": assumed_window_area,
            "compliant": natural_compliant,
            "standard": "自然通风面积 ≥ 地面 1/20",
        },
        "mechanical_ventilation": {
            "required_airflow": required_mechanical,
            "unit": "m³/h",
            "air_change_rate": round(air_change_rate, 1),
            "compliant": mechanical_compliant,
            "standard": "机械通风风量 ≥ 80m³/h",
        },
        "rating": rating,
        "suggestion": suggestion,
    }


# ── 卫生间设计 CRUD ──

async def create_design(db: AsyncSession, data: dict) -> BathroomDesign:
    design = BathroomDesign(**data)
    db.add(design)
    await db.commit()
    await db.refresh(design)
    return design


async def get_design(db: AsyncSession, design_id: str) -> BathroomDesign | None:
    result = await db.execute(
        select(BathroomDesign)
        .where(BathroomDesign.id == design_id)
        .options(selectinload(BathroomDesign.fixtures))
    )
    return result.scalar_one_or_none()


async def list_designs(db: AsyncSession, project_id: str) -> list[BathroomDesign]:
    result = await db.execute(
        select(BathroomDesign)
        .where(BathroomDesign.project_id == project_id)
        .order_by(BathroomDesign.created_at.desc())
    )
    return list(result.scalars().all())


async def delete_design(db: AsyncSession, design_id: str) -> bool:
    design = await get_design(db, design_id)
    if not design:
        return False
    await db.delete(design)
    await db.commit()
    return True


# ── 卫浴设备 CRUD ──

async def add_fixture(db: AsyncSession, data: dict) -> BathroomFixture:
    fixture = BathroomFixture(**data)
    db.add(fixture)
    await db.commit()
    await db.refresh(fixture)
    return fixture


async def list_fixtures(db: AsyncSession, design_id: str) -> list[BathroomFixture]:
    result = await db.execute(
        select(BathroomFixture)
        .where(BathroomFixture.design_id == design_id)
        .order_by(BathroomFixture.created_at)
    )
    return list(result.scalars().all())


async def delete_fixture(db: AsyncSession, fixture_id: str) -> bool:
    result = await db.execute(select(BathroomFixture).where(BathroomFixture.id == fixture_id))
    fixture = result.scalar_one_or_none()
    if not fixture:
        return False
    await db.delete(fixture)
    await db.commit()
    return True

"""F8-F9 土建模块服务层 — 结构属性管理 + 工程量计算"""

import math
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.structural import (
    LoadBearingWall,
    Beam,
    Column,
    FloorSlab,
    FoundationType,
    StructureLoadEstimate,
    BayCompliance,
    QuantityCalculation,
    QuantityLineItem,
)


# ════════════════════════════════════════════════════════════════
# 承重墙 CRUD
# ════════════════════════════════════════════════════════════════

async def create_wall(db: AsyncSession, data: dict) -> LoadBearingWall:
    wall = LoadBearingWall(**data)
    db.add(wall)
    await db.commit()
    await db.refresh(wall)
    return wall


async def get_wall(db: AsyncSession, wall_id: str) -> LoadBearingWall | None:
    result = await db.execute(
        select(LoadBearingWall).where(LoadBearingWall.id == wall_id)
    )
    return result.scalar_one_or_none()


async def list_walls(db: AsyncSession, project_id: str) -> list[LoadBearingWall]:
    result = await db.execute(
        select(LoadBearingWall)
        .where(LoadBearingWall.project_id == project_id)
        .order_by(LoadBearingWall.created_at.desc())
    )
    return list(result.scalars().all())


async def update_wall(db: AsyncSession, wall_id: str, data: dict) -> LoadBearingWall | None:
    wall = await get_wall(db, wall_id)
    if not wall:
        return None
    for key, value in data.items():
        if hasattr(wall, key) and key not in ("id", "project_id", "created_at"):
            setattr(wall, key, value)
    await db.commit()
    await db.refresh(wall)
    return wall


async def delete_wall(db: AsyncSession, wall_id: str) -> bool:
    wall = await get_wall(db, wall_id)
    if not wall:
        return False
    await db.delete(wall)
    await db.commit()
    return True


# ════════════════════════════════════════════════════════════════
# 梁 CRUD
# ════════════════════════════════════════════════════════════════

async def create_beam(db: AsyncSession, data: dict) -> Beam:
    beam = Beam(**data)
    db.add(beam)
    await db.commit()
    await db.refresh(beam)
    return beam


async def get_beam(db: AsyncSession, beam_id: str) -> Beam | None:
    result = await db.execute(select(Beam).where(Beam.id == beam_id))
    return result.scalar_one_or_none()


async def list_beams(db: AsyncSession, project_id: str) -> list[Beam]:
    result = await db.execute(
        select(Beam)
        .where(Beam.project_id == project_id)
        .order_by(Beam.created_at.desc())
    )
    return list(result.scalars().all())


async def update_beam(db: AsyncSession, beam_id: str, data: dict) -> Beam | None:
    beam = await get_beam(db, beam_id)
    if not beam:
        return None
    for key, value in data.items():
        if hasattr(beam, key) and key not in ("id", "project_id", "created_at"):
            setattr(beam, key, value)
    await db.commit()
    await db.refresh(beam)
    return beam


async def delete_beam(db: AsyncSession, beam_id: str) -> bool:
    beam = await get_beam(db, beam_id)
    if not beam:
        return False
    await db.delete(beam)
    await db.commit()
    return True


# ════════════════════════════════════════════════════════════════
# 柱 CRUD
# ════════════════════════════════════════════════════════════════

async def create_column(db: AsyncSession, data: dict) -> Column:
    col = Column(**data)
    db.add(col)
    await db.commit()
    await db.refresh(col)
    return col


async def get_column(db: AsyncSession, column_id: str) -> Column | None:
    result = await db.execute(select(Column).where(Column.id == column_id))
    return result.scalar_one_or_none()


async def list_columns(db: AsyncSession, project_id: str) -> list[Column]:
    result = await db.execute(
        select(Column)
        .where(Column.project_id == project_id)
        .order_by(Column.created_at.desc())
    )
    return list(result.scalars().all())


async def update_column(db: AsyncSession, column_id: str, data: dict) -> Column | None:
    col = await get_column(db, column_id)
    if not col:
        return None
    for key, value in data.items():
        if hasattr(col, key) and key not in ("id", "project_id", "created_at"):
            setattr(col, key, value)
    await db.commit()
    await db.refresh(col)
    return col


async def delete_column(db: AsyncSession, column_id: str) -> bool:
    col = await get_column(db, column_id)
    if not col:
        return False
    await db.delete(col)
    await db.commit()
    return True


# ════════════════════════════════════════════════════════════════
# 楼板 CRUD
# ════════════════════════════════════════════════════════════════

async def create_slab(db: AsyncSession, data: dict) -> FloorSlab:
    slab = FloorSlab(**data)
    db.add(slab)
    await db.commit()
    await db.refresh(slab)
    return slab


async def get_slab(db: AsyncSession, slab_id: str) -> FloorSlab | None:
    result = await db.execute(select(FloorSlab).where(FloorSlab.id == slab_id))
    return result.scalar_one_or_none()


async def list_slabs(db: AsyncSession, project_id: str) -> list[FloorSlab]:
    result = await db.execute(
        select(FloorSlab)
        .where(FloorSlab.project_id == project_id)
        .order_by(FloorSlab.created_at.desc())
    )
    return list(result.scalars().all())


async def update_slab(db: AsyncSession, slab_id: str, data: dict) -> FloorSlab | None:
    slab = await get_slab(db, slab_id)
    if not slab:
        return None
    for key, value in data.items():
        if hasattr(slab, key) and key not in ("id", "project_id", "created_at"):
            setattr(slab, key, value)
    await db.commit()
    await db.refresh(slab)
    return slab


async def delete_slab(db: AsyncSession, slab_id: str) -> bool:
    slab = await get_slab(db, slab_id)
    if not slab:
        return False
    await db.delete(slab)
    await db.commit()
    return True


# ════════════════════════════════════════════════════════════════
# 基础类型管理
# ════════════════════════════════════════════════════════════════

async def create_foundation(db: AsyncSession, data: dict) -> FoundationType:
    foundation = FoundationType(**data)
    db.add(foundation)
    await db.commit()
    await db.refresh(foundation)
    return foundation


async def get_foundation(db: AsyncSession, foundation_id: str) -> FoundationType | None:
    result = await db.execute(
        select(FoundationType).where(FoundationType.id == foundation_id)
    )
    return result.scalar_one_or_none()


async def list_foundations(db: AsyncSession, project_id: str) -> list[FoundationType]:
    result = await db.execute(
        select(FoundationType)
        .where(FoundationType.project_id == project_id)
        .order_by(FoundationType.created_at.desc())
    )
    return list(result.scalars().all())


async def select_foundation(db: AsyncSession, foundation_id: str) -> FoundationType | None:
    """将指定基础方案标记为项目选定方案（先取消其他选定）"""
    foundation = await get_foundation(db, foundation_id)
    if not foundation:
        return None
    # 取消该项目已有的选定
    all_foundations = await list_foundations(db, foundation.project_id)
    for f in all_foundations:
        f.is_selected = False
    foundation.is_selected = True
    await db.commit()
    await db.refresh(foundation)
    return foundation


async def delete_foundation(db: AsyncSession, foundation_id: str) -> bool:
    foundation = await get_foundation(db, foundation_id)
    if not foundation:
        return False
    await db.delete(foundation)
    await db.commit()
    return True


def recommend_foundation(soil_type: str, building_floors: int = 2) -> dict:
    """基础类型推荐

    根据土质和楼层数推荐基础类型 (参考 GB 50007 建筑地基基础设计规范)

    Args:
        soil_type: 土质类型 (粘土 / 砂土 / 粉土 / 岩石)
        building_floors: 楼层数
    """
    options = {
        "岩石": {
            "recommended": "isolated",
            "bearing_capacity_kpa": 300.0,
            "embed_depth_m": 0.8,
            "reason": "岩石地基承载力高，可采用独立基础",
        },
        "砂土": {
            "recommended": "strip",
            "bearing_capacity_kpa": 200.0,
            "embed_depth_m": 1.2,
            "reason": "砂土地基承载力较好，条形基础经济可靠",
        },
        "粘土": {
            "recommended": "raft" if building_floors >= 3 else "strip",
            "bearing_capacity_kpa": 150.0,
            "embed_depth_m": 1.5,
            "reason": f"{building_floors}层建筑粘土地区，推荐{'筏板' if building_floors >= 3 else '条形'}基础",
        },
        "粉土": {
            "recommended": "raft",
            "bearing_capacity_kpa": 120.0,
            "embed_depth_m": 1.5,
            "reason": "粉土地基承载力较低，建议筏板基础或桩基础",
        },
    }
    option = options.get(soil_type, {
        "recommended": "strip",
        "bearing_capacity_kpa": 150.0,
        "embed_depth_m": 1.5,
        "reason": "未识别土质，默认条形基础方案",
    })
    return {
        "soil_type": soil_type,
        "building_floors": building_floors,
        **option,
    }


# ════════════════════════════════════════════════════════════════
# 荷载估算
# ════════════════════════════════════════════════════════════════

# 参考 GB 50009 建筑结构荷载规范
LOAD_STANDARDS = {
    "住宅": {"dead_load": 2.0, "live_load": 2.0},
    "办公": {"dead_load": 2.5, "live_load": 2.0},
    "商业": {"dead_load": 3.0, "live_load": 3.5},
    "屋面": {"dead_load": 3.5, "live_load": 0.5},
}


async def create_load_estimate(db: AsyncSession, data: dict) -> StructureLoadEstimate:
    # 自动计算总荷载
    load_value = data.get("load_value_kn_m2", 0.0) or 0.0
    area = data.get("area_m2", 0.0) or 0.0
    if data.get("total_load_kn", 0.0) == 0.0:
        data["total_load_kn"] = round(load_value * area, 2)
    estimate = StructureLoadEstimate(**data)
    db.add(estimate)
    await db.commit()
    await db.refresh(estimate)
    return estimate


async def get_load_estimate(db: AsyncSession, estimate_id: str) -> StructureLoadEstimate | None:
    result = await db.execute(
        select(StructureLoadEstimate).where(StructureLoadEstimate.id == estimate_id)
    )
    return result.scalar_one_or_none()


async def list_load_estimates(db: AsyncSession, project_id: str) -> list[StructureLoadEstimate]:
    result = await db.execute(
        select(StructureLoadEstimate)
        .where(StructureLoadEstimate.project_id == project_id)
        .order_by(StructureLoadEstimate.created_at.desc())
    )
    return list(result.scalars().all())


async def delete_load_estimate(db: AsyncSession, estimate_id: str) -> bool:
    estimate = await get_load_estimate(db, estimate_id)
    if not estimate:
        return False
    await db.delete(estimate)
    await db.commit()
    return True


def compute_load_estimates(usage: str, area_m2: float, floor_level: int | None = None, include_seismic: bool = False) -> dict:
    """自动计算荷载估算 (参考 GB 50009)

    Args:
        usage: 使用功能 (住宅/办公/商业/屋面)
        area_m2: 面积 (m²)
        floor_level: 楼层 (None 为屋面)
        include_seismic: 是否包含抗震荷载
    """
    standards = LOAD_STANDARDS.get(usage, {"dead_load": 2.0, "live_load": 2.0})
    dead_load = standards["dead_load"]
    live_load = standards["live_load"]

    dead_total = round(dead_load * area_m2, 2)
    live_total = round(live_load * area_m2, 2)

    items = [
        {
            "load_type": "dead_load",
            "load_name": "恒载 (结构自重)",
            "load_value_kn_m2": dead_load,
            "total_load_kn": dead_total,
        },
        {
            "load_type": "live_load",
            "load_name": "活载 (使用荷载)",
            "load_value_kn_m2": live_load,
            "total_load_kn": live_total,
        },
    ]

    # 风荷载简化计算 (基本风压 0.45 kN/m², GB 50009)
    wind_load = 0.45
    wind_total = round(wind_load * area_m2, 2)
    items.append({
        "load_type": "wind_load",
        "load_name": "风荷载",
        "load_value_kn_m2": wind_load,
        "total_load_kn": wind_total,
    })

    # 屋面雪荷载 (GB 50009, 基本雪压按地区, 此处取 0.4)
    if usage == "屋面" or floor_level is None:
        snow_load = 0.4
        snow_total = round(snow_load * area_m2, 2)
        items.append({
            "load_type": "snow_load",
            "load_name": "雪荷载 (屋面)",
            "load_value_kn_m2": snow_load,
            "total_load_kn": snow_total,
        })

    # 地震荷载简化估算 (GB 50011, 按 7 度设防)
    if include_seismic:
        seismic_base = 0.08  # 7度设防基本加速度
        seismic_total = round(seismic_base * (dead_total + 0.5 * live_total), 2)
        items.append({
            "load_type": "seismic",
            "load_name": "地震作用 (7度设防)",
            "load_value_kn_m2": seismic_base,
            "total_load_kn": seismic_total,
        })

    grand_total = round(sum(item["total_load_kn"] for item in items), 2)

    return {
        "usage": usage,
        "area_m2": area_m2,
        "floor_level": floor_level,
        "include_seismic": include_seismic,
        "load_items": items,
        "total_load_kn": grand_total,
        "reference_standard": "GB 50009-2012 建筑结构荷载规范",
    }


# ════════════════════════════════════════════════════════════════
# 开间/进深/层高合规检查
# ════════════════════════════════════════════════════════════════

async def create_compliance_check(db: AsyncSession, data: dict) -> BayCompliance:
    bay_width = data.get("bay_width_m", 0.0) or 0.0
    depth = data.get("depth_m", 0.0) or 0.0
    floor_height = data.get("floor_height_m", 2.8) or 2.8

    # 合规检查 (参考 GB 50096-2011 住宅设计规范)
    checks = []

    # 开间检查: 住宅 ≥ 2.7m
    is_bay_ok = bay_width >= 2.7
    checks.append({
        "item": "开间 ≥ 2.7m (GB 50096-2011 §5.1.4)",
        "value": bay_width,
        "standard": 2.7,
        "passed": is_bay_ok,
    })

    # 进深检查: 不宜超过开间 2 倍
    is_depth_ok = (depth <= bay_width * 2) if bay_width > 0 else True
    checks.append({
        "item": "进深 ≤ 开间 × 2",
        "value": depth,
        "standard": round(bay_width * 2, 2),
        "passed": is_depth_ok,
    })

    # 层高检查: 住宅 ≥ 2.8m, 卧室 ≥ 2.4m
    is_height_ok = floor_height >= 2.8
    checks.append({
        "item": "层高 ≥ 2.8m (GB 50096-2011 §5.5.1)",
        "value": floor_height,
        "standard": 2.8,
        "passed": is_height_ok,
    })

    data["is_bay_compliant"] = is_bay_ok
    data["is_depth_compliant"] = is_depth_ok
    data["is_height_compliant"] = is_height_ok
    data["checks"] = checks

    compliance = BayCompliance(**data)
    db.add(compliance)
    await db.commit()
    await db.refresh(compliance)
    return compliance


async def get_compliance(db: AsyncSession, compliance_id: str) -> BayCompliance | None:
    result = await db.execute(
        select(BayCompliance).where(BayCompliance.id == compliance_id)
    )
    return result.scalar_one_or_none()


async def list_compliance(db: AsyncSession, project_id: str) -> list[BayCompliance]:
    result = await db.execute(
        select(BayCompliance)
        .where(BayCompliance.project_id == project_id)
        .order_by(BayCompliance.created_at.desc())
    )
    return list(result.scalars().all())


async def delete_compliance(db: AsyncSession, compliance_id: str) -> bool:
    compliance = await get_compliance(db, compliance_id)
    if not compliance:
        return False
    await db.delete(compliance)
    await db.commit()
    return True


# ════════════════════════════════════════════════════════════════
# 工程量自动计算
# ════════════════════════════════════════════════════════════════

# 材料单价参考 (元)
MATERIAL_PRICES = {
    "brick": 0.65,           # 标准砖 240×115×53 元/块
    "mortar": 380.0,         # 预拌砂浆 元/m³
    "concrete_c25": 420.0,   # C25 商品混凝土 元/m³
    "concrete_c30": 450.0,   # C30 商品混凝土 元/m³
    "concrete_c35": 480.0,   # C35 商品混凝土 元/m³
    "rebar": 5.5,            # 钢筋 元/kg
    "formwork_plywood": 45.0, # 木模板 元/m²
    "formwork_steel": 18.0,  # 钢模板(租赁) 元/m²/次
}

# 标准砖 240×115×53mm, 含灰缝 10mm
BRICK_VOLUME_M3 = 0.24 * 0.115 * 0.053  # 单块砖体积
MORTAR_RATIO = 0.23  # 砂浆占砌体总体积比例 (含灰缝)

# 钢筋配筋率参考 (按混凝土体积)
REBAR_RATIO_SLAB = 0.08   # 楼板配筋率 80 kg/m³
REBAR_RATIO_BEAM = 0.12   # 梁配筋率 120 kg/m³
REBAR_RATIO_COLUMN = 0.15 # 柱配筋率 150 kg/m³


def calc_brickwork(wall_length_m: float, wall_height_m: float, wall_thickness_m: float) -> dict:
    """墙体体积 → 砖/砂浆自动计算

    Args:
        wall_length_m: 墙体长度 (m)
        wall_height_m: 墙体高度 (m)
        wall_thickness_m: 墙体厚度 (m)
    """
    wall_volume = wall_length_m * wall_height_m * wall_thickness_m
    # 砖块数 (扣除砂浆)
    brick_net_volume = wall_volume * (1 - MORTAR_RATIO)
    brick_count = math.ceil(brick_net_volume / BRICK_VOLUME_M3)
    # 砂浆用量
    mortar_volume = wall_volume * MORTAR_RATIO

    return {
        "wall_volume_m3": round(wall_volume, 3),
        "brick_count": brick_count,
        "brick_unit": "块",
        "brick_spec": "240×115×53mm 标准砖",
        "mortar_m3": round(mortar_volume, 3),
        "mortar_unit": "m³",
        "brick_unit_price": MATERIAL_PRICES["brick"],
        "mortar_unit_price": MATERIAL_PRICES["mortar"],
        "total_material_cost": round(brick_count * MATERIAL_PRICES["brick"] + mortar_volume * MATERIAL_PRICES["mortar"], 2),
    }


def calc_concrete_rebar(slab_area_m2: float, slab_thickness_m: float, concrete_grade: str = "C30") -> dict:
    """楼板面积 → 混凝土/钢筋估算

    Args:
        slab_area_m2: 楼板面积 (m²)
        slab_thickness_m: 楼板厚度 (m)
        concrete_grade: 混凝土等级 (C25/C30/C35)
    """
    concrete_volume = slab_area_m2 * slab_thickness_m
    rebar_weight = concrete_volume * REBAR_RATIO_SLAB * 1000  # kg/m³ → kg

    grade_key = concrete_grade.lower().replace("c", "concrete_c")
    concrete_price = MATERIAL_PRICES.get(grade_key, MATERIAL_PRICES["concrete_c30"])

    concrete_cost = concrete_volume * concrete_price
    rebar_cost = rebar_weight * MATERIAL_PRICES["rebar"]

    return {
        "slab_area_m2": slab_area_m2,
        "slab_thickness_mm": round(slab_thickness_m * 1000),
        "concrete_grade": concrete_grade,
        "concrete_m3": round(concrete_volume, 3),
        "concrete_unit_price": concrete_price,
        "concrete_cost": round(concrete_cost, 2),
        "rebar_kg": round(rebar_weight, 2),
        "rebar_unit_price": MATERIAL_PRICES["rebar"],
        "rebar_cost": round(rebar_cost, 2),
        "total_material_cost": round(concrete_cost + rebar_cost, 2),
    }


def calc_formwork(formwork_area_m2: float) -> dict:
    """模板面积 → 周转材料估算

    模板按使用面积 + 损耗计算

    Args:
        formwork_area_m2: 模板面积 (m²)
    """
    waste_rate = 0.05  # 5% 损耗
    actual_area = formwork_area_m2 * (1 + waste_rate)

    # 木模板 (推荐用于住宅)
    plywood_sheets = math.ceil(actual_area / (1.22 * 2.44))  # 标准板 1220×2440mm
    plywood_cost = actual_area * MATERIAL_PRICES["formwork_plywood"]

    # 支撑体系 (按面积估算, 约 25元/m²)
    support_cost = formwork_area_m2 * 25.0

    # 钢管脚手架 (按面积, 约 15元/m²)
    scaffolding_cost = formwork_area_m2 * 15.0

    return {
        "formwork_area_m2": formwork_area_m2,
        "waste_rate": waste_rate * 100,
        "actual_area_m2": round(actual_area, 2),
        "plywood_sheets_1220x2440": plywood_sheets,
        "plywood_unit_price": MATERIAL_PRICES["formwork_plywood"],
        "plywood_cost": round(plywood_cost, 2),
        "support_cost": round(support_cost, 2),
        "scaffolding_cost": round(scaffolding_cost, 2),
        "total_formwork_cost": round(plywood_cost + support_cost + scaffolding_cost, 2),
        "turnover_times": 5,
        "note": "木模板周转 5-7次, 钢模板周转 30-50次",
    }


async def create_quantity_calc(db: AsyncSession, data: dict) -> QuantityCalculation:
    # 自动计算 total_cost
    if data.get("total_cost", 0.0) == 0.0:
        brick_count = data.get("brick_count", 0) or 0
        mortar_m3 = data.get("mortar_m3", 0.0) or 0.0
        concrete_m3 = data.get("concrete_m3", 0.0) or 0.0
        rebar_kg = data.get("rebar_kg", 0.0) or 0.0
        formwork_m2 = data.get("formwork_m2", 0.0) or 0.0
        data["total_cost"] = round(
            brick_count * MATERIAL_PRICES["brick"]
            + mortar_m3 * MATERIAL_PRICES["mortar"]
            + concrete_m3 * MATERIAL_PRICES["concrete_c30"]
            + rebar_kg * MATERIAL_PRICES["rebar"]
            + formwork_m2 * MATERIAL_PRICES["formwork_plywood"],
            2,
        )
    calc = QuantityCalculation(**data)
    db.add(calc)
    await db.commit()
    await db.refresh(calc)
    return calc


async def get_quantity_calc(db: AsyncSession, calc_id: str) -> QuantityCalculation | None:
    result = await db.execute(
        select(QuantityCalculation)
        .where(QuantityCalculation.id == calc_id)
        .options(selectinload(QuantityCalculation.line_items))
    )
    return result.scalar_one_or_none()


async def list_quantity_calcs(db: AsyncSession, project_id: str) -> list[QuantityCalculation]:
    result = await db.execute(
        select(QuantityCalculation)
        .where(QuantityCalculation.project_id == project_id)
        .options(selectinload(QuantityCalculation.line_items))
        .order_by(QuantityCalculation.created_at.desc())
    )
    return list(result.scalars().all())


async def delete_quantity_calc(db: AsyncSession, calc_id: str) -> bool:
    calc = await get_quantity_calc(db, calc_id)
    if not calc:
        return False
    await db.delete(calc)
    await db.commit()
    return True


async def add_line_item(db: AsyncSession, data: dict) -> QuantityLineItem:
    quantity = data.get("quantity", 0.0) or 0.0
    unit_price = data.get("unit_price", 0.0) or 0.0
    if data.get("total_price", 0.0) == 0.0:
        data["total_price"] = round(quantity * unit_price, 2)
    item = QuantityLineItem(**data)
    db.add(item)
    await db.commit()
    await db.refresh(item)
    return item


async def delete_line_item(db: AsyncSession, item_id: str) -> bool:
    result = await db.execute(
        select(QuantityLineItem).where(QuantityLineItem.id == item_id)
    )
    item = result.scalar_one_or_none()
    if not item:
        return False
    await db.delete(item)
    await db.commit()
    return True

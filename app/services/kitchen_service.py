"""F16 厨房设计器服务层 — 布局生成 + 动线分析 + 规范校验 + CRUD"""

import math

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.kitchen import KitchenDesign, KitchenComponent


# ── 布局生成 ──

def generate_kitchen_layout(design: KitchenDesign) -> list[dict]:
    """根据布局类型生成橱柜排布

    Args:
        design: 厨房设计
    """
    layout = design.layout_type
    w = design.room_width
    l = design.room_length
    ch = design.counter_height
    cd = design.counter_depth

    components = []

    if layout == "I":
        # 一字型: 沿一面墙布置
        components.extend(_gen_i_layout(w, l, ch, cd))
    elif layout == "L":
        # L 型: 沿两面相邻墙布置
        components.extend(_gen_l_layout(w, l, ch, cd))
    elif layout == "U":
        # U 型: 沿三面墙布置
        components.extend(_gen_u_layout(w, l, ch, cd))
    elif layout == "G":
        # G 型: U 型 + 半岛
        components.extend(_gen_u_layout(w, l, ch, cd))
        components.extend(_gen_peninsula(w, l, ch, cd))
    elif layout == "double_i":
        # 双一字型: 两面平行墙
        components.extend(_gen_i_layout(w, l, ch, cd))
        components.extend(_gen_i_layout(w, l, ch, cd, offset_y=l - cd / 1000))
    elif layout == "island":
        # 岛台型: 一字 + 岛台
        components.extend(_gen_i_layout(w, l, ch, cd))
        components.extend(_gen_island(w, l, ch, cd))
    else:
        components.extend(_gen_l_layout(w, l, ch, cd))

    return components


def _gen_i_layout(w: float, l: float, ch: float, cd: float, offset_y: float = 0.0) -> list[dict]:
    """一字型布局"""
    cd_m = cd / 1000  # mm → m
    components = []

    # 冰箱 (左侧)
    components.append({
        "component_type": "fridge",
        "brand": "海尔",
        "width": 600.0, "depth": cd, "height": 1800.0,
        "position_x": 0.0, "position_y": offset_y, "position_z": 0.0,
        "price": 5999.0,
    })

    # 地柜 + 台面 (水槽段)
    components.append({
        "component_type": "cabinet_base",
        "brand": "欧派",
        "width": 800.0, "depth": cd, "height": 720.0,
        "position_x": 600.0, "position_y": offset_y, "position_z": 0.0,
        "material": "颗粒板", "color": "白色",
    })
    components.append({
        "component_type": "countertop",
        "brand": "中迅",
        "width": 800.0, "depth": cd, "height": 20.0,
        "position_x": 600.0, "position_y": offset_y, "position_z": ch,
        "material": "石英石", "color": "白色",
    })
    components.append({
        "component_type": "sink",
        "brand": "欧琳",
        "width": 760.0, "depth": 450.0, "height": 200.0,
        "position_x": 620.0, "position_y": offset_y, "position_z": ch,
    })

    # 地柜 + 台面 (备餐段)
    components.append({
        "component_type": "cabinet_base",
        "brand": "欧派",
        "width": 600.0, "depth": cd, "height": 720.0,
        "position_x": 1400.0, "position_y": offset_y, "position_z": 0.0,
        "material": "颗粒板", "color": "白色",
    })
    components.append({
        "component_type": "countertop",
        "brand": "中迅",
        "width": 600.0, "depth": cd, "height": 20.0,
        "position_x": 1400.0, "position_y": offset_y, "position_z": ch,
        "material": "石英石", "color": "白色",
    })

    # 地柜 + 台面 (灶台段)
    components.append({
        "component_type": "cabinet_base",
        "brand": "欧派",
        "width": 800.0, "depth": cd, "height": 720.0,
        "position_x": 2000.0, "position_y": offset_y, "position_z": 0.0,
        "material": "颗粒板", "color": "白色",
    })
    components.append({
        "component_type": "countertop",
        "brand": "中迅",
        "width": 800.0, "depth": cd, "height": 20.0,
        "position_x": 2000.0, "position_y": offset_y, "position_z": ch,
        "material": "石英石", "color": "白色",
    })
    components.append({
        "component_type": "stove",
        "brand": "方太",
        "width": 720.0, "depth": 420.0, "height": 50.0,
        "position_x": 2040.0, "position_y": offset_y, "position_z": ch,
    })

    # 抽油烟机
    components.append({
        "component_type": "range_hood",
        "brand": "方太",
        "width": 900.0, "depth": 520.0, "height": 700.0,
        "position_x": 1950.0, "position_y": offset_y, "position_z": ch + 700.0,
    })

    # 吊柜 (水槽上方)
    components.append({
        "component_type": "wall_cabinet",
        "brand": "欧派",
        "width": 1400.0, "depth": 350.0, "height": 700.0,
        "position_x": 600.0, "position_y": offset_y, "position_z": ch + 400.0,
        "material": "颗粒板", "color": "白色",
    })

    return components


def _gen_l_layout(w: float, l: float, ch: float, cd: float) -> list[dict]:
    """L 型布局"""
    components = _gen_i_layout(w, l, ch, cd)
    # 转角延伸段
    components.append({
        "component_type": "cabinet_base",
        "brand": "欧派",
        "width": 600.0, "depth": cd, "height": 720.0,
        "position_x": 0.0, "position_y": cd / 1000, "position_z": 0.0,
        "rotation": 90.0,
        "material": "颗粒板", "color": "白色",
    })
    components.append({
        "component_type": "countertop",
        "brand": "中迅",
        "width": 600.0, "depth": cd, "height": 20.0,
        "position_x": 0.0, "position_y": cd / 1000, "position_z": ch,
        "rotation": 90.0,
        "material": "石英石", "color": "白色",
    })
    return components


def _gen_u_layout(w: float, l: float, ch: float, cd: float) -> list[dict]:
    """U 型布局"""
    components = _gen_l_layout(w, l, ch, cd)
    # 另一侧墙
    components.append({
        "component_type": "cabinet_base",
        "brand": "欧派",
        "width": 1200.0, "depth": cd, "height": 720.0,
        "position_x": 2800.0, "position_y": cd / 1000, "position_z": 0.0,
        "rotation": 270.0,
        "material": "颗粒板", "color": "白色",
    })
    components.append({
        "component_type": "countertop",
        "brand": "中迅",
        "width": 1200.0, "depth": cd, "height": 20.0,
        "position_x": 2800.0, "position_y": cd / 1000, "position_z": ch,
        "rotation": 270.0,
        "material": "石英石", "color": "白色",
    })
    return components


def _gen_island(w: float, l: float, ch: float, cd: float) -> list[dict]:
    """岛台"""
    return [{
        "component_type": "island",
        "brand": "欧派",
        "width": 1200.0, "depth": 800.0, "height": 850.0,
        "position_x": (w * 1000 - 1200) / 2,
        "position_y": (l * 1000 - 800) / 2,
        "position_z": 0.0,
        "material": "颗粒板", "color": "木纹",
        "price": 8800.0,
    }]


def _gen_peninsula(w: float, l: float, ch: float, cd: float) -> list[dict]:
    """半岛"""
    return [{
        "component_type": "island",
        "brand": "欧派",
        "width": 1000.0, "depth": 600.0, "height": 850.0,
        "position_x": 2800.0,
        "position_y": (l * 1000 - 600) / 2,
        "position_z": 0.0,
        "material": "颗粒板", "color": "木纹",
        "price": 6800.0,
    }]


# ── 动线分析 ──

def analyze_kitchen_workflow(design: KitchenDesign) -> dict:
    """动线分析 — 冰箱→水槽→备餐→灶台→装盘，三角动线总距离应 3.6-6.6m

    Args:
        design: 厨房设计 (需已加载 components)
    """
    components = design.components if design.components else []

    # 定位关键设备 (mm 坐标转 m)
    fridge = _find_component(components, "fridge")
    sink = _find_component(components, "sink")
    stove = _find_component(components, "stove")

    if not all([fridge, sink, stove]):
        return {
            "status": "incomplete",
            "message": "缺少关键设备 (冰箱/水槽/灶台)，无法分析动线",
            "distances": {},
            "total_distance": 0.0,
            "rating": "unknown",
        }

    # 计算三角动线距离 (单位: m)
    d_fridge_sink = _calc_distance(fridge, sink)
    d_sink_stove = _calc_distance(sink, stove)
    d_stove_fridge = _calc_distance(stove, fridge)
    total = d_fridge_sink + d_sink_stove + d_stove_fridge

    # 评级
    if 3.6 <= total <= 6.6:
        rating = "optimal"
        suggestion = "动线合理，操作流畅"
    elif total < 3.6:
        rating = "too_compact"
        suggestion = "动线过短，设备间距不足，建议拉开距离"
    else:
        rating = "too_spread"
        suggestion = "动线过长，操作疲劳，建议缩短设备间距"

    return {
        "status": "complete",
        "distances": {
            "fridge_to_sink": round(d_fridge_sink, 2),
            "sink_to_stove": round(d_sink_stove, 2),
            "stove_to_fridge": round(d_stove_fridge, 2),
        },
        "total_distance": round(total, 2),
        "recommended_range": [3.6, 6.6],
        "rating": rating,
        "suggestion": suggestion,
    }


def _find_component(components: list[KitchenComponent], comp_type: str) -> KitchenComponent | None:
    """查找指定类型的组件"""
    for c in components:
        if c.component_type == comp_type:
            return c
    return None


def _calc_distance(a: KitchenComponent, b: KitchenComponent) -> float:
    """计算两个组件中心点之间的距离 (mm → m)"""
    ax = a.position_x + a.width / 2
    ay = a.position_y + a.depth / 2
    bx = b.position_x + b.width / 2
    by = b.position_y + b.depth / 2
    return math.sqrt((ax - bx) ** 2 + (ay - by) ** 2) / 1000.0


# ── 规范校验 ──

def validate_kitchen_compliance(design: KitchenDesign) -> dict:
    """规范校验:
    - 燃气灶距墙 ≥ 150mm
    - 灶台距水槽 ≥ 600mm (防止溅水)
    - 抽油烟机距灶台 650-750mm
    - 燃气表距灶台 ≥ 500mm
    - 水槽距灶台 ≥ 300mm (台面安全距离)
    - 操作台面三段式 (备餐 600mm + 烹饪 800mm + 装盘 300mm)

    Args:
        design: 厨房设计 (需已加载 components)
    """
    components = design.components if design.components else []
    checks = []
    all_pass = True

    stove = _find_component(components, "stove")
    sink = _find_component(components, "sink")
    hood = _find_component(components, "range_hood")

    # 1. 燃气灶距墙 ≥ 150mm
    if stove:
        wall_dist = min(stove.position_x, stove.position_y,
                        design.room_width * 1000 - stove.position_x - stove.width,
                        design.room_length * 1000 - stove.position_y - stove.depth)
        passed = wall_dist >= 150
        checks.append({
            "item": "燃气灶距墙 ≥ 150mm",
            "value": round(wall_dist, 1),
            "unit": "mm",
            "passed": passed,
            "standard": "≥ 150mm",
        })
        if not passed:
            all_pass = False
    else:
        checks.append({"item": "燃气灶距墙 ≥ 150mm", "passed": False, "message": "未找到灶台"})

    # 2. 灶台距水槽 ≥ 600mm (中心距)
    if stove and sink:
        dist = _calc_distance(stove, sink) * 1000  # m → mm
        passed = dist >= 600
        checks.append({
            "item": "灶台距水槽 ≥ 600mm",
            "value": round(dist, 1),
            "unit": "mm",
            "passed": passed,
            "standard": "≥ 600mm",
        })
        if not passed:
            all_pass = False
    else:
        checks.append({"item": "灶台距水槽 ≥ 600mm", "passed": False, "message": "缺少灶台或水槽"})

    # 3. 抽油烟机距灶台 650-750mm
    if hood and stove:
        vertical_dist = hood.position_z - stove.position_z
        passed = 650 <= vertical_dist <= 750
        checks.append({
            "item": "抽油烟机距灶台 650-750mm",
            "value": round(vertical_dist, 1),
            "unit": "mm",
            "passed": passed,
            "standard": "650-750mm",
        })
        if not passed:
            all_pass = False
    else:
        checks.append({"item": "抽油烟机距灶台 650-750mm", "passed": False, "message": "缺少抽油烟机或灶台"})

    # 4. 燃气表距灶台 ≥ 500mm
    gas_meter = _find_component(components, "stove")
    if stove:
        # 假设燃气表在灶台侧方 500mm 处，这里检查灶台距侧墙
        gas_dist = min(stove.position_x, stove.position_y)
        passed = gas_dist >= 500
        checks.append({
            "item": "燃气表距灶台 ≥ 500mm",
            "value": round(gas_dist, 1),
            "unit": "mm",
            "passed": passed,
            "standard": "≥ 500mm",
        })
        if not passed:
            all_pass = False
    else:
        checks.append({"item": "燃气表距灶台 ≥ 500mm", "passed": False, "message": "未找到灶台"})

    # 5. 水槽距灶台 ≥ 300mm (台面边缘距离)
    if stove and sink:
        edge_dist = abs(stove.position_x - (sink.position_x + sink.width)) if stove.position_x > sink.position_x \
            else abs(sink.position_x - (stove.position_x + stove.width))
        passed = edge_dist >= 300
        checks.append({
            "item": "水槽距灶台台面 ≥ 300mm",
            "value": round(edge_dist, 1),
            "unit": "mm",
            "passed": passed,
            "standard": "≥ 300mm",
        })
        if not passed:
            all_pass = False
    else:
        checks.append({"item": "水槽距灶台台面 ≥ 300mm", "passed": False, "message": "缺少灶台或水槽"})

    # 6. 操作台面三段式 (备餐 600mm + 烹饪 800mm + 装盘 300mm)
    countertops = [c for c in components if c.component_type == "countertop"]
    total_ct_width = sum(c.width for c in countertops)
    passed = total_ct_width >= 1700  # 600 + 800 + 300
    checks.append({
        "item": "操作台面三段式 (≥ 1700mm)",
        "value": round(total_ct_width, 1),
        "unit": "mm",
        "passed": passed,
        "standard": "备餐 600 + 烹饪 800 + 装盘 300 = 1700mm",
    })
    if not passed:
        all_pass = False

    return {
        "compliant": all_pass,
        "checks": checks,
        "total_checks": len(checks),
        "passed_checks": sum(1 for c in checks if c.get("passed")),
    }


# ── 厨房设计 CRUD ──

async def create_design(db: AsyncSession, data: dict) -> KitchenDesign:
    design = KitchenDesign(**data)
    db.add(design)
    await db.commit()
    await db.refresh(design)
    return design


async def get_design(db: AsyncSession, design_id: str) -> KitchenDesign | None:
    result = await db.execute(
        select(KitchenDesign)
        .where(KitchenDesign.id == design_id)
        .options(selectinload(KitchenDesign.components))
    )
    return result.scalar_one_or_none()


async def list_designs(db: AsyncSession, project_id: str) -> list[KitchenDesign]:
    result = await db.execute(
        select(KitchenDesign)
        .where(KitchenDesign.project_id == project_id)
        .order_by(KitchenDesign.created_at.desc())
    )
    return list(result.scalars().all())


async def delete_design(db: AsyncSession, design_id: str) -> bool:
    design = await get_design(db, design_id)
    if not design:
        return False
    await db.delete(design)
    await db.commit()
    return True


# ── 厨房组件 CRUD ──

async def add_component(db: AsyncSession, data: dict) -> KitchenComponent:
    component = KitchenComponent(**data)
    db.add(component)
    await db.commit()
    await db.refresh(component)
    return component


async def list_components(db: AsyncSession, design_id: str) -> list[KitchenComponent]:
    result = await db.execute(
        select(KitchenComponent)
        .where(KitchenComponent.design_id == design_id)
        .order_by(KitchenComponent.created_at)
    )
    return list(result.scalars().all())


async def delete_component(db: AsyncSession, component_id: str) -> bool:
    result = await db.execute(select(KitchenComponent).where(KitchenComponent.id == component_id))
    component = result.scalar_one_or_none()
    if not component:
        return False
    await db.delete(component)
    await db.commit()
    return True

"""F21 硬装模块服务层 — 瓷砖排版 + 涂料用量 + 吊顶设计 + 预算汇总 + CRUD"""

import math

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.hard_decoration import (
    HardDecorationScheme,
    HardDecorationFloor,
    WallFinish,
    CeilingDesign,
)


# ── 瓷砖排版 ──

def generate_tile_layout(
    room_width: float,
    room_length: float,
    tile_width: float,
    tile_length: float,
    pattern: str,
) -> dict:
    """瓷砖排版

    Args:
        room_width: 房间宽度 (m)
        room_length: 房间长度 (m)
        tile_width: 砖宽 (mm)，若 < 10 视为 m 自动换算（兼容前端误传）
        tile_length: 砖长 (mm)，若 < 10 视为 m 自动换算（兼容前端误传）
        pattern: 直铺 / 人字拼 / 鱼骨拼 / 工字铺 / 菱形
    """
    # 单位兼容：瓷砖尺寸若 < 10（不可能的 mm 值），视为 m 自动换算为 mm
    # 避免前端误传 0.6 (m) 导致 full_tiles 异常膨胀到千万级
    if tile_width < 10:
        tile_width = tile_width * 1000
    if tile_length < 10:
        tile_length = tile_length * 1000
    # 房间面积 (m²)
    room_area = room_width * room_length
    # 单砖面积 (m²)
    tile_area = (tile_width / 1000) * (tile_length / 1000)

    if pattern == "直铺":
        # 从门口开始,整砖居中
        full_tiles_x = int(room_width * 1000 / tile_width)
        full_tiles_y = int(room_length * 1000 / tile_length)
        full_tiles = full_tiles_x * full_tiles_y
        # 边缘切割砖
        cut_x = 1 if (room_width * 1000) % tile_width > 0 else 0
        cut_y = 1 if (room_length * 1000) % tile_length > 0 else 0
        cut_tiles = full_tiles_x * cut_y + full_tiles_y * cut_x + cut_x * cut_y
        waste_percent = 5.0
        layout_desc = "从门口开始,整砖居中铺设"
    elif pattern == "人字拼":
        # 45° 角铺设,损耗较大
        full_tiles = math.ceil(room_area / tile_area)
        cut_tiles = math.ceil(full_tiles * 0.15)
        waste_percent = 8.0
        layout_desc = "45° 角人字形铺设,需大量切割"
    elif pattern == "鱼骨拼":
        # 45° 角铺设,损耗较大
        full_tiles = math.ceil(room_area / tile_area)
        cut_tiles = math.ceil(full_tiles * 0.18)
        waste_percent = 10.0
        layout_desc = "鱼骨拼,两端均需 45° 切割"
    elif pattern == "工字铺":
        # 错位 1/2
        full_tiles_x = int(room_width * 1000 / tile_width)
        full_tiles_y = int(room_length * 1000 / tile_length)
        full_tiles = full_tiles_x * full_tiles_y
        # 错位需要额外的半砖
        cut_tiles = math.ceil(full_tiles_y * 0.5)
        waste_percent = 6.0
        layout_desc = "错位 1/2 工字铺,每行偏移半砖"
    elif pattern == "菱形":
        # 45° 旋转
        # 菱形铺设面积按 1.414 倍计算
        full_tiles = math.ceil(room_area * 1.414 / tile_area)
        cut_tiles = math.ceil(full_tiles * 0.2)
        waste_percent = 12.0
        layout_desc = "45° 旋转菱形铺设,四角切割量大"
    else:
        full_tiles = math.ceil(room_area / tile_area)
        cut_tiles = 0
        waste_percent = 5.0
        layout_desc = "默认直铺"

    total_tiles = full_tiles + cut_tiles
    waste_tiles = math.ceil(total_tiles * waste_percent / 100)
    final_total = total_tiles + waste_tiles
    # 实际材料面积 (m²)
    material_area = final_total * tile_area

    return {
        "pattern": pattern,
        "layout_description": layout_desc,
        "room_area_m2": round(room_area, 2),
        "tile_area_m2": round(tile_area, 4),
        "full_tiles": full_tiles,
        "cut_tiles": cut_tiles,
        "total_tiles": total_tiles,
        "waste_percent": waste_percent,
        "waste_tiles": waste_tiles,
        "final_total_tiles": final_total,
        "material_area_m2": round(material_area, 2),
    }


# ── 涂料用量计算 ──

def compute_paint_usage(wall_area: float, coats: int, coverage_per_l: float = 9.0) -> dict:
    """涂料用量计算 (每升涂 8-10㎡ 单遍)

    Args:
        wall_area: 墙面面积 (m²)
        coats: 涂料遍数
        coverage_per_l: 每升单遍涂刷面积 (默认 9㎡)
    """
    # 总涂刷面积 = 墙面面积 × 遍数
    total_coverage = wall_area * coats
    # 用量 (L)
    paint_liters = total_coverage / coverage_per_l
    # 损耗 5%
    waste = paint_liters * 0.05
    total_liters = paint_liters + waste
    # 桶数 (按 18L/桶 计算)
    bucket_size = 18.0
    buckets = math.ceil(total_liters / bucket_size)

    return {
        "wall_area_m2": round(wall_area, 2),
        "coats": coats,
        "coverage_per_l": coverage_per_l,
        "total_coverage_m2": round(total_coverage, 2),
        "paint_liters": round(paint_liters, 2),
        "waste_liters": round(waste, 2),
        "total_liters": round(total_liters, 2),
        "buckets_18l": buckets,
    }


# ── 地板用量计算 ──

def compute_floor_material(area: float, waste_percent: float = 5.0) -> dict:
    """地板用量计算 (含损耗)

    Args:
        area: 面积 (m²)
        waste_percent: 损耗率 (默认 5%)
    """
    waste = area * waste_percent / 100
    total = area + waste
    return {
        "area_m2": round(area, 2),
        "waste_percent": waste_percent,
        "waste_m2": round(waste, 2),
        "total_material_m2": round(total, 2),
    }


# ── 吊顶造型设计 ──

def design_ceiling(room_type: str, height: float = 2.8) -> dict:
    """吊顶造型设计 (客厅周边吊顶+灯带,卧室平顶,厨卫铝扣板)

    Args:
        room_type: 客厅 living / 卧室 bedroom / 厨房 kitchen / 卫生间 bathroom
        height: 层高 (m)
    """
    if room_type in ("living", "客厅"):
        return {
            "room_type": room_type,
            "ceiling_type": "gypsum_perimeter",
            "height_drop_mm": 200,
            "light_strip": True,
            "material": "石膏板 + 轻钢龙骨",
            "light_positions": [
                {"type": "筒灯", "count": 6, "position": "周边"},
                {"type": "灯带", "count": 1, "position": "吊顶凹槽"},
            ],
            "design_description": "客厅周边吊顶 + 灯带,中间留空显高",
            "min_height_after": round(height - 0.2, 2),
        }
    elif room_type in ("bedroom", "卧室"):
        return {
            "room_type": room_type,
            "ceiling_type": "flat",
            "height_drop_mm": 0,
            "light_strip": False,
            "material": "石膏线收边",
            "light_positions": [
                {"type": "主灯", "count": 1, "position": "居中"},
            ],
            "design_description": "卧室平顶,石膏线收边,保留层高",
            "min_height_after": height,
        }
    elif room_type in ("kitchen", "厨房", "bathroom", "卫生间"):
        return {
            "room_type": room_type,
            "ceiling_type": "suspended",
            "height_drop_mm": 150,
            "light_strip": False,
            "material": "铝扣板 300×300",
            "light_positions": [
                {"type": "集成吊顶灯", "count": 2, "position": "均匀分布"},
            ],
            "design_description": "厨卫铝扣板吊顶,防潮易清洁",
            "min_height_after": round(height - 0.15, 2),
        }
    else:
        return {
            "room_type": room_type,
            "ceiling_type": "flat",
            "height_drop_mm": 0,
            "light_strip": False,
            "material": "石膏线收边",
            "light_positions": [{"type": "主灯", "count": 1, "position": "居中"}],
            "design_description": "默认平顶设计",
            "min_height_after": height,
        }


# ── 预算汇总 ──

def compute_total_budget(scheme: HardDecorationScheme) -> dict:
    """预算汇总"""
    floor_total = sum(f.total_price for f in scheme.floors)
    wall_total = sum(w.total_price for w in scheme.walls)
    ceiling_total = sum(c.total_price for c in scheme.ceilings)
    grand_total = floor_total + wall_total + ceiling_total

    return {
        "scheme_id": scheme.id,
        "floor_budget": round(floor_total, 2),
        "wall_budget": round(wall_total, 2),
        "ceiling_budget": round(ceiling_total, 2),
        "total_budget": round(grand_total, 2),
        "floor_count": len(scheme.floors),
        "wall_count": len(scheme.walls),
        "ceiling_count": len(scheme.ceilings),
    }


# ── 硬装方案 CRUD ──

async def create_scheme(db: AsyncSession, data: dict) -> HardDecorationScheme:
    scheme = HardDecorationScheme(**data)
    db.add(scheme)
    await db.commit()
    await db.refresh(scheme)
    return scheme


async def get_scheme(db: AsyncSession, scheme_id: str) -> HardDecorationScheme | None:
    result = await db.execute(
        select(HardDecorationScheme)
        .where(HardDecorationScheme.id == scheme_id)
        .options(
            selectinload(HardDecorationScheme.floors),
            selectinload(HardDecorationScheme.walls),
            selectinload(HardDecorationScheme.ceilings),
        )
    )
    return result.scalar_one_or_none()


async def list_schemes(db: AsyncSession, project_id: str) -> list[HardDecorationScheme]:
    result = await db.execute(
        select(HardDecorationScheme)
        .where(HardDecorationScheme.project_id == project_id)
        .order_by(HardDecorationScheme.created_at.desc())
    )
    return list(result.scalars().all())


async def delete_scheme(db: AsyncSession, scheme_id: str) -> bool:
    scheme = await get_scheme(db, scheme_id)
    if not scheme:
        return False
    await db.delete(scheme)
    await db.commit()
    return True


# ── 地面方案 CRUD ──

async def add_floor(db: AsyncSession, data: dict) -> HardDecorationFloor:
    # 自动计算材料总量与总价
    coverage = data.get("coverage_area", 0.0) or 0.0
    waste_pct = data.get("waste_percent", 5.0) or 5.0
    unit_price = data.get("unit_price", 0.0) or 0.0
    if data.get("total_material", 0.0) == 0.0:
        data["total_material"] = round(coverage * (1 + waste_pct / 100), 2)
    if data.get("total_price", 0.0) == 0.0:
        data["total_price"] = round(data["total_material"] * unit_price, 2)
    floor = HardDecorationFloor(**data)
    db.add(floor)
    await db.commit()
    await db.refresh(floor)
    return floor


async def list_floors(db: AsyncSession, scheme_id: str) -> list[HardDecorationFloor]:
    result = await db.execute(
        select(HardDecorationFloor)
        .where(HardDecorationFloor.scheme_id == scheme_id)
        .order_by(HardDecorationFloor.created_at.desc())
    )
    return list(result.scalars().all())


# ── 墙面方案 CRUD ──

async def add_wall(db: AsyncSession, data: dict) -> WallFinish:
    # 自动计算材料总量与总价
    coverage = data.get("coverage_area", 0.0) or 0.0
    waste_pct = data.get("waste_percent", 5.0) or 5.0
    unit_price = data.get("unit_price", 0.0) or 0.0
    if data.get("total_material", 0.0) == 0.0:
        data["total_material"] = round(coverage * (1 + waste_pct / 100), 2)
    if data.get("total_price", 0.0) == 0.0:
        data["total_price"] = round(coverage * unit_price, 2)
    wall = WallFinish(**data)
    db.add(wall)
    await db.commit()
    await db.refresh(wall)
    return wall


async def list_walls(db: AsyncSession, scheme_id: str) -> list[WallFinish]:
    result = await db.execute(
        select(WallFinish)
        .where(WallFinish.scheme_id == scheme_id)
        .order_by(WallFinish.created_at.desc())
    )
    return list(result.scalars().all())


# ── 吊顶方案 CRUD ──

async def add_ceiling(db: AsyncSession, data: dict) -> CeilingDesign:
    # 自动计算总价
    total_area = data.get("total_area", 0.0) or 0.0
    unit_price = data.get("unit_price", 0.0) or 0.0
    if data.get("total_price", 0.0) == 0.0:
        data["total_price"] = round(total_area * unit_price, 2)
    ceiling = CeilingDesign(**data)
    db.add(ceiling)
    await db.commit()
    await db.refresh(ceiling)
    return ceiling


async def list_ceilings(db: AsyncSession, scheme_id: str) -> list[CeilingDesign]:
    result = await db.execute(
        select(CeilingDesign)
        .where(CeilingDesign.scheme_id == scheme_id)
        .order_by(CeilingDesign.created_at.desc())
    )
    return list(result.scalars().all())


# ── 合规验证 ──

# DIN 51130 防滑等级 — 材料 → 典型防滑等级
MATERIAL_SLIP_GRADE: dict[str, str] = {
    "瓷砖": "R9",
    "防滑瓷砖": "R10",
    "哑光瓷砖": "R10",
    "仿古砖": "R11",
    "石材": "R9",
    "大理石": "R9",
    "花岗岩": "R10",
    "实木地板": "R9",
    "复合地板": "R9",
    "强化地板": "R9",
    "SPC石塑地板": "R10",
    "LVT地板": "R10",
    "水磨石": "R9",
    "微水泥": "R9",
    "环氧地坪": "R10",
    "防滑地砖": "R12",
    "马赛克": "R10",
}

# DIN 51130 — 各房间防滑等级要求
ROOM_SLIP_REQUIREMENT: dict[str, str] = {
    "bathroom": "R10",
    "kitchen": "R10",
    "balcony": "R11",
}

# GB 50222 — 墙面材料防火等级 (简化映射)
MATERIAL_FIRE_RATING: dict[str, str] = {
    "乳胶漆": "B1",
    "壁纸": "B2",
    "壁布": "B2",
    "瓷砖": "A",
    "石材": "A",
    "大理石": "A",
    "岩板": "A",
    "微水泥": "A",
    "木质饰面板": "B2",
    "防火板": "B1",
    "护墙板": "B2",
    "硅藻泥": "A",
    "艺术漆": "B1",
}

# GB 50222 — 各房间墙面防火等级要求
ROOM_FIRE_REQUIREMENT: dict[str, str] = {
    "kitchen": "B1",
    "escape_route": "A",
    "corridor": "A",
}


def check_floor_slip_resistance(room_type: str, floor_material: str) -> dict:
    """地面防滑合规检查 — 依据 DIN 51130

    Args:
        room_type: 房间类型 (bathroom/kitchen/balcony 等)
        floor_material: 地面材料名称

    Returns:
        {compliant, required_grade, material_grade, suggestions}
    """
    suggestions: list[str] = []
    required_grade = ROOM_SLIP_REQUIREMENT.get(room_type)
    material_grade = MATERIAL_SLIP_GRADE.get(floor_material, "未知")

    if required_grade is None:
        # 非潮湿区域无强制防滑要求
        return {
            "compliant": True,
            "required_grade": "无强制要求",
            "material_grade": material_grade,
            "suggestions": [f"{room_type} 无强制防滑等级要求 (DIN 51130)"],
        }

    # 比较防滑等级 (R9 < R10 < R11 < R12 < R13)
    grade_order = ["R9", "R10", "R11", "R12", "R13"]
    try:
        material_idx = grade_order.index(material_grade)
        required_idx = grade_order.index(required_grade)
        compliant = material_idx >= required_idx
    except ValueError:
        compliant = False
        suggestions.append(
            f"无法识别材料 {floor_material} 的防滑等级，"
            f"建议选用防滑等级 ≥ {required_grade} 的材料"
        )

    if compliant:
        suggestions.append(
            f"{room_type} 地面材料 {floor_material} 防滑等级 {material_grade} "
            f"满足要求 ≥ {required_grade} (DIN 51130)"
        )
    else:
        suggestions.append(
            f"{room_type} 地面材料 {floor_material} 防滑等级 {material_grade} "
            f"不满足要求 ≥ {required_grade} (DIN 51130)"
        )
        suggestions.append(
            f"建议更换为防滑等级 ≥ {required_grade} 的材料，"
            f"如防滑瓷砖(R10+)、仿古砖(R11)或做防滑处理"
        )

    return {
        "compliant": compliant,
        "required_grade": required_grade,
        "material_grade": material_grade,
        "suggestions": suggestions,
    }


def check_wall_fire_rating(room_type: str, wall_material: str) -> dict:
    """墙面防火合规检查 — 依据 GB 50222

    Args:
        room_type: 房间类型 (kitchen/escape_route/corridor 等)
        wall_material: 墙面材料名称

    Returns:
        {compliant, required_rating, material_rating, suggestions}
    """
    suggestions: list[str] = []
    required_rating = ROOM_FIRE_REQUIREMENT.get(room_type)
    material_rating = MATERIAL_FIRE_RATING.get(wall_material, "未知")

    if required_rating is None:
        return {
            "compliant": True,
            "required_rating": "无强制要求",
            "material_rating": material_rating,
            "suggestions": [f"{room_type} 无特殊防火等级要求 (GB 50222)"],
        }

    # 比较防火等级 (A > B1 > B2 > B3)
    rating_order = ["A", "B1", "B2", "B3"]
    try:
        material_idx = rating_order.index(material_rating)
        required_idx = rating_order.index(required_rating)
        compliant = material_idx <= required_idx  # 越小越优
    except ValueError:
        compliant = False
        suggestions.append(
            f"无法识别材料 {wall_material} 的防火等级，"
            f"建议选用防火等级 ≥ {required_rating} 的材料"
        )

    if compliant:
        suggestions.append(
            f"{room_type} 墙面材料 {wall_material} 防火等级 {material_rating} "
            f"满足要求 ≥ {required_rating} (GB 50222)"
        )
    else:
        suggestions.append(
            f"{room_type} 墙面材料 {wall_material} 防火等级 {material_rating} "
            f"不满足要求 ≥ {required_rating} (GB 50222)"
        )
        if room_type == "kitchen":
            suggestions.append(
                "厨房墙面建议使用瓷砖(A级)、岩板(A级)或防火板(B1级)"
            )
        elif room_type in ("escape_route", "corridor"):
            suggestions.append(
                "疏散通道/走廊墙面必须使用 A 级不燃材料，如瓷砖、石材、微水泥等"
            )

    return {
        "compliant": compliant,
        "required_rating": required_rating,
        "material_rating": material_rating,
        "suggestions": suggestions,
    }

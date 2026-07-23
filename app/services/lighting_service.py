"""F29/F30 灯光设计器服务层 — 照度计算 + 色温规划 + AI 方案 + CRUD"""

import math

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.lighting import LightingScheme, LightingFixture

# 利用系数 (CU) 与维护系数 (MF)
UTILIZATION_COEFFICIENT = 0.7
MAINTENANCE_COEFFICIENT = 0.8

# 房间类型 → 色温映射 (单位: K)
ROOM_COLOR_TEMP = {
    "living_room": 3000,   # 客厅 暖白
    "kitchen": 4000,       # 厨房 中性白
    "bedroom": 2700,       # 卧室 暖黄
    "study": 5000,         # 书房 冷白
}

# 房间类型 → 推荐照度范围 (lux)
ROOM_ILLUMINANCE_RANGE = {
    "living_room": (100, 300),
    "kitchen": (150, 300),
    "bedroom": (75, 150),
    "study": (200, 500),
}

# 房间类型 → 推荐方案类型
ROOM_SCHEME_TYPE = {
    "living_room": "none_main",   # 客厅推荐无主灯
    "kitchen": "panel",           # 厨房推荐面板灯
    "bedroom": "none_main",       # 卧室推荐无主灯
    "study": "main_light",        # 书房推荐主灯
}


# ── 照度计算 ──

def compute_illuminance(room_area: float, ceiling_height: float, fixtures: list[LightingFixture]) -> dict:
    """照度计算 (lm/m² = 总光通量 × 利用系数 × 维护系数 / 面积)

    Args:
        room_area: 房间面积 (m²)
        ceiling_height: 层高 (m)
        fixtures: 灯具列表
    """
    total_lumens = sum(f.lumens * f.quantity for f in fixtures)
    total_power = sum(f.wattage_w * f.quantity for f in fixtures)

    if room_area <= 0:
        return {
            "total_lumens": round(total_lumens, 2),
            "total_power_w": round(total_power, 2),
            "illuminance": 0.0,
            "status": "invalid",
            "message": "房间面积无效",
        }

    illuminance = total_lumens * UTILIZATION_COEFFICIENT * MAINTENANCE_COEFFICIENT / room_area

    # 照度评级
    if illuminance < 50:
        rating = "insufficient"
    elif illuminance < 150:
        rating = "low"
    elif illuminance <= 300:
        rating = "optimal"
    elif illuminance <= 500:
        rating = "bright"
    else:
        rating = "excessive"

    return {
        "total_lumens": round(total_lumens, 2),
        "total_power_w": round(total_power, 2),
        "illuminance": round(illuminance, 2),
        "rating": rating,
        "utilization_coefficient": UTILIZATION_COEFFICIENT,
        "maintenance_coefficient": MAINTENANCE_COEFFICIENT,
    }


# ── 色温规划 ──

def plan_color_temp(scheme_type: str, room_type: str) -> dict:
    """色温规划 (客厅 3000K 暖白, 厨房 4000K 中性白, 卧室 2700K 暖黄, 书房 5000K 冷白)

    Args:
        scheme_type: 方案类型
        room_type: 房间类型
    """
    color_temp = ROOM_COLOR_TEMP.get(room_type, 3500)
    descriptions = {
        2700: "暖黄光 — 营造温馨氛围，适合卧室",
        3000: "暖白光 — 舒适自然，适合客厅",
        4000: "中性白 — 清晰明亮，适合厨房",
        5000: "冷白光 — 高效专注，适合书房",
    }
    description = descriptions.get(color_temp, "中性光")

    return {
        "room_type": room_type,
        "color_temp_k": color_temp,
        "description": description,
        "scheme_type": scheme_type,
    }


# ── 无主灯设计 ──

def design_none_main_light(scheme: LightingScheme) -> list[dict]:
    """无主灯设计 — 筒灯 + 射灯 + 灯带组合，生成 CAD 布置坐标

    Args:
        scheme: 灯光方案
    """
    area = scheme.room_area
    height = scheme.ceiling_height

    # 根据面积计算筒灯数量 (每 1.5-2 m² 一盏)
    spot_count = max(4, int(area / 2.0))
    # 灯带长度 (沿四周)
    strip_length = (area ** 0.5) * 4

    fixtures = []

    # 1. 筒灯 (均匀布置)
    cols = int((area ** 0.5) / 1.0) + 1
    rows = max(1, spot_count // cols)
    spacing_x = (area ** 0.5 * 1000) / (cols + 1)  # mm
    spacing_y = (area ** 0.5 * 1000) / (rows + 1)

    for i in range(cols):
        for j in range(rows):
            if len(fixtures) >= spot_count:
                break
            fixtures.append({
                "fixture_type": "spot",
                "brand": "西顿",
                "model": "7W 筒灯",
                "wattage_w": 7.0,
                "lumens": 560.0,
                "color_temp_k": scheme.color_temp_k or 3000,
                "beam_angle": 60.0,
                "position_x": round(spacing_x * (i + 1) / 1000, 3),  # m
                "position_y": round(spacing_y * (j + 1) / 1000, 3),
                "position_z": round(height, 3),
                "quantity": 1,
                "dimmable": True,
                "smart_control": True,
            })

    # 2. 射灯 (重点照明 - 沿墙边)
    for i in range(2):
        fixtures.append({
            "fixture_type": "spot",
            "brand": "西顿",
            "model": "12W 射灯",
            "wattage_w": 12.0,
            "lumens": 960.0,
            "color_temp_k": scheme.color_temp_k or 3000,
            "beam_angle": 24.0,
            "position_x": round(0.3 + i * 0.5, 3),
            "position_y": 0.3,
            "position_z": round(height, 3),
            "quantity": 1,
            "dimmable": True,
            "smart_control": True,
        })

    # 3. 灯带 (间接照明 - 沿吊顶四周)
    fixtures.append({
        "fixture_type": "strip",
        "brand": "欧普",
        "model": "LED 灯带 10W/m",
        "wattage_w": round(strip_length * 10, 2),
        "lumens": round(strip_length * 800, 2),
        "color_temp_k": scheme.color_temp_k or 3000,
        "beam_angle": 120.0,
        "position_x": 0.0,
        "position_y": 0.0,
        "position_z": round(height - 0.1, 3),
        "quantity": 1,
        "dimmable": True,
        "smart_control": True,
    })

    return fixtures


# ── AI 灯光方案 ──

def generate_ai_scheme(
    project_id: str,
    room_name: str,
    room_area: float,
    room_type: str,
    style: str = "modern",
) -> dict:
    """AI 灯光方案 — 规则引擎，根据房间类型推荐方案

    Args:
        project_id: 项目 ID
        room_name: 房间名称
        room_area: 房间面积
        room_type: 房间类型 (living_room/kitchen/bedroom/study)
        style: 风格 (modern/minimalist/warm/luxury)
    """
    # 推荐方案类型
    scheme_type = ROOM_SCHEME_TYPE.get(room_type, "mixed")

    # 色温规划
    color_temp = plan_color_temp(scheme_type, room_type)

    # 生成灯具列表
    fixtures = []
    if scheme_type == "none_main":
        # 无主灯: 临时构造 scheme 对象用于 design_none_main_light
        temp_scheme = type("TempScheme", (), {
            "room_area": room_area,
            "ceiling_height": 2.8,
            "color_temp_k": color_temp["color_temp_k"],
        })()
        fixtures = design_none_main_light(temp_scheme)
    else:
        # 主灯方案: 1 主灯 + 若干筒灯
        main_wattage = max(36, int(room_area * 4))
        main_lumens = main_wattage * 80
        fixtures.append({
            "fixture_type": "ceiling" if room_type != "study" else "panel",
            "brand": "欧普",
            "model": f"{main_wattage}W 吸顶灯",
            "wattage_w": float(main_wattage),
            "lumens": float(main_lumens),
            "color_temp_k": color_temp["color_temp_k"],
            "beam_angle": 120.0,
            "position_x": round(room_area ** 0.5 / 2, 3),
            "position_y": round(room_area ** 0.5 / 2, 3),
            "position_z": 2.8,
            "quantity": 1,
            "dimmable": True,
            "smart_control": style in ("modern", "luxury"),
        })
        # 辅助筒灯
        aux_count = max(2, int(room_area / 3))
        for i in range(aux_count):
            fixtures.append({
                "fixture_type": "spot",
                "brand": "西顿",
                "model": "7W 筒灯",
                "wattage_w": 7.0,
                "lumens": 560.0,
                "color_temp_k": color_temp["color_temp_k"],
                "beam_angle": 60.0,
                "position_x": round(0.5 + (i % 2) * 1.0, 3),
                "position_y": round(0.5 + (i // 2) * 1.0, 3),
                "position_z": 2.8,
                "quantity": 1,
                "dimmable": True,
                "smart_control": True,
            })

    total_lumens = sum(f["lumens"] * f.get("quantity", 1) for f in fixtures)
    total_power = sum(f["wattage_w"] * f.get("quantity", 1) for f in fixtures)

    return {
        "project_id": project_id,
        "room_name": room_name,
        "scheme_type": scheme_type,
        "room_area": room_area,
        "color_temp_k": color_temp["color_temp_k"],
        "cri": 90.0,
        "ugpr": 19.0,
        "total_lumens": round(total_lumens, 2),
        "total_power_w": round(total_power, 2),
        "notes": f"AI 推荐方案 — {color_temp['description']}",
        "fixtures": fixtures,
    }


# ── 灯光方案 CRUD ──

async def create_scheme(db: AsyncSession, data: dict) -> LightingScheme:
    scheme = LightingScheme(**data)
    db.add(scheme)
    await db.commit()
    await db.refresh(scheme)
    return scheme


async def get_scheme(db: AsyncSession, scheme_id: str) -> LightingScheme | None:
    result = await db.execute(
        select(LightingScheme)
        .where(LightingScheme.id == scheme_id)
        .options(selectinload(LightingScheme.fixtures))
    )
    return result.scalar_one_or_none()


async def list_schemes(db: AsyncSession, project_id: str) -> list[LightingScheme]:
    result = await db.execute(
        select(LightingScheme)
        .where(LightingScheme.project_id == project_id)
        .order_by(LightingScheme.created_at.desc())
    )
    return list(result.scalars().all())


async def update_scheme(db: AsyncSession, scheme_id: str, data: dict) -> LightingScheme | None:
    scheme = await get_scheme(db, scheme_id)
    if not scheme:
        return None
    for key, value in data.items():
        if value is not None:
            setattr(scheme, key, value)
    await db.commit()
    await db.refresh(scheme)
    return scheme


async def delete_scheme(db: AsyncSession, scheme_id: str) -> bool:
    scheme = await get_scheme(db, scheme_id)
    if not scheme:
        return False
    await db.delete(scheme)
    await db.commit()
    return True


# ── 灯具 CRUD ──

async def add_fixture(db: AsyncSession, data: dict) -> LightingFixture:
    fixture = LightingFixture(**data)
    db.add(fixture)
    await db.commit()
    await db.refresh(fixture)
    return fixture


async def list_fixtures(db: AsyncSession, scheme_id: str) -> list[LightingFixture]:
    result = await db.execute(
        select(LightingFixture)
        .where(LightingFixture.scheme_id == scheme_id)
        .order_by(LightingFixture.created_at)
    )
    return list(result.scalars().all())


async def delete_fixture(db: AsyncSession, fixture_id: str) -> bool:
    result = await db.execute(select(LightingFixture).where(LightingFixture.id == fixture_id))
    fixture = result.scalar_one_or_none()
    if not fixture:
        return False
    await db.delete(fixture)
    await db.commit()
    return True


# ── 合规验证 ──

# GB 50034 住宅建筑照明标准 — 各房间最低照度 (lx)
GB50034_MIN_ILLUMINANCE: dict[str, float] = {
    "living_room": 100.0,
    "bedroom": 75.0,
    "kitchen": 150.0,
    "bathroom": 100.0,
    "study": 300.0,
}

# GB 50034 — 住宅空间 UGR 上限
GB50034_RESIDENTIAL_UGR_LIMIT = 19

# GB 50034 — 住宅照度均匀度 U0 最低要求
GB50034_UNIFORMITY_MIN = 0.7


def check_illuminance_compliance(room_type: str, area_sq_m: float, total_lumens: float) -> dict:
    """照度合规检查 — 依据 GB 50034

    Args:
        room_type: 房间类型 (living_room/bedroom/kitchen/bathroom/study)
        area_sq_m: 房间面积 (m²)
        total_lumens: 灯具总光通量 (lm)

    Returns:
        {compliant, actual_lx, required_lx, room_type, suggestions}
    """
    suggestions: list[str] = []
    required_lx = GB50034_MIN_ILLUMINANCE.get(room_type)

    if required_lx is None:
        return {
            "compliant": True,
            "actual_lx": None,
            "required_lx": None,
            "room_type": room_type,
            "suggestions": [f"未知房间类型 {room_type}，跳过照度合规检查"],
        }

    if area_sq_m <= 0:
        return {
            "compliant": False,
            "actual_lx": 0.0,
            "required_lx": required_lx,
            "room_type": room_type,
            "suggestions": ["房间面积为 0 或无效，无法计算照度"],
        }

    actual_lx = total_lumens * UTILIZATION_COEFFICIENT * MAINTENANCE_COEFFICIENT / area_sq_m
    actual_lx = round(actual_lx, 1)

    compliant = actual_lx >= required_lx

    if not compliant:
        deficit = required_lx - actual_lx
        suggestions.append(
            f"当前照度 {actual_lx} lx 不满足 {room_type} 最低要求 {required_lx} lx (GB 50034)，"
            f"缺少 {deficit:.1f} lx"
        )
        # 建议增加光通量
        extra_lumens = deficit * area_sq_m / (UTILIZATION_COEFFICIENT * MAINTENANCE_COEFFICIENT)
        suggestions.append(
            f"建议增加总光通量约 {extra_lumens:.0f} lm，或增加灯具数量"
        )
    else:
        suggestions.append(
            f"当前照度 {actual_lx} lx 满足 {room_type} 最低要求 {required_lx} lx (GB 50034)"
        )

    return {
        "compliant": compliant,
        "actual_lx": actual_lx,
        "required_lx": required_lx,
        "room_type": room_type,
        "suggestions": suggestions,
    }


def check_glare_compliance(ugr_value: float) -> dict:
    """眩光合规检查 — 依据 GB 50034 住宅空间 UGR ≤ 19

    Args:
        ugr_value: 统一眩光值 (UGR)

    Returns:
        {compliant, ugr_value, ugr_limit, suggestions}
    """
    compliant = ugr_value <= GB50034_RESIDENTIAL_UGR_LIMIT
    suggestions: list[str] = []

    if compliant:
        suggestions.append(
            f"UGR {ugr_value} ≤ {GB50034_RESIDENTIAL_UGR_LIMIT}，满足住宅空间眩光限制 (GB 50034)"
        )
    else:
        suggestions.append(
            f"UGR {ugr_value} 超过住宅空间上限 {GB50034_RESIDENTIAL_UGR_LIMIT} (GB 50034)，"
            f"可能产生不适眩光"
        )
        suggestions.append("建议使用防眩灯具（深杯筒灯、格栅灯）或调整灯具安装位置")

    return {
        "compliant": compliant,
        "ugr_value": ugr_value,
        "ugr_limit": GB50034_RESIDENTIAL_UGR_LIMIT,
        "suggestions": suggestions,
    }


async def check_uniformity(lighting_scheme_id: str, db: AsyncSession) -> dict:
    """照度均匀度检查 — Emin/Eavg ≥ 0.7 (GB 50034)

    Args:
        lighting_scheme_id: 灯光方案 ID
        db: 数据库会话

    Returns:
        {compliant, uniformity_ratio, suggestions, assessment_type}
    """
    scheme = await get_scheme(db, lighting_scheme_id)
    if not scheme:
        return {
            "compliant": False,
            "uniformity_ratio": None,
            "suggestions": [f"灯光方案 {lighting_scheme_id} 不存在"],
            "assessment_type": "error",
        }

    fixtures = scheme.fixtures or await list_fixtures(db, lighting_scheme_id)

    if not fixtures:
        return {
            "compliant": False,
            "uniformity_ratio": None,
            "suggestions": ["当前方案无灯具数据，无法计算均匀度"],
            "assessment_type": "preliminary",
        }

    # 检查是否有位置坐标数据
    positioned_fixtures = [
        f for f in fixtures
        if f.position_x is not None and f.position_y is not None
    ]

    if len(positioned_fixtures) < 2:
        # 灯具数据不足，给出初步评估
        return {
            "compliant": False,
            "uniformity_ratio": None,
            "suggestions": [
                f"当前方案仅有 {len(positioned_fixtures)} 个有坐标的灯具，"
                f"无法准确计算照度均匀度",
                "建议确保灯具均匀布置，避免局部过亮或过暗",
                f"住宅空间照度均匀度 U0 应 ≥ {GB50034_UNIFORMITY_MIN} (GB 50034)",
            ],
            "assessment_type": "preliminary",
        }

    # 基于灯具光通量和位置估算照度分布
    room_side = scheme.room_area ** 0.5 if scheme.room_area else 5.0
    grid_size = 0.5  # 0.5m 网格
    grid_points: list[float] = []
    x_range = [i * grid_size for i in range(int(room_side / grid_size) + 1)]
    y_range = [i * grid_size for i in range(int(room_side / grid_size) + 1)]

    for px in x_range:
        for py in y_range:
            # 逐点计算照度 (平方反比法简化)
            point_lx = 0.0
            for f in positioned_fixtures:
                dx = px - float(f.position_x or 0)
                dy = py - float(f.position_y or 0)
                dist = (dx ** 2 + dy ** 2) ** 0.5
                # 灯具安装高度 (默认 2.8m)
                h = float(f.position_z or 2.8)
                # 照度 ∝ 光通量 × cos³θ / d²，简化为光强 / 距离²
                # 距离 = sqrt(水平距离² + 高度²)
                total_dist = (dist ** 2 + h ** 2) ** 0.5
                if total_dist < 0.1:
                    total_dist = 0.1  # 避免除零
                # 简化模型：点光源在水平面的照度
                cos_theta = h / total_dist
                illumination = (float(f.lumens or 0) * float(f.quantity or 1)
                                * cos_theta / (total_dist ** 2))
                # 加入光束角影响
                beam_angle = float(f.beam_angle or 120)
                if dist > 0:
                    angle_rad = math.atan(dist / h)
                    if angle_rad > math.radians(beam_angle / 2):
                        illumination *= 0.3  # 光束角外衰减
                point_lx += illumination

            # 应用利用系数和维护系数
            point_lx *= UTILIZATION_COEFFICIENT * MAINTENANCE_COEFFICIENT
            grid_points.append(point_lx)

    if not grid_points:
        return {
            "compliant": False,
            "uniformity_ratio": None,
            "suggestions": ["无法生成照度网格，请检查灯具数据"],
            "assessment_type": "preliminary",
        }

    emin = min(grid_points)
    eavg = sum(grid_points) / len(grid_points)

    if eavg <= 0:
        return {
            "compliant": False,
            "uniformity_ratio": None,
            "suggestions": ["平均照度为 0，请检查灯具光通量和位置数据"],
            "assessment_type": "preliminary",
        }

    uniformity = round(emin / eavg, 3)
    compliant = uniformity >= GB50034_UNIFORMITY_MIN

    suggestions: list[str] = []
    if compliant:
        suggestions.append(
            f"照度均匀度 U0={uniformity} ≥ {GB50034_UNIFORMITY_MIN}，满足 GB 50034 要求"
        )
    else:
        suggestions.append(
            f"照度均匀度 U0={uniformity} < {GB50034_UNIFORMITY_MIN}，不满足 GB 50034 要求"
        )
        suggestions.append("建议调整灯具间距、增加辅助照明或增加灯具数量以提升均匀度")

    return {
        "compliant": compliant,
        "uniformity_ratio": uniformity,
        "eavg_lx": round(eavg, 1),
        "emin_lx": round(emin, 1),
        "grid_points_count": len(grid_points),
        "required_uniformity": GB50034_UNIFORMITY_MIN,
        "suggestions": suggestions,
        "assessment_type": "full",
    }

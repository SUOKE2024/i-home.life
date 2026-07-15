"""F19 电器品类库 + F20 电器点位规划 服务层"""

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.appliance import ApplianceCategory, Appliance, AppliancePoint, ApplianceLoadCalc
from app.models.project import Room


# ════════════════════════════════════════════════════════════════
# 电器品类 CRUD
# ════════════════════════════════════════════════════════════════


async def create_category(db: AsyncSession, data: dict) -> ApplianceCategory:
    cat = ApplianceCategory(**data)
    db.add(cat)
    await db.commit()
    await db.refresh(cat)
    return cat


async def get_category(db: AsyncSession, cat_id: str) -> ApplianceCategory | None:
    result = await db.execute(select(ApplianceCategory).where(ApplianceCategory.id == cat_id))
    return result.scalar_one_or_none()


async def list_categories(db: AsyncSession) -> list[ApplianceCategory]:
    result = await db.execute(select(ApplianceCategory).order_by(ApplianceCategory.name))
    return list(result.scalars().all())


async def update_category(db: AsyncSession, cat_id: str, data: dict) -> ApplianceCategory | None:
    cat = await get_category(db, cat_id)
    if not cat:
        return None
    for k, v in data.items():
        if v is not None:
            setattr(cat, k, v)
    await db.commit()
    await db.refresh(cat)
    return cat


async def delete_category(db: AsyncSession, cat_id: str) -> bool:
    cat = await get_category(db, cat_id)
    if not cat:
        return False
    await db.delete(cat)
    await db.commit()
    return True


# ════════════════════════════════════════════════════════════════
# 电器实例 CRUD + 搜索/筛选/排序
# ════════════════════════════════════════════════════════════════


async def create_appliance(db: AsyncSession, data: dict) -> Appliance:
    appliance = Appliance(**data)
    db.add(appliance)
    await db.commit()
    await db.refresh(appliance)
    return appliance


async def get_appliance(db: AsyncSession, appliance_id: str) -> Appliance | None:
    result = await db.execute(select(Appliance).where(Appliance.id == appliance_id))
    return result.scalar_one_or_none()


async def update_appliance(db: AsyncSession, appliance_id: str, data: dict) -> Appliance | None:
    item = await get_appliance(db, appliance_id)
    if not item:
        return None
    for k, v in data.items():
        if v is not None:
            setattr(item, k, v)
    await db.commit()
    await db.refresh(item)
    return item


async def delete_appliance(db: AsyncSession, appliance_id: str) -> bool:
    item = await get_appliance(db, appliance_id)
    if not item:
        return False
    await db.delete(item)
    await db.commit()
    return True


async def search_appliances(db: AsyncSession, filters: dict) -> list[Appliance]:
    """多维筛选 + 搜索"""
    stmt = select(Appliance).where(Appliance.status == "active")

    category_id = filters.get("category_id")
    if category_id:
        stmt = stmt.where(Appliance.category_id == category_id)

    subcategory = filters.get("subcategory")
    if subcategory:
        stmt = stmt.where(Appliance.subcategory == subcategory)

    brand = filters.get("brand")
    if brand:
        stmt = stmt.where(Appliance.brand == brand)

    energy_label = filters.get("energy_label")
    if energy_label:
        stmt = stmt.where(Appliance.energy_label == energy_label)

    keyword = filters.get("keyword")
    if keyword:
        stmt = stmt.where(Appliance.name.ilike(f"%{keyword}%"))

    price_min = filters.get("price_min")
    price_max = filters.get("price_max")
    if price_min is not None:
        stmt = stmt.where(Appliance.price >= price_min)
    if price_max is not None:
        stmt = stmt.where(Appliance.price <= price_max)

    # 排序: 默认按价格升序
    sort_by = filters.get("sort_by", "price")
    sort_order = filters.get("sort_order", "asc")
    sort_col = getattr(Appliance, sort_by, Appliance.price)
    if sort_order == "desc":
        stmt = stmt.order_by(sort_col.desc())
    else:
        stmt = stmt.order_by(sort_col.asc())

    result = await db.execute(stmt)
    return list(result.scalars().all())


# ════════════════════════════════════════════════════════════════
# 电器点位规划 CRUD
# ════════════════════════════════════════════════════════════════


async def create_point(db: AsyncSession, data: dict) -> AppliancePoint:
    # 自动填充推荐信息
    if not data.get("outlet_type") and data.get("appliance_id"):
        data["outlet_type"] = await _recommend_outlet_type(db, data["appliance_id"])
    if not data.get("circuit") and data.get("appliance_id"):
        data["circuit"] = await _recommend_circuit(db, data["appliance_id"])
    point = AppliancePoint(**data)
    db.add(point)
    await db.commit()
    await db.refresh(point)
    return point


async def get_point(db: AsyncSession, point_id: str) -> AppliancePoint | None:
    result = await db.execute(select(AppliancePoint).where(AppliancePoint.id == point_id))
    return result.scalar_one_or_none()


async def update_point(db: AsyncSession, point_id: str, data: dict) -> AppliancePoint | None:
    point = await get_point(db, point_id)
    if not point:
        return None
    for k, v in data.items():
        if v is not None:
            setattr(point, k, v)
    await db.commit()
    await db.refresh(point)
    return point


async def delete_point(db: AsyncSession, point_id: str) -> bool:
    point = await get_point(db, point_id)
    if not point:
        return False
    await db.delete(point)
    await db.commit()
    return True


async def list_points_by_project(db: AsyncSession, project_id: str) -> list[AppliancePoint]:
    result = await db.execute(
        select(AppliancePoint)
        .where(AppliancePoint.project_id == project_id)
        .order_by(AppliancePoint.circuit, AppliancePoint.name)
    )
    return list(result.scalars().all())


# ── 自动推荐 ──


# 电器子类型 → 推荐插座类型
SUBCATEGORY_OUTLET_MAP: dict[str, str] = {
    "air_conditioner": "16A",
    "refrigerator": "10A",
    "washing_machine": "10A 防水",
    "water_heater": "16A",
    "tv": "10A",
    "range_hood": "10A",
    "cooktop": "16A",
    "dishwasher": "10A 防水",
    "steam_oven": "16A",
    "microwave": "10A",
    "water_purifier": "10A",
    "garbage_disposal": "10A",
    "robot_vacuum": "10A",
    "vacuum_cleaner": "10A",
    "dehumidifier": "10A",
    "fresh_air_system": "10A",
}

# 电器子类型 → 推荐回路
SUBCATEGORY_CIRCUIT_MAP: dict[str, str] = {
    "air_conditioner": "空调回路",
    "refrigerator": "厨房回路",
    "washing_machine": "卫生间回路",
    "water_heater": "卫生间回路",
    "tv": "普通插座回路",
    "range_hood": "厨房回路",
    "cooktop": "厨房回路",
    "dishwasher": "厨房回路",
    "steam_oven": "厨房回路",
    "microwave": "厨房回路",
    "water_purifier": "厨房回路",
    "garbage_disposal": "厨房回路",
    "robot_vacuum": "普通插座回路",
    "vacuum_cleaner": "普通插座回路",
    "dehumidifier": "普通插座回路",
    "fresh_air_system": "普通插座回路",
}

# 电器子类型 → 安装要求 (给水/排水/燃气/墙孔)
SUBCATEGORY_EMBEDDING_MAP: dict[str, dict] = {
    "air_conditioner": {
        "water_supply": False, "drainage": True, "gas_supply": False,
        "wall_hole": "φ65mm (空调孔)",
        "embedding_notes": "需预留空调孔和室外机位置,插座16A布置在室内机附近",
    },
    "refrigerator": {
        "water_supply": False, "drainage": False, "gas_supply": False,
        "wall_hole": None,
        "embedding_notes": "冰箱两侧预留100mm散热空间,电源10A插座地面以上300mm",
    },
    "washing_machine": {
        "water_supply": True, "drainage": True, "gas_supply": False,
        "wall_hole": None,
        "embedding_notes": "预留冷/热水给水口、专用排水口和防水插座",
    },
    "water_heater": {
        "water_supply": True, "drainage": False, "gas_supply": True,
        "wall_hole": "φ80mm (排气孔)",
        "embedding_notes": "预埋燃气管道,预留强排烟道,强制通风,插座16A带漏保",
    },
    "tv": {
        "water_supply": False, "drainage": False, "gas_supply": False,
        "wall_hole": "φ50mm (穿线管)",
        "embedding_notes": "预埋φ50mm穿线管从电视墙到电视柜,墙面留置86暗盒,预留网线和HDMI穿线",
    },
    "range_hood": {
        "water_supply": False, "drainage": False, "gas_supply": False,
        "wall_hole": "φ160mm (排烟孔)",
        "embedding_notes": "预埋止逆阀和排烟管道,插座布置在吊顶内",
    },
    "cooktop": {
        "water_supply": False, "drainage": False, "gas_supply": True,
        "wall_hole": None,
        "embedding_notes": "预埋燃气管道,台面开孔尺寸按型号确定",
    },
    "dishwasher": {
        "water_supply": True, "drainage": True, "gas_supply": False,
        "wall_hole": None,
        "embedding_notes": "预留冷/热水给水口和排水口,防水插座",
    },
    "steam_oven": {
        "water_supply": False, "drainage": False, "gas_supply": False,
        "wall_hole": None,
        "embedding_notes": "嵌入式安装需预留散热空间,16A插座",
    },
    "microwave": {
        "water_supply": False, "drainage": False, "gas_supply": False,
        "wall_hole": None,
        "embedding_notes": "单独10A插座,不建议与其他大功率电器共用回路",
    },
    "water_purifier": {
        "water_supply": True, "drainage": True, "gas_supply": False,
        "wall_hole": None,
        "embedding_notes": "预埋专用给水管路和废水排放管,预留RO膜更换操作空间",
    },
    "garbage_disposal": {
        "water_supply": False, "drainage": True, "gas_supply": False,
        "wall_hole": None,
        "embedding_notes": "水槽下方预留防水插座,排水管接口匹配Φ40mm",
    },
    "robot_vacuum": {
        "water_supply": False, "drainage": False, "gas_supply": False,
        "wall_hole": None,
        "embedding_notes": "基站附近预留地面插座,基站需离墙至少0.5m",
    },
    "vacuum_cleaner": {
        "water_supply": False, "drainage": False, "gas_supply": False,
        "wall_hole": None,
        "embedding_notes": "充电底座附近预留插座",
    },
    "dehumidifier": {
        "water_supply": False, "drainage": True, "gas_supply": False,
        "wall_hole": None,
        "embedding_notes": "预留排水管道,排水口位置低于除湿机水箱",
    },
    "fresh_air_system": {
        "water_supply": False, "drainage": False, "gas_supply": False,
        "wall_hole": "φ110mm×2 (进/排风)",
        "embedding_notes": "预埋进风和排风管道,主机吊顶安装预留检修口",
    },
}


async def _recommend_outlet_type(db: AsyncSession, appliance_id: str) -> str | None:
    app = await get_appliance(db, appliance_id)
    if not app:
        return None
    return SUBCATEGORY_OUTLET_MAP.get(app.subcategory, "10A")


async def _recommend_circuit(db: AsyncSession, appliance_id: str) -> str | None:
    app = await get_appliance(db, appliance_id)
    if not app:
        return None
    return SUBCATEGORY_CIRCUIT_MAP.get(app.subcategory, "普通插座回路")


# ════════════════════════════════════════════════════════════════
# 全屋负载计算
# ════════════════════════════════════════════════════════════════


# 线径 → 安全载流量 (铜芯线,环境温度30°C)
WIRE_GAUGE_CAPACITY: dict[str, float] = {
    "1.5mm²": 14.0,
    "2.5mm²": 23.0,
    "4mm²": 32.0,
    "6mm²": 45.0,
    "10mm²": 60.0,
}


def _recommend_wire_and_breaker(current: float) -> tuple[str, str]:
    """根据电流推荐线径和断路器"""
    if current <= 14:
        return "2.5mm²", "16A"
    elif current <= 23:
        return "2.5mm²", "20A"
    elif current <= 32:
        return "4mm²", "25A"
    elif current <= 45:
        return "6mm²", "32A"
    else:
        return "10mm²", "40A"


async def compute_load_calc(db: AsyncSession, project_id: str) -> dict:
    """全屋负载计算

    根据所有电器点位,按回路分组统计功率 → 计算电流 → 校验线径 → 建议拆分回路
    """
    points = await list_points_by_project(db, project_id)

    # 按回路分组
    circuit_groups: dict[str, list[AppliancePoint]] = {}
    for p in points:
        c = p.circuit or "未分配"
        circuit_groups.setdefault(c, []).append(p)

    circuits: list[dict] = []
    total_power = 0.0
    warnings: list[str] = []

    for circuit_name, group in circuit_groups.items():
        # 计算回路总功率
        c_power = sum(float(p.power_w or 0) for p in group)
        c_count = len(group)
        current = c_power / 220.0  # 电压 220V
        wire, breaker = _recommend_wire_and_breaker(current)

        # 校验: 查看该回路下是否有已有计算结果 (用现有线径校验)
        is_compliant = current <= 32.0  # 默认 4mm² 线路不超过 32A
        warning = None
        if current > 32:
            warning = f"回路'{circuit_name}'电流 {current:.1f}A 超过 4mm² 安全载流量 32A,建议拆分为多路"
            is_compliant = False
            warnings.append(warning)

        circuits.append({
            "circuit_name": circuit_name,
            "total_power": round(c_power, 1),
            "max_current": round(current, 1),
            "wire_gauge": wire,
            "breaker_rating": breaker,
            "is_compliant": is_compliant,
            "warning_msg": warning,
            "appliance_count": c_count,
            "appliances": [p.name for p in group],
        })
        total_power += c_power

    total_current = total_power / 220.0
    overall_compliant = len(warnings) == 0

    main_breaker = "40A"
    if total_current > 60:
        main_breaker = "63A (建议三相电)"
    elif total_current > 40:
        main_breaker = "63A"
    elif total_current > 32:
        main_breaker = "40A"

    # 持久化计算结果
    await db.execute(
        select(ApplianceLoadCalc).where(ApplianceLoadCalc.project_id == project_id)
    )
    existing = (
        await db.execute(
            select(ApplianceLoadCalc).where(ApplianceLoadCalc.project_id == project_id)
        )
    ).scalars().all()
    for e in existing:
        await db.delete(e)
    await db.flush()

    for c in circuits:
        calc = ApplianceLoadCalc(
            project_id=project_id,
            circuit_name=c["circuit_name"],
            total_power=c["total_power"],
            max_current=c["max_current"],
            wire_gauge=c["wire_gauge"],
            breaker_rating=c["breaker_rating"],
            is_compliant=c["is_compliant"],
            warning_msg=c["warning_msg"],
            appliance_count=c["appliance_count"],
        )
        db.add(calc)
    await db.commit()

    return {
        "project_id": project_id,
        "total_power": round(total_power, 1),
        "total_current": round(total_current, 1),
        "circuits": circuits,
        "main_breaker_advice": main_breaker,
        "is_overall_compliant": overall_compliant,
        "warnings": warnings,
    }


async def get_load_calcs(db: AsyncSession, project_id: str) -> list[ApplianceLoadCalc]:
    result = await db.execute(
        select(ApplianceLoadCalc)
        .where(ApplianceLoadCalc.project_id == project_id)
        .order_by(ApplianceLoadCalc.circuit_name)
    )
    return list(result.scalars().all())


# ════════════════════════════════════════════════════════════════
# 嵌入式电器尺寸匹配检查
# ════════════════════════════════════════════════════════════════

# 嵌入式电器子类型列表
EMBEDDED_SUBCATEGORIES = {
    "dishwasher", "steam_oven", "microwave",
    "range_hood", "cooktop",
}


def check_cabinet_match(
    appliance: Appliance,
    cabinet_width: float,
    cabinet_depth: float,
    cabinet_height: float,
) -> dict:
    """检查嵌入式电器与柜体尺寸是否匹配"""
    dims = appliance.dimensions or {}
    app_w = float(dims.get("width", 0))
    app_d = float(dims.get("depth", 0))
    app_h = float(dims.get("height", 0))

    if app_w == 0 or app_d == 0 or app_h == 0:
        return {
            "appliance_id": appliance.id,
            "appliance_name": appliance.name,
            "appliance_dimensions": dims,
            "cabinet_dimensions": {"width": cabinet_width, "depth": cabinet_depth, "height": cabinet_height},
            "fits": False,
            "clearance": None,
            "issues": ["电器尺寸信息不完整,无法进行匹配检查"],
            "suggestions": ["请补全电器的宽/深/高尺寸信息"],
        }

    # 嵌入式电器需要柜体内部尺寸略大于电器外形尺寸
    # 建议单边间隙 5-15mm
    clearance_w = cabinet_width - app_w
    clearance_d = cabinet_depth - app_d
    clearance_h = cabinet_height - app_h

    issues: list[str] = []
    suggestions: list[str] = []

    if clearance_w < 5:
        issues.append(f"宽度间隙不足: {clearance_w:.0f}mm (需 ≥5mm)")
        suggestions.append(f"柜体宽度需增加 {5 - clearance_w:.0f}mm 或选择宽度 ≤{cabinet_width - 5:.0f}mm 的电器")
    elif clearance_w > 20:
        issues.append(f"宽度间隙过大: {clearance_w:.0f}mm (建议 5-20mm)")
        suggestions.append("间隙过大可能导致电器晃动,建议加装填充条")

    if clearance_d < 5:
        issues.append(f"深度间隙不足: {clearance_d:.0f}mm (需 ≥5mm)")
        suggestions.append(f"柜体深度需增加 {5 - clearance_d:.0f}mm 或选择深度 ≤{cabinet_depth - 5:.0f}mm 的电器")

    if clearance_h < 5:
        issues.append(f"高度间隙不足: {clearance_h:.0f}mm (需 ≥5mm)")
        suggestions.append(f"柜体高度需增加 {5 - clearance_h:.0f}mm 或选择高度 ≤{cabinet_height - 5:.0f}mm 的电器")

    fits = len([i for i in issues if "不足" in i]) == 0

    return {
        "appliance_id": appliance.id,
        "appliance_name": appliance.name,
        "appliance_dimensions": {"width": app_w, "depth": app_d, "height": app_h},
        "cabinet_dimensions": {"width": cabinet_width, "depth": cabinet_depth, "height": cabinet_height},
        "fits": fits,
        "clearance": {
            "width": round(clearance_w, 1),
            "depth": round(clearance_d, 1),
            "height": round(clearance_h, 1),
        },
        "issues": issues,
        "suggestions": suggestions,
    }


# ════════════════════════════════════════════════════════════════
# 预埋规划引擎
# ════════════════════════════════════════════════════════════════


async def plan_embedding(db: AsyncSession, project_id: str) -> dict:
    """预埋规划引擎

    遍历项目的所有电器点位,按品类生成预埋要求清单:
    - 空调: 空调孔 + 电源 + 室外机平台
    - 洗衣机: 给排水 + 电源
    - 热水器: 燃气 + 强排孔 + 电源
    - 冰箱: 电源
    - 电视: 穿线管 + 电源 + 网线
    """
    points = await list_points_by_project(db, project_id)
    items: list[dict] = []
    seen_categories: set[str] = set()

    for p in points:
        if not p.appliance_id:
            continue

        app = await get_appliance(db, p.appliance_id)
        if not app:
            continue

        sub = app.subcategory
        embedding = SUBCATEGORY_EMBEDDING_MAP.get(sub)
        if not embedding:
            continue

        # 同品类去重 (每个品类只输出一次)
        if sub in seen_categories:
            continue
        seen_categories.add(sub)

        item = {
            "appliance_subcategory": sub,
            "appliance_name": app.name,
            "water_supply": embedding.get("water_supply", False),
            "drainage": embedding.get("drainage", False),
            "gas_supply": embedding.get("gas_supply", False),
            "wall_hole": embedding.get("wall_hole"),
            "outlet_type": SUBCATEGORY_OUTLET_MAP.get(sub, "10A"),
            "embedding_notes": embedding.get("embedding_notes", ""),
        }
        items.append(item)

    summary_lines: list[str] = []
    if any(it["water_supply"] for it in items):
        summary_lines.append("★ 涉水电器: 需在水电阶段预留给水管道,建议同时安装前置过滤器")
    if any(it["drainage"] for it in items):
        summary_lines.append("★ 排水电器: 需预留排水管道,注意排水坡度 ≥1%")
    if any(it["gas_supply"] for it in items):
        summary_lines.append("★ 燃气电器: 需燃气公司审批,预埋燃气管线(不锈钢波纹管),安装燃气报警器")
    if any(it["wall_hole"] for it in items):
        summary_lines.append("★ 墙孔预留: 需在水电阶段开好空调孔/烟道孔/排气孔,避免后期开孔污染墙面")

    return {
        "project_id": project_id,
        "items": items,
        "summary": "\n".join(summary_lines) if summary_lines else "无特殊预埋要求",
    }


# ════════════════════════════════════════════════════════════════
# 按房间推荐电器
# ════════════════════════════════════════════════════════════════

# 房间类型 → 推荐电器子类型 + 数量 + 默认功率 + 预估价格
ROOM_APPLIANCE_PRESETS: dict[str, list[dict]] = {
    "living_room": [
        {"subcategory": "air_conditioner", "label": "客厅空调", "qty": 1, "default_power_w": 2500, "default_price": 6000},
        {"subcategory": "tv", "label": "电视机", "qty": 1, "default_power_w": 150, "default_price": 5000},
        {"subcategory": "robot_vacuum", "label": "扫地机器人", "qty": 1, "default_power_w": 50, "default_price": 3000},
        {"subcategory": "air_conditioner", "label": "新风系统", "qty": 1, "default_power_w": 120, "default_price": 8800},
    ],
    "bedroom": [
        {"subcategory": "air_conditioner", "label": "卧室空调", "qty": 1, "default_power_w": 2000, "default_price": 4000},
        {"subcategory": "air_conditioner", "label": "除湿机", "qty": 1, "default_power_w": 500, "default_price": 2000},
    ],
    "kitchen": [
        {"subcategory": "refrigerator", "label": "冰箱", "qty": 1, "default_power_w": 150, "default_price": 5000},
        {"subcategory": "range_hood", "label": "油烟机", "qty": 1, "default_power_w": 200, "default_price": 3000},
        {"subcategory": "cooktop", "label": "燃气灶", "qty": 1, "default_power_w": 0, "default_price": 2000},
        {"subcategory": "dishwasher", "label": "洗碗机", "qty": 1, "default_power_w": 1800, "default_price": 4500},
        {"subcategory": "steam_oven", "label": "蒸烤箱", "qty": 1, "default_power_w": 2500, "default_price": 5000},
        {"subcategory": "microwave", "label": "微波炉", "qty": 1, "default_power_w": 1000, "default_price": 800},
        {"subcategory": "water_purifier", "label": "净水器", "qty": 1, "default_power_w": 50, "default_price": 2500},
        {"subcategory": "garbage_disposal", "label": "垃圾处理器", "qty": 1, "default_power_w": 500, "default_price": 2000},
    ],
    "bathroom": [
        {"subcategory": "water_heater", "label": "热水器", "qty": 1, "default_power_w": 3000, "default_price": 3000},
        {"subcategory": "washing_machine", "label": "洗衣机", "qty": 1, "default_power_w": 2000, "default_price": 4000},
    ],
}

# 房间类型映射 (room_type → preset key)
ROOM_TYPE_MAP: dict[str, str] = {
    "living_room": "living_room",
    "餐厅": "living_room",
    "dining_room": "kitchen",
    "bedroom": "bedroom",
    "kitchen": "kitchen",
    "bathroom": "bathroom",
}


async def recommend_for_room(db: AsyncSession, room_id: str) -> dict:
    """按房间推荐电器"""
    result = await db.execute(select(Room).where(Room.id == room_id))
    room = result.scalar_one_or_none()

    if not room:
        return {
            "room_id": room_id,
            "room_type": "unknown",
            "room_name": None,
            "recommended": [],
            "total_power": 0.0,
            "total_price": 0.0,
            "notes": ["房间不存在"],
        }

    preset_key = ROOM_TYPE_MAP.get(room.room_type, "living_room") if hasattr(room, 'room_type') else "living_room"
    presets = ROOM_APPLIANCE_PRESETS.get(preset_key, [])

    recommended: list[dict] = []
    total_power = 0.0
    total_price = 0.0
    notes: list[str] = []

    for cfg in presets:
        # 查找数据库中匹配的电器
        stmt = (
            select(Appliance)
            .where(
                Appliance.subcategory == cfg["subcategory"],
                Appliance.status == "active",
            )
            .order_by(Appliance.price.asc())
            .limit(1)
        )
        res = await db.execute(stmt)
        matched = res.scalar_one_or_none()

        if matched:
            unit_price = float(matched.price)
            power = float(matched.power_rating or cfg["default_power_w"])
            item = {
                "appliance_id": matched.id,
                "name": matched.name,
                "brand": matched.brand,
                "subcategory": matched.subcategory,
                "label": cfg["label"],
                "qty": cfg["qty"],
                "unit_price": unit_price,
                "subtotal": round(unit_price * cfg["qty"], 2),
                "power_w": power,
                "energy_label": matched.energy_label,
            }
        else:
            item = {
                "appliance_id": None,
                "name": cfg["label"],
                "brand": None,
                "subcategory": cfg["subcategory"],
                "label": cfg["label"],
                "qty": cfg["qty"],
                "unit_price": cfg["default_price"],
                "subtotal": round(cfg["default_price"] * cfg["qty"], 2),
                "power_w": cfg["default_power_w"],
                "energy_label": None,
            }

        recommended.append(item)
        total_power += item["power_w"] * cfg["qty"]
        total_price += item["subtotal"]

    if preset_key == "kitchen":
        notes.append("厨房电器点位密度高,建议单独设置厨房配电回路(4mm² 线径,25A 断路器)")

    return {
        "room_id": room_id,
        "room_type": getattr(room, 'room_type', 'unknown'),
        "room_name": getattr(room, 'name', None),
        "recommended": recommended,
        "total_power": round(total_power, 1),
        "total_price": round(total_price, 2),
        "notes": notes,
    }

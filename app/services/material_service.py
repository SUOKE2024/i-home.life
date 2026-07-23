import time
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from sqlalchemy.orm import selectinload

from app.models.material import MaterialCategory, Material, BOMItem
from app.models.project import Floor, Room


# 标准损耗系数
WASTE_FACTOR = {
    "flooring": 1.05,   # 地面 5% 损耗
    "wall": 1.08,       # 墙面 8% 损耗
    "ceiling": 1.05,    # 顶面 5% 损耗
}

# 墙地比（墙面面积 / 地面面积）经验值
WALL_TO_FLOOR_RATIO = 2.8

# 涂料每桶覆盖面积（18L 桶，1底2面 ≈ 90 m²）
PAINT_COVERAGE_PER_BUCKET = 90.0

# 各房间类型默认物料品类映射
ROOM_CATEGORY_MAP: dict[str, list[str]] = {
    "bedroom": ["flooring", "wall", "ceiling", "doors_windows", "custom_furniture"],
    "living": ["flooring", "wall", "ceiling", "doors_windows"],
    "kitchen": ["flooring", "wall", "ceiling", "kitchen_bath", "custom_furniture"],
    "bathroom": ["flooring", "wall", "ceiling", "kitchen_bath", "doors_windows"],
    "balcony": ["flooring", "wall", "ceiling"],
    "dining": ["flooring", "wall", "ceiling"],
    "study": ["flooring", "wall", "ceiling", "custom_furniture"],
}


# ── 简单 TTL 内存缓存（v1.1.12 性能优化） ──
# 适用于高频读、低频写的目录数据（物料分类、家具目录）
_CACHE_TTL = 60  # 秒
_cache_store: dict[str, tuple[float, Any]] = {}


def _cache_get(key: str) -> Any | None:
    """命中返回缓存值，未命中或过期返回 None"""
    entry = _cache_store.get(key)
    if entry is None:
        return None
    exp_at, value = entry
    if time.monotonic() >= exp_at:
        _cache_store.pop(key, None)
        return None
    return value


def _cache_set(key: str, value: Any, ttl: int = _CACHE_TTL) -> None:
    _cache_store[key] = (time.monotonic() + ttl, value)


def invalidate_material_cache() -> None:
    """清除物料/分类缓存（写操作后调用）"""
    _cache_store.pop("categories", None)
    # 清除所有 materials: 前缀的缓存
    keys_to_remove = [k for k in _cache_store if k.startswith("materials:")]
    for k in keys_to_remove:
        _cache_store.pop(k, None)


async def get_categories(db: AsyncSession) -> list[MaterialCategory]:
    cached = _cache_get("categories")
    if cached is not None:
        return cached
    result = await db.execute(
        select(MaterialCategory).order_by(MaterialCategory.code)
    )
    categories = list(result.scalars().all())
    _cache_set("categories", categories)
    return categories


async def get_category_by_id(db: AsyncSession, category_id: str) -> MaterialCategory | None:
    result = await db.execute(
        select(MaterialCategory).where(MaterialCategory.id == category_id)
    )
    return result.scalar_one_or_none()


async def create_category(db: AsyncSession, data: dict) -> MaterialCategory:
    category = MaterialCategory(**data)
    db.add(category)
    await db.commit()
    await db.refresh(category)
    invalidate_material_cache()
    return category


async def get_materials(
    db: AsyncSession, category_id: str | None = None, skip: int = 0, limit: int = 50
) -> list[Material]:
    stmt = (
        select(Material)
        .where(Material.is_active.is_(True))
        .options(selectinload(Material.category))
        .offset(skip)
        .limit(limit)
        .order_by(Material.created_at.desc())
    )
    if category_id:
        stmt = stmt.where(Material.category_id == category_id)

    result = await db.execute(stmt)
    return list(result.scalars().all())


async def get_material_by_id(db: AsyncSession, material_id: str) -> Material | None:
    result = await db.execute(
        select(Material)
        .where(Material.id == material_id)
        .options(selectinload(Material.category))
    )
    return result.scalar_one_or_none()


async def create_material(db: AsyncSession, data: dict) -> Material:
    material = Material(**data)
    db.add(material)
    await db.commit()
    await db.refresh(material)
    invalidate_material_cache()
    return await get_material_by_id(db, material.id)


async def add_bom_item(db: AsyncSession, data: dict) -> BOMItem:
    total = data["quantity"] * data["unit_price"]
    bom_item = BOMItem(**data, total_price=total)
    db.add(bom_item)
    await db.commit()
    await db.refresh(bom_item)
    return bom_item


async def get_project_bom(db: AsyncSession, project_id: str) -> list[BOMItem]:
    result = await db.execute(
        select(BOMItem)
        .where(BOMItem.project_id == project_id)
        .options(selectinload(BOMItem.material).selectinload(Material.category))
        .order_by(BOMItem.created_at.desc())
    )
    return list(result.scalars().all())


async def delete_bom_item(db: AsyncSession, bom_id: str) -> bool:
    result = await db.execute(select(BOMItem).where(BOMItem.id == bom_id))
    item = result.scalar_one_or_none()
    if not item:
        return False
    await db.delete(item)
    await db.commit()
    return True


async def get_bom_summary(db: AsyncSession, project_id: str) -> dict | None:
    """BOM 汇总（按品类聚合） — F6/F7 配套"""
    bom_items = await get_project_bom(db, project_id)
    if not bom_items:
        return None

    cat_map: dict[str, dict] = {}
    total_price = 0.0
    for item in bom_items:
        cat = item.material.category if item.material and item.material.category else None
        code = cat.code if cat else "unknown"
        name = cat.name if cat else "未分类"
        if code not in cat_map:
            cat_map[code] = {
                "category_code": code,
                "category_name": name,
                "item_count": 0,
                "total_price": 0.0,
            }
        cat_map[code]["item_count"] += 1
        cat_map[code]["total_price"] = round(cat_map[code]["total_price"] + item.total_price, 2)
        total_price = round(total_price + item.total_price, 2)

    return {
        "project_id": project_id,
        "total_items": len(bom_items),
        "total_price": total_price,
        "categories": list(cat_map.values()),
    }


def _calc_material_quantity(category_code: str, material: Material, room: Room) -> float:
    """根据品类、物料和房间计算用量"""
    area = room.area or 10.0

    if category_code == "flooring":
        return round(area * WASTE_FACTOR["flooring"], 2)
    if category_code == "ceiling":
        return round(area * WASTE_FACTOR["ceiling"], 2)
    if category_code == "wall":
        wall_area = area * WALL_TO_FLOOR_RATIO
        # 涂料按桶计
        if material.unit and "桶" in material.unit:
            buckets = wall_area / PAINT_COVERAGE_PER_BUCKET
            # 整桶向上取整
            return float(int(buckets) + (1 if buckets % 1 > 0 else 0))
        return round(wall_area * WASTE_FACTOR["wall"], 2)
    if category_code == "doors_windows":
        # 卧室/卫生间按 1 扇门
        if room.room_type in ("bedroom", "bathroom"):
            return 1.0
        return 0.0
    if category_code == "kitchen_bath":
        # 卫生间默认 1 套卫浴（马桶/花洒/洗手盆各 1）
        # 厨房默认 1 个水槽 + 1 m 台面
        if room.room_type == "bathroom":
            return 1.0
        if room.room_type == "kitchen":
            # 台面按 m 计，其他按个/套计
            if material.unit == "m":
                return 3.0
            return 1.0
        return 0.0
    if category_code == "custom_furniture":
        # 卧室：衣柜按投影面积 = 房间面积 × 0.6
        # 厨房：橱柜按 m 计，默认 3m
        # 书房：书柜按 m² 计，默认房间面积 × 0.3
        if room.room_type == "bedroom":
            return round(area * 0.6, 2)
        if room.room_type == "kitchen":
            return 3.0
        if room.room_type == "study":
            return round(area * 0.3, 2)
        return 0.0
    return 1.0


async def generate_bom_for_project(db: AsyncSession, project_id: str) -> list[BOMItem]:
    """F6 BOM 自动生成

    基于项目房间面积/类型，按标准用量自动生成 BOM 物料清单。
    若项目已有 BOM 项则抛出 ValueError("PROJECT_ALREADY_HAS_BOM")。
    若项目无房间则返回空列表。
    """
    existing = await get_project_bom(db, project_id)
    if existing:
        raise ValueError("PROJECT_ALREADY_HAS_BOM")

    # 取项目下所有房间
    room_result = await db.execute(
        select(Room).join(Floor, Floor.id == Room.floor_id).where(Floor.project_id == project_id)
    )
    rooms = list(room_result.scalars().all())
    if not rooms:
        return []

    # 取所有启用物料，按品类 code 取首条作为默认物料
    mat_result = await db.execute(
        select(Material)
        .where(Material.is_active.is_(True))
        .options(selectinload(Material.category))
        .order_by(Material.created_at.asc())
    )
    all_materials = list(mat_result.scalars().all())
    materials_by_category: dict[str, Material] = {}
    for m in all_materials:
        code = m.category.code if m.category else None
        if code and code not in materials_by_category:
            materials_by_category[code] = m

    # 聚合：material_id -> (quantity, note)
    aggregated: dict[str, dict] = {}
    for room in rooms:
        cats = ROOM_CATEGORY_MAP.get(room.room_type, ["flooring", "wall", "ceiling"])
        for code in cats:
            mat = materials_by_category.get(code)
            if not mat:
                continue
            qty = _calc_material_quantity(code, mat, room)
            if qty <= 0:
                continue
            if mat.id not in aggregated:
                aggregated[mat.id] = {"quantity": 0.0, "rooms": []}
            aggregated[mat.id]["quantity"] = round(aggregated[mat.id]["quantity"] + qty, 2)
            aggregated[mat.id]["rooms"].append(room.name or room.room_type)

    # 创建 BOM 项
    new_items: list[BOMItem] = []
    for mat_id, info in aggregated.items():
        mat = next(m for m in all_materials if m.id == mat_id)
        total = round(info["quantity"] * mat.unit_price, 2)
        note = f"自动生成（覆盖房间：{', '.join(info['rooms'])}）"
        item = BOMItem(
            project_id=project_id,
            material_id=mat_id,
            quantity=info["quantity"],
            unit_price=mat.unit_price,
            total_price=total,
            note=note,
            status="auto_generated",
        )
        db.add(item)
        new_items.append(item)

    await db.commit()

    # 重新查询以加载关联
    result = await db.execute(
        select(BOMItem)
        .where(BOMItem.project_id == project_id)
        .options(selectinload(BOMItem.material).selectinload(Material.category))
        .order_by(BOMItem.created_at.asc())
    )
    return list(result.scalars().all())


async def search_materials(
    db: AsyncSession, keyword: str, skip: int = 0, limit: int = 50
) -> list[Material]:
    """按名称/SKU/品牌模糊搜索物料"""
    pattern = f"%{keyword}%"
    stmt = (
        select(Material)
        .where(
            Material.is_active.is_(True),
            (Material.name.ilike(pattern))
            | (Material.sku.ilike(pattern))
            | (Material.brand.ilike(pattern)),
        )
        .options(selectinload(Material.category))
        .offset(skip)
        .limit(limit)
        .order_by(Material.created_at.desc())
    )
    result = await db.execute(stmt)
    return list(result.scalars().all())


# ── 房间类型 → 物料品类映射 ──
ROOM_TO_CATEGORY_MAP: dict[str, list[str]] = {
    "living": ["flooring", "wall", "ceiling", "doors_windows"],
    "bedroom": ["flooring", "wall", "ceiling", "doors_windows", "custom_furniture"],
    "kitchen": ["flooring", "wall", "ceiling", "kitchen_bath", "custom_furniture"],
    "bathroom": ["flooring", "wall", "ceiling", "kitchen_bath", "doors_windows"],
    "dining": ["flooring", "wall", "ceiling"],
    "study": ["flooring", "wall", "ceiling", "custom_furniture"],
    "balcony": ["flooring", "wall", "ceiling"],
}

# ── 风格 → 关键词映射 ──
STYLE_KEYWORD_MAP: dict[str, list[str]] = {
    "modern": ["现代", "简约", "极简", "现代简约"],
    "nordic": ["北欧", "斯堪的纳维亚"],
    "chinese": ["新中式", "中式", "东方"],
    "american": ["美式", "美式经典", "美式乡村"],
    "french": ["法式", "法式浪漫"],
    "industrial": ["工业", "工业风", "loft"],
    "japanese": ["日式", "和风", "侘寂"],
    "luxury": ["轻奢", "奢华", "高端"],
}


def _calc_match_score(
    material: Material,
    target_categories: list[str],
    style: str | None,
    budget_level: str | None,
) -> int:
    """计算物料匹配分数 (0-100)"""
    score = 0

    # 品类匹配 (0-50 分)
    cat_code = material.category.code if material.category else ""
    if cat_code in target_categories:
        score += 50

    # 风格匹配 (0-25 分)
    if style:
        keywords = STYLE_KEYWORD_MAP.get(style, [])
        text = (material.name or "") + " " + (material.description or "")
        for kw in keywords:
            if kw in text:
                score += 25
                break
        else:
            # 部分匹配给一半分数
            for kw in keywords:
                for sub_kw in kw:
                    if sub_kw in text:
                        score += 10
                        break

    # 品牌加分 (0-10 分)
    if material.brand:
        score += 5
        if material.brand in ("立邦", "多乐士", "三棵树", "马可波罗", "东鹏", "诺贝尔", "科勒", "TOTO", "方太", "老板", "欧派", "索菲亚"):
            score += 5

    # 规格/描述丰富度 (0-5 分)
    if material.spec and len(material.spec) > 20:
        score += 5

    # 价格合理性 (0-10 分) — 根据预算等级调整
    if budget_level:
        if budget_level == "economy" and material.unit_price <= 150:
            score += 10
        elif budget_level == "standard" and 50 <= material.unit_price <= 500:
            score += 10
        elif budget_level == "premium" and material.unit_price >= 300:
            score += 10
    else:
        score += 5  # 无预算偏好的基础分

    return min(score, 100)


def _derive_budget_level(budget: "Budget | None") -> str:
    """根据预算推断等级"""
    if not budget or not budget.total_estimated:
        return "standard"
    total = budget.total_estimated
    if total < 80000:
        return "economy"
    elif total > 200000:
        return "premium"
    return "standard"


def _estimate_environmental_grade(material: Material) -> str:
    """从物料名称/规格推断环保等级"""
    text = (material.name or "") + " " + (material.spec or "") + " " + (material.description or "")
    if "E0" in text:
        return "E0"
    if "E1" in text:
        return "E1"
    if "F4" in text or "F☆☆☆☆" in text:
        return "F4"
    if "零甲醛" in text or "无醛" in text or "ENF" in text:
        return "ENF"
    if "A+" in text or "A+级" in text:
        return "A+"
    if material.category and material.category.code in ("flooring", "custom_furniture"):
        return "E1"  # 板材类默认 E1
    return "A"


async def recommend_materials(
    db: AsyncSession,
    project_id: str,
    room_type: str | None = None,
    style: str | None = None,
    budget_level: str | None = None,  # "economy" / "standard" / "premium"
) -> dict:
    """AI 物料推荐引擎

    基于项目预算、房间类型和风格偏好，从数据库中筛选并推荐物料。
    每个品类返回 top 5 推荐，含匹配分数和推荐理由。
    """
    from app.models.budget import Budget
    from app.models.procurement import Quotation

    # 1. 获取项目预算并推断预算等级
    budget_result = await db.execute(
        select(Budget).where(Budget.project_id == project_id)
    )
    budget = budget_result.scalar_one_or_none()

    if not budget_level:
        budget_level = _derive_budget_level(budget)

    total_budget = budget.total_estimated if budget else 0.0
    if total_budget <= 0:
        total_budget = 100000.0  # 默认 10 万

    # 2. 确定目标品类
    if room_type:
        target_categories = ROOM_TO_CATEGORY_MAP.get(
            room_type, ["flooring", "wall", "ceiling"]
        )
    else:
        target_categories = None  # 不限制品类

    # 3. 查询所有活跃物料
    all_materials = await get_materials(db, limit=1000)

    # 如果指定了品类，过滤
    if target_categories:
        all_materials = [
            m for m in all_materials
            if m.category and m.category.code in target_categories
        ]

    if not all_materials:
        return {
            "project_id": project_id,
            "budget_level": budget_level,
            "total_budget": round(total_budget, 2),
            "recommendations": [],
            "total_estimated_cost": 0.0,
            "budget_utilization_percent": 0.0,
            "alternative_suggestions": ["当前数据库中暂无匹配物料，请先添加物料数据"],
        }

    # 4. 为每个物料计算匹配分数
    scored_materials: list[tuple[Material, int]] = []
    for m in all_materials:
        score = _calc_match_score(m, target_categories or [], style, budget_level)
        scored_materials.append((m, score))

    # 5. 按品类分组，每个品类取 top 5
    grouped: dict[str, list[tuple[Material, int]]] = {}
    for m, score in scored_materials:
        cat_code = m.category.code if m.category else "unknown"
        if cat_code not in grouped:
            grouped[cat_code] = []
        grouped[cat_code].append((m, score))

    # 按预算等级排序
    for cat_code in grouped:
        if budget_level == "economy":
            # 低价优先，同价格按分数降序
            grouped[cat_code].sort(key=lambda x: (x[0].unit_price, -x[1]))
        elif budget_level == "premium":
            # 高价优先，同价格按分数降序
            grouped[cat_code].sort(key=lambda x: (-x[0].unit_price, -x[1]))
        else:
            # 标准：按分数降序
            grouped[cat_code].sort(key=lambda x: -x[1])

        # 只保留 top 5
        grouped[cat_code] = grouped[cat_code][:5]

    # 6. 生成推荐结果
    recommendations: list[dict] = []
    total_material_cost = 0.0

    # 为每个物料的 supplier 做批量查询
    supplier_cache: dict[str, str] = {}  # material_id -> supplier_name

    for cat_code, items in grouped.items():
        for m, score in items:
            # 查询供应商信息 (若有报价)
            if m.id not in supplier_cache:
                q_result = await db.execute(
                    select(Quotation)
                    .where(Quotation.material_id == m.id)
                    .options(selectinload(Quotation.supplier))
                    .order_by(Quotation.unit_price.asc())
                    .limit(1)
                )
                quotation = q_result.scalar_one_or_none()
                if quotation and quotation.supplier:
                    supplier_cache[m.id] = quotation.supplier.name
                else:
                    supplier_cache[m.id] = m.brand or "未指定"

            # 估算用量（默认 50㎡面积用量）
            estimated_qty = 50.0
            cat_code_val = m.category.code if m.category else ""
            if cat_code_val in WASTE_FACTOR:
                estimated_qty = round(50.0 * WASTE_FACTOR[cat_code_val], 2)
            if cat_code_val == "wall" and m.unit and "桶" in m.unit:
                wall_area = 50.0 * WALL_TO_FLOOR_RATIO
                buckets = wall_area / PAINT_COVERAGE_PER_BUCKET
                estimated_qty = float(int(buckets) + (1 if buckets % 1 > 0 else 0))

            estimated_cost = round(estimated_qty * m.unit_price, 2)
            total_material_cost += estimated_cost

            # 生成推荐理由
            reasons: list[str] = []
            if cat_code_val in (target_categories or []):
                reasons.append(f"匹配目标房间类型")
            if style:
                style_kws = STYLE_KEYWORD_MAP.get(style, [])
                text = (m.name or "") + " " + (m.description or "")
                matched_kw = next((kw for kw in style_kws if kw in text), None)
                if matched_kw:
                    reasons.append(f"风格匹配「{matched_kw}」")
            if m.brand:
                reasons.append(f"品牌「{m.brand}」")
            if budget_level == "economy" and m.unit_price <= 100:
                reasons.append("经济实惠")
            elif budget_level == "premium" and m.unit_price >= 300:
                reasons.append("高端品质")
            if not reasons:
                reasons.append("综合评分较高")

            recommendations.append({
                "material_id": m.id,
                "name": m.name,
                "category": m.category.name if m.category else "未分类",
                "category_code": cat_code_val,
                "unit_price": m.unit_price,
                "unit": m.unit,
                "estimated_quantity": estimated_qty,
                "estimated_cost": estimated_cost,
                "environmental_grade": _estimate_environmental_grade(m),
                "supplier": supplier_cache.get(m.id, "未指定"),
                "brand": m.brand,
                "match_score": score,
                "reason": "，".join(reasons),
            })

    # 按匹配分数降序排列所有推荐
    recommendations.sort(key=lambda x: x["match_score"], reverse=True)

    # 7. 计算预算利用率
    budget_utilization = round((total_material_cost / total_budget) * 100, 1) if total_budget > 0 else 0.0

    # 8. 生成替代建议
    alternative_suggestions: list[str] = []
    if budget_utilization > 90:
        alternative_suggestions.append(
            f"推荐物料总费用 {total_material_cost:.0f} 元接近预算 {total_budget:.0f} 元（{budget_utilization}%），"
            f"建议将预算等级从 {budget_level} 调整为标准，或优先选择低价替代品"
        )
    elif budget_utilization < 30 and budget_level == "premium":
        alternative_suggestions.append(
            f"当前预算利用率仅 {budget_utilization}%，建议考虑更高品质物料"
        )
    if budget_level == "economy":
        alternative_suggestions.append("您选择了经济型预算，推荐关注性价比高的物料")
    elif budget_level == "premium":
        alternative_suggestions.append("您选择了高端预算，推荐关注环保等级高、品牌知名的物料")

    # 品类覆盖建议
    if target_categories:
        covered = {r["category_code"] for r in recommendations}
        missing = set(target_categories) - covered
        if missing:
            alternative_suggestions.append(f"以下品类暂无推荐物料：{', '.join(sorted(missing))}，建议补充数据库")

    return {
        "project_id": project_id,
        "room_type": room_type,
        "style": style,
        "budget_level": budget_level,
        "total_budget": round(total_budget, 2),
        "recommendations": recommendations,
        "total_recommendations": len(recommendations),
        "categories_covered": len(set(r["category_code"] for r in recommendations)),
        "total_estimated_cost": round(total_material_cost, 2),
        "budget_utilization_percent": budget_utilization,
        "alternative_suggestions": alternative_suggestions,
    }

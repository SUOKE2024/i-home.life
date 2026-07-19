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

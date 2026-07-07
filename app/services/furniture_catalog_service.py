"""F26 家具品类库服务层 — 检索 + 房间推荐 + AR 摆放 + 相似推荐"""

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.furniture_catalog import FurnitureCatalogItem


# ── 标准 CRUD ──


async def create_item(db: AsyncSession, data: dict) -> FurnitureCatalogItem:
    item = FurnitureCatalogItem(**data)
    db.add(item)
    await db.commit()
    await db.refresh(item)
    return item


async def get_item(db: AsyncSession, item_id: str) -> FurnitureCatalogItem | None:
    result = await db.execute(select(FurnitureCatalogItem).where(FurnitureCatalogItem.id == item_id))
    return result.scalar_one_or_none()


async def update_item(db: AsyncSession, item_id: str, data: dict) -> FurnitureCatalogItem | None:
    item = await get_item(db, item_id)
    if not item:
        return None
    for k, v in data.items():
        if v is not None:
            setattr(item, k, v)
    await db.commit()
    await db.refresh(item)
    return item


async def delete_item(db: AsyncSession, item_id: str) -> bool:
    item = await get_item(db, item_id)
    if not item:
        return False
    await db.delete(item)
    await db.commit()
    return True


# ── 多维筛选 ──


async def search_furniture(db: AsyncSession, filters: dict) -> list[FurnitureCatalogItem]:
    """多维筛选 (category/subcategory/brand/style/price_range/material/color)"""
    stmt = select(FurnitureCatalogItem).where(FurnitureCatalogItem.status == "active")

    category = filters.get("category")
    if category:
        stmt = stmt.where(FurnitureCatalogItem.category == category)
    subcategory = filters.get("subcategory")
    if subcategory:
        stmt = stmt.where(FurnitureCatalogItem.subcategory == subcategory)
    brand = filters.get("brand")
    if brand:
        stmt = stmt.where(FurnitureCatalogItem.brand == brand)
    style = filters.get("style")
    if style:
        stmt = stmt.where(FurnitureCatalogItem.style == style)
    material = filters.get("material")
    if material:
        stmt = stmt.where(FurnitureCatalogItem.material == material)
    color = filters.get("color")
    if color:
        stmt = stmt.where(FurnitureCatalogItem.color == color)

    price_min = filters.get("price_min")
    price_max = filters.get("price_max")
    if price_min is not None:
        stmt = stmt.where(FurnitureCatalogItem.price >= price_min)
    if price_max is not None:
        stmt = stmt.where(FurnitureCatalogItem.price <= price_max)

    keyword = filters.get("keyword")
    if keyword:
        stmt = stmt.where(FurnitureCatalogItem.name.ilike(f"%{keyword}%"))

    # 排序: 评分高 + 销量高
    stmt = stmt.order_by(FurnitureCatalogItem.rating.desc(), FurnitureCatalogItem.sales_count.desc())

    result = await db.execute(stmt)
    return list(result.scalars().all())


# ── 房间推荐 ──

# 房间类型 → 推荐家具组合配置
ROOM_COMBO_PRESETS: dict[str, list[dict]] = {
    "living_room": [
        {"subcategory": "sofa", "quantity": 3, "label": "三人沙发", "default_price": 4980.0},
        {"subcategory": "sofa", "quantity": 2, "label": "双人沙发", "default_price": 3580.0},
        {"subcategory": "sofa", "quantity": 1, "label": "单人沙发", "default_price": 1980.0},
        {"subcategory": "coffee_table", "quantity": 1, "label": "茶几", "default_price": 1980.0},
        {"subcategory": "tv_cabinet", "quantity": 1, "label": "电视柜", "default_price": 2280.0},
    ],
    "bedroom": [
        {"subcategory": "bed", "quantity": 1, "label": "1.8m 床", "default_price": 4980.0},
        {"subcategory": "nightstand", "quantity": 2, "label": "床头柜", "default_price": 680.0},
        {"subcategory": "wardrobe", "quantity": 1, "label": "衣柜", "default_price": 4280.0},
    ],
    "dining_room": [
        {"subcategory": "dining_table", "quantity": 1, "label": "餐桌", "default_price": 2980.0},
        {"subcategory": "chair", "quantity": 6, "label": "餐椅", "default_price": 380.0},
    ],
    "study": [
        {"subcategory": "desk", "quantity": 1, "label": "书桌", "default_price": 2280.0},
        {"subcategory": "bookshelf", "quantity": 1, "label": "书柜", "default_price": 1880.0},
        {"subcategory": "chair", "quantity": 1, "label": "办公椅", "default_price": 980.0},
    ],
    "kitchen": [
        {"subcategory": "wardrobe", "quantity": 1, "label": "橱柜", "default_price": 5280.0},
    ],
    "bathroom": [
        {"subcategory": "wardrobe", "quantity": 1, "label": "浴室柜", "default_price": 1880.0},
    ],
    "entrance": [
        {"subcategory": "shoe_cabinet", "quantity": 1, "label": "鞋柜", "default_price": 1280.0},
    ],
}


async def recommend_for_room(
    db: AsyncSession,
    room_type: str,
    room_area: float,
    style: str,
    budget: float,
) -> dict:
    """按房间推荐家具组合

    客厅: 3+2+1 沙发组合 + 茶几 + 电视柜
    卧室: 1.8m 床 + 床头柜×2 + 衣柜
    """
    preset = ROOM_COMBO_PRESETS.get(room_type, [])
    combos: list[dict] = []
    total = 0.0

    for cfg in preset:
        # 按风格 + 子品类查询匹配的家具
        stmt = (
            select(FurnitureCatalogItem)
            .where(
                FurnitureCatalogItem.subcategory == cfg["subcategory"],
                FurnitureCatalogItem.style == style,
                FurnitureCatalogItem.status == "active",
            )
            .order_by(FurnitureCatalogItem.rating.desc())
            .limit(1)
        )
        result = await db.execute(stmt)
        matched = result.scalar_one_or_none()

        if matched:
            unit_price = float(matched.sale_price or matched.price)
            item_info = {
                "item_id": matched.id,
                "name": matched.name,
                "brand": matched.brand,
                "subcategory": matched.subcategory,
                "quantity": cfg["quantity"],
                "label": cfg["label"],
                "unit_price": unit_price,
                "subtotal": round(unit_price * cfg["quantity"], 2),
                "image_url": matched.image_url,
                "model_3d_url": matched.model_3d_url,
                "ar_preview_supported": matched.ar_preview_supported,
            }
        else:
            # 无匹配数据时使用默认估价
            unit_price = cfg["default_price"]
            item_info = {
                "item_id": None,
                "name": cfg["label"],
                "brand": None,
                "subcategory": cfg["subcategory"],
                "quantity": cfg["quantity"],
                "label": cfg["label"],
                "unit_price": unit_price,
                "subtotal": round(unit_price * cfg["quantity"], 2),
                "image_url": None,
                "model_3d_url": None,
                "ar_preview_supported": False,
            }
        combos.append(item_info)
        total += item_info["subtotal"]

    within = budget <= 0 or total <= budget
    return {
        "room_type": room_type,
        "room_area": room_area,
        "style": style,
        "budget": budget,
        "combos": combos,
        "total_estimate": round(total, 2),
        "within_budget": within,
    }


# ── AR 摆放预览 ──


def compute_ar_placement(item: FurnitureCatalogItem, room_dimensions: dict) -> dict:
    """AR 摆放预览计算 (1:1 比例,推荐位置坐标)

    room_dimensions: {"width": 宽 mm, "length": 长 mm, "height": 高 mm}
    """
    room_w = float(room_dimensions.get("width", 0))
    room_l = float(room_dimensions.get("length", 0))
    room_h = float(room_dimensions.get("height", 2800))

    item_w = float(item.width or 0)
    item_d = float(item.depth or 0)
    item_h = float(item.height or 0)

    # 推荐位置: 贴墙居中摆放,离地高度根据家具类型调整
    # 默认贴后墙居中
    pos_x = room_w / 2 - item_w / 2 if room_w > 0 else 0
    pos_y = room_l - item_d if room_l > 0 else 0  # 贴后墙
    pos_z = 0.0  # 默认落地

    # 高大家具(如衣柜/书柜)落地,悬挂类家具(如电视柜)适当离地
    if item.subcategory == "tv_cabinet":
        pos_z = 0.0  # 落地电视柜
    elif item.subcategory == "wardrobe":
        pos_z = 0.0
    elif item.subcategory == "nightstand":
        pos_z = 0.0

    # 适配警告
    warning = None
    if room_w > 0 and item_w > room_w:
        warning = f"家具宽度 {item_w}mm 超过房间宽度 {room_w}mm,无法摆放"
    elif room_l > 0 and item_d > room_l:
        warning = f"家具深度 {item_d}mm 超过房间长度 {room_l}mm,无法摆放"
    elif room_h > 0 and item_h > room_h:
        warning = f"家具高度 {item_h}mm 超过房间高度 {room_h}mm,无法摆放"

    return {
        "item_id": item.id,
        "item_name": item.name,
        "item_dimensions": {"width": item_w, "depth": item_d, "height": item_h},
        "scale": 1.0,  # 1:1 比例
        "recommended_position": {"x": round(pos_x, 1), "y": round(pos_y, 1), "z": round(pos_z, 1)},
        "room_dimensions": {"width": room_w, "length": room_l, "height": room_h},
        "fit_warning": warning,
    }


# ── 浏览量统计 ──


async def increment_views(db: AsyncSession, item_id: str) -> FurnitureCatalogItem | None:
    item = await get_item(db, item_id)
    if not item:
        return None
    item.view_count = int(item.view_count or 0) + 1
    await db.commit()
    await db.refresh(item)
    return item


# ── 相似家具推荐 ──


async def get_similar_items(db: AsyncSession, item_id: str, limit: int = 5) -> list[FurnitureCatalogItem]:
    """相似家具推荐 (同 category + 同 style)"""
    item = await get_item(db, item_id)
    if not item:
        return []
    stmt = (
        select(FurnitureCatalogItem)
        .where(
            FurnitureCatalogItem.id != item_id,
            FurnitureCatalogItem.category == item.category,
            FurnitureCatalogItem.style == item.style,
            FurnitureCatalogItem.status == "active",
        )
        .order_by(FurnitureCatalogItem.rating.desc())
        .limit(limit)
    )
    result = await db.execute(stmt)
    return list(result.scalars().all())

"""产品/服务 Service — 供应商产品的 CRUD 操作"""
import json

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.models.product import Product
from app.schemas.product import ProductCreate, ProductUpdate


async def create_product(
    db: AsyncSession, user_id: str, supplier_id: str, data: ProductCreate,
) -> Product:
    images_json = json.dumps(data.images, ensure_ascii=False) if data.images else None
    tags_json = json.dumps(data.tags, ensure_ascii=False) if data.tags else None
    specs_json = json.dumps(data.specs, ensure_ascii=False) if data.specs else None

    product = Product(
        user_id=user_id,
        supplier_id=supplier_id,
        name=data.name,
        category=data.category,
        description=data.description,
        price_min=data.price_min,
        price_max=data.price_max,
        unit=data.unit,
        images=images_json,
        cover_image=data.cover_image,
        tags=tags_json,
        specs=specs_json,
        stock_status=data.stock_status,
        status="draft",
        ai_generated=data.ai_assisted,
    )
    db.add(product)
    await db.commit()
    await db.refresh(product)
    return product


async def get_product(db: AsyncSession, product_id: str) -> Product | None:
    result = await db.execute(
        select(Product).where(Product.id == product_id)
    )
    return result.scalar_one_or_none()


async def list_products(
    db: AsyncSession,
    user_id: str | None = None,
    supplier_id: str | None = None,
    category: str | None = None,
    status: str | None = None,
    skip: int = 0,
    limit: int = 50,
) -> list[Product]:
    stmt = select(Product).order_by(Product.created_at.desc()).offset(skip).limit(limit)

    if user_id:
        stmt = stmt.where(Product.user_id == user_id)
    if supplier_id:
        stmt = stmt.where(Product.supplier_id == supplier_id)
    if category:
        stmt = stmt.where(Product.category == category)
    if status:
        stmt = stmt.where(Product.status == status)

    result = await db.execute(stmt)
    return list(result.scalars().all())


async def update_product(
    db: AsyncSession, product_id: str, data: ProductUpdate,
) -> Product | None:
    product = await get_product(db, product_id)
    if not product:
        return None

    update_data = data.model_dump(exclude_unset=True)

    # 序列化 JSON 字段
    for json_field in ("images", "tags", "specs"):
        if json_field in update_data and update_data[json_field] is not None:
            update_data[json_field] = json.dumps(
                update_data[json_field], ensure_ascii=False,
            )

    for key, value in update_data.items():
        setattr(product, key, value)

    await db.commit()
    await db.refresh(product)
    return product


async def publish_product(db: AsyncSession, product_id: str) -> Product | None:
    """发布产品（draft → published）"""
    product = await get_product(db, product_id)
    if not product:
        return None
    product.status = "published"
    await db.commit()
    await db.refresh(product)
    return product


async def delete_product(db: AsyncSession, product_id: str) -> bool:
    product = await get_product(db, product_id)
    if not product:
        return False
    await db.delete(product)
    await db.commit()
    return True

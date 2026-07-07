from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from sqlalchemy.orm import selectinload

from app.models.material import MaterialCategory, Material, BOMItem


async def get_categories(db: AsyncSession) -> list[MaterialCategory]:
    result = await db.execute(
        select(MaterialCategory).order_by(MaterialCategory.code)
    )
    return list(result.scalars().all())


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
    return category


async def get_materials(
    db: AsyncSession, category_id: str | None = None, skip: int = 0, limit: int = 50
) -> list[Material]:
    stmt = (
        select(Material)
        .where(Material.is_active == True)
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

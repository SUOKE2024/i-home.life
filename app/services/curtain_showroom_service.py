"""窗帘智能展厅服务层 — 单店铺固定展厅的目录查询"""

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.curtain_showroom import (
    CurtainInstallation,
    CurtainLightingPreset,
    CurtainProduct,
    CurtainSeries,
    CurtainShowroom,
    CurtainShowroomArea,
)


async def get_showroom(db: AsyncSession) -> CurtainShowroom | None:
    """获取（唯一的）窗帘展厅锚点。"""
    result = await db.execute(
        select(CurtainShowroom)
        .where(CurtainShowroom.is_active.is_(True))
        .order_by(CurtainShowroom.created_at.asc())
        .limit(1)
    )
    return result.scalar_one_or_none()


async def list_series(db: AsyncSession, showroom_id: str) -> list[CurtainSeries]:
    result = await db.execute(
        select(CurtainSeries)
        .where(CurtainSeries.showroom_id == showroom_id)
        .order_by(CurtainSeries.sort_order.asc(), CurtainSeries.created_at.asc())
    )
    return list(result.scalars().all())


async def list_products(
    db: AsyncSession,
    showroom_id: str,
    series_id: str | None = None,
    brand: str | None = None,
    fabric: str | None = None,
) -> list[CurtainProduct]:
    stmt = select(CurtainProduct).where(
        CurtainProduct.showroom_id == showroom_id,
        CurtainProduct.is_active.is_(True),
    )
    if series_id:
        stmt = stmt.where(CurtainProduct.series_id == series_id)
    if brand:
        stmt = stmt.where(CurtainProduct.brand == brand)
    if fabric:
        stmt = stmt.where(CurtainProduct.fabric == fabric)
    stmt = stmt.order_by(CurtainProduct.sort_order.asc(), CurtainProduct.name.asc())
    result = await db.execute(stmt)
    return list(result.scalars().all())


async def list_installations(db: AsyncSession) -> list[CurtainInstallation]:
    result = await db.execute(
        select(CurtainInstallation).order_by(CurtainInstallation.sort_order.asc())
    )
    return list(result.scalars().all())


async def list_lighting_presets(db: AsyncSession) -> list[CurtainLightingPreset]:
    result = await db.execute(
        select(CurtainLightingPreset).order_by(CurtainLightingPreset.sort_order.asc())
    )
    return list(result.scalars().all())


async def list_areas(db: AsyncSession, showroom_id: str) -> list[CurtainShowroomArea]:
    result = await db.execute(
        select(CurtainShowroomArea)
        .where(CurtainShowroomArea.showroom_id == showroom_id)
        .options(
            selectinload(CurtainShowroomArea.installation),
            selectinload(CurtainShowroomArea.default_product),
        )
        .order_by(CurtainShowroomArea.sort_order.asc(), CurtainShowroomArea.created_at.asc())
    )
    return list(result.scalars().all())

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from sqlalchemy.orm import selectinload

from app.models.procurement import Supplier, Quotation, ProcurementOrder, OrderLine

# 采购订单状态流转定义
ORDER_STATUS_FLOW: dict[str, set[str]] = {
    "draft": {"pending", "confirmed", "cancelled"},
    "pending": {"confirmed", "cancelled"},
    "confirmed": {"shipped", "cancelled"},
    "shipped": {"delivered", "cancelled"},
    "delivered": {"completed"},
    "completed": set(),
    "cancelled": set(),
}


def is_valid_status_transition(current: str, target: str) -> bool:
    """校验订单状态流转是否合法"""
    allowed = ORDER_STATUS_FLOW.get(current, set())
    return target in allowed


async def get_suppliers(db: AsyncSession, category: str | None = None) -> list[Supplier]:
    stmt = select(Supplier).where(Supplier.is_active.is_(True)).order_by(Supplier.rating.desc())
    if category:
        stmt = stmt.where(Supplier.category == category)
    result = await db.execute(stmt)
    return list(result.scalars().all())


async def create_supplier(db: AsyncSession, data: dict) -> Supplier:
    supplier = Supplier(**data)
    db.add(supplier)
    await db.commit()
    await db.refresh(supplier)
    return supplier


async def create_quotation(db: AsyncSession, data: dict) -> Quotation:
    total = data["quantity"] * data["unit_price"]
    quotation = Quotation(**data, total_price=total)
    db.add(quotation)
    await db.commit()
    await db.refresh(quotation)
    return quotation


async def get_quotations(db: AsyncSession, project_id: str) -> list[Quotation]:
    result = await db.execute(
        select(Quotation)
        .where(Quotation.project_id == project_id)
        .options(selectinload(Quotation.supplier), selectinload(Quotation.material))
        .order_by(Quotation.total_price.asc())
    )
    return list(result.scalars().all())


async def create_order(db: AsyncSession, data: dict) -> ProcurementOrder:
    lines_data = data.pop("lines", [])
    order = ProcurementOrder(**data)
    db.add(order)
    await db.flush()

    total = 0.0
    for line_data in lines_data:
        line_total = line_data["quantity"] * line_data["unit_price"]
        total += line_total
        ol = OrderLine(order_id=order.id, **line_data, total_price=line_total)
        db.add(ol)

    order.total_amount = total
    await db.commit()
    await db.refresh(order)
    return await get_order(db, order.id)


async def get_order(db: AsyncSession, order_id: str) -> ProcurementOrder | None:
    result = await db.execute(
        select(ProcurementOrder)
        .where(ProcurementOrder.id == order_id)
        .options(
            selectinload(ProcurementOrder.lines).selectinload(OrderLine.material),
            selectinload(ProcurementOrder.supplier),
        )
    )
    return result.scalar_one_or_none()


async def get_project_orders(db: AsyncSession, project_id: str) -> list[ProcurementOrder]:
    result = await db.execute(
        select(ProcurementOrder)
        .where(ProcurementOrder.project_id == project_id)
        .options(
            selectinload(ProcurementOrder.supplier),
            selectinload(ProcurementOrder.lines).selectinload(OrderLine.material),
        )
        .order_by(ProcurementOrder.created_at.desc())
    )
    return list(result.scalars().all())


async def update_order_status(db: AsyncSession, order_id: str, status: str) -> ProcurementOrder | None:
    result = await db.execute(select(ProcurementOrder).where(ProcurementOrder.id == order_id))
    order = result.scalar_one_or_none()
    if not order:
        return None
    if not is_valid_status_transition(order.status, status):
        raise ValueError(f"非法状态流转: {order.status} → {status}")
    order.status = status
    await db.commit()
    await db.refresh(order)
    return order


async def update_order(db: AsyncSession, order_id: str, data: dict) -> ProcurementOrder | None:
    result = await db.execute(select(ProcurementOrder).where(ProcurementOrder.id == order_id))
    order = result.scalar_one_or_none()
    if not order:
        return None
    for key, value in data.items():
        setattr(order, key, value)
    await db.commit()
    return await get_order(db, order_id)


async def delete_order(db: AsyncSession, order_id: str) -> bool:
    result = await db.execute(select(ProcurementOrder).where(ProcurementOrder.id == order_id))
    order = result.scalar_one_or_none()
    if not order:
        return False
    await db.delete(order)
    await db.commit()
    return True

"""变更管理服务 — F39 业主发起变更 → 设计评估 → 预算影响 → 业主确认"""

from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.change_order import ChangeOrder, ChangeOrderItem


async def get_change_orders(db: AsyncSession, project_id: str) -> list[ChangeOrder]:
    result = await db.execute(
        select(ChangeOrder)
        .where(ChangeOrder.project_id == project_id)
        .options(selectinload(ChangeOrder.items))
        .order_by(ChangeOrder.created_at.desc())
    )
    return list(result.scalars().all())


async def get_change_order(db: AsyncSession, change_id: str) -> ChangeOrder | None:
    result = await db.execute(
        select(ChangeOrder)
        .where(ChangeOrder.id == change_id)
        .options(selectinload(ChangeOrder.items))
    )
    return result.scalar_one_or_none()


async def create_change_order(db: AsyncSession, data: dict) -> ChangeOrder:
    items_data = data.pop("items", [])
    order = ChangeOrder(**data)
    db.add(order)
    await db.flush()

    for item_data in items_data:
        # 自动计算 amount
        if item_data.get("amount", 0) == 0:
            item_data["amount"] = item_data.get("quantity", 1) * item_data.get("unit_price", 0)
        item = ChangeOrderItem(change_order_id=order.id, **item_data)
        db.add(item)

    await db.commit()
    return await get_change_order(db, order.id)


async def review_change_order(db: AsyncSession, change_id: str, data: dict, reviewer: str) -> ChangeOrder | None:
    order = await get_change_order(db, change_id)
    if not order:
        return None
    order.feasibility = data.get("feasibility", "feasible")
    order.feasibility_note = data.get("feasibility_note")
    order.cost_impact = data.get("cost_impact", 0.0)
    order.schedule_impact_days = data.get("schedule_impact_days", 0)
    order.design_impact = data.get("design_impact")
    order.reviewed_by = reviewer
    order.reviewed_at = datetime.now(timezone.utc)
    order.status = "reviewing" if order.feasibility != "infeasible" else "rejected"
    await db.commit()
    return await get_change_order(db, change_id)


async def approve_change_order(db: AsyncSession, change_id: str, approver: str) -> ChangeOrder | None:
    order = await get_change_order(db, change_id)
    if not order:
        return None
    order.approved_by = approver
    order.approved_at = datetime.now(timezone.utc)
    order.status = "approved"
    await db.commit()
    return await get_change_order(db, change_id)


async def cancel_change_order(db: AsyncSession, change_id: str) -> ChangeOrder | None:
    order = await get_change_order(db, change_id)
    if not order:
        return None
    order.status = "cancelled"
    await db.commit()
    return await get_change_order(db, change_id)

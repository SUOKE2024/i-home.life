"""变更管理服务 — F39 业主发起变更 → 设计评估 → 预算影响 → 业主确认"""

from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.change_order import ChangeOrder, ChangeOrderItem


# ── 状态机定义 ──
# pending    → reviewing (评审) | cancelled (取消)
# reviewing  → approved (批准) | rejected (驳回)
# approved   → completed (完成) | cancelled (取消)
# rejected   → cancelled (取消)
# cancelled  → 终态，不可再变
# completed  → 终态，不可再变
VALID_TRANSITIONS: dict[str, set[str]] = {
    "pending": {"reviewing", "cancelled"},
    "reviewing": {"approved", "rejected"},
    "approved": {"completed", "cancelled"},
    "rejected": {"cancelled"},
    "cancelled": set(),
    "completed": set(),
}


class ChangeOrderStateError(Exception):
    """变更单状态机校验失败"""

    def __init__(self, current_status: str, action: str, allowed: set[str]):
        self.current_status = current_status
        self.action = action
        self.allowed = allowed
        super().__init__(
            f"变更单状态「{current_status}」不支持操作「{action}」，"
            f"允许的目标状态: {sorted(allowed) or '无（终态）'}"
        )


def _assert_transition(order: ChangeOrder, action: str, target: str) -> None:
    """校验状态机：当前状态是否允许转换到 target"""
    allowed = VALID_TRANSITIONS.get(order.status, set())
    if target not in allowed:
        raise ChangeOrderStateError(order.status, action, allowed)


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
    target = "reviewing" if data.get("feasibility", "feasible") != "infeasible" else "rejected"
    _assert_transition(order, "review", target)
    order.feasibility = data.get("feasibility", "feasible")
    order.feasibility_note = data.get("feasibility_note")
    order.cost_impact = data.get("cost_impact", 0.0)
    order.schedule_impact_days = data.get("schedule_impact_days", 0)
    order.design_impact = data.get("design_impact")
    order.reviewed_by = reviewer
    order.reviewed_at = datetime.now(timezone.utc)
    order.status = target
    await db.commit()
    return await get_change_order(db, change_id)


async def approve_change_order(db: AsyncSession, change_id: str, approver: str) -> ChangeOrder | None:
    order = await get_change_order(db, change_id)
    if not order:
        return None
    _assert_transition(order, "approve", "approved")
    order.approved_by = approver
    order.approved_at = datetime.now(timezone.utc)
    order.status = "approved"
    await db.commit()
    return await get_change_order(db, change_id)


async def cancel_change_order(db: AsyncSession, change_id: str) -> ChangeOrder | None:
    order = await get_change_order(db, change_id)
    if not order:
        return None
    _assert_transition(order, "cancel", "cancelled")
    order.status = "cancelled"
    await db.commit()
    return await get_change_order(db, change_id)


async def complete_change_order(db: AsyncSession, change_id: str) -> ChangeOrder | None:
    """完成变更：approved → completed"""
    order = await get_change_order(db, change_id)
    if not order:
        return None
    _assert_transition(order, "complete", "completed")
    order.status = "completed"
    await db.commit()
    return await get_change_order(db, change_id)

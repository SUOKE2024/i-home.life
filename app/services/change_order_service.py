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


async def review_change_order(
    db: AsyncSession, change_id: str, data: dict, reviewer: str,
    assessment_source: str = "manual",
) -> ChangeOrder | None:
    order = await get_change_order(db, change_id)
    if not order:
        return None
    if assessment_source == "unavailable":
        # F39 诚实降级：Agent 自动评估失败 → 结论置 pending，不推进状态机，不伪造结论
        order.feasibility = "pending"
        order.feasibility_note = data.get("feasibility_note") or "Agent 自动评估失败，等待人工评估"
        order.reviewed_by = reviewer
        order.reviewed_at = datetime.now(timezone.utc)
        await db.commit()
        return await get_change_order(db, change_id)
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

    # 全链路编排：变更审批通过 → 触发预算更新（受 lifecycle_orchestration_enabled flag 控制）
    from app.services.lifecycle_events import emit_change_order_approved
    await emit_change_order_approved(
        project_id=order.project_id,
        change_order_id=order.id,
        cost_change=float(order.cost_impact or 0.0),
        description=order.description or "变更项",
        unit="项",
    )

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


def _extract_rooms_from_order(order: ChangeOrder) -> list[dict]:
    """从变更明细的 before/after_data 提取房间布局数据（JSON），去重。"""
    import json

    rooms: list[dict] = []
    seen: set[tuple] = set()
    for item in order.items:
        for key in ("after_data", "before_data"):
            raw = getattr(item, key, None)
            if not raw:
                continue
            try:
                data = json.loads(raw)
            except (json.JSONDecodeError, TypeError):
                continue
            candidates = data if isinstance(data, list) else [data]
            for c in candidates:
                if not isinstance(c, dict) or not c.get("name"):
                    continue
                ident = (c.get("name"), c.get("type", ""))
                if ident in seen:
                    continue
                seen.add(ident)
                room = {
                    "name": c["name"],
                    "type": c.get("type", c.get("room_type", "room")),
                }
                if all(k in c for k in ("x", "y", "w", "h")):
                    room.update(x=c["x"], y=c["y"], w=c["w"], h=c["h"])
                if c.get("furniture"):
                    room["furniture"] = c["furniture"]
                rooms.append(room)
    return rooms


async def auto_assess_change_order(order: ChangeOrder) -> dict:
    """F39 变更自动评估：设计 Agent（可行性/设计影响）+ 预算 Agent（费用影响）。

    使用确定性规则引擎路径（designer.analyze_circulation / budget.generate_budget_plan），
    不调用 LLM，避免复杂异步。调用失败时抛出异常，由 API 层降级为 unavailable。
    """
    from app.agents.designer import DesignerAgent
    from app.agents.budget import BudgetAgent

    designer = DesignerAgent()
    budget = BudgetAgent()
    try:
        rooms = _extract_rooms_from_order(order)

        if rooms:
            circulation = designer.analyze_circulation(rooms)
            score = circulation.get("overall_score", 0)
            rating_text = circulation.get("rating_text", "")
            issues = circulation.get("issues", [])
            critical_count = circulation.get("critical_count", 0)
            feasibility = "partial" if critical_count else "feasible"
            parts = [f"动线综合评分 {score}（{rating_text}）"]
            if issues:
                parts.append("；".join(i["detail"] for i in issues[:5]))
            design_impact = "设计Agent自动评估：" + "；".join(parts)
        else:
            # 无布局数据不伪造动线结论，仅诚实标注数据不足
            feasibility = "feasible"
            design_impact = "设计Agent自动评估：变更单未含房间布局数据，未做动线分析"

        # 费用影响：优先按明细汇总（精确），无明细时用规则引擎估算（诚实标注）
        item_amount = round(sum(i.amount or 0 for i in order.items), 2)
        if item_amount > 0:
            cost_impact = item_amount
            estimated = False
        else:
            plan = budget.generate_budget_plan(order.description or "126㎡ 舒适型装修")
            cost_impact = round(plan.get("total_estimated", 0.0), 2)
            estimated = True

        return {
            "feasibility": feasibility,
            "feasibility_note": (
                f"自动评估（规则引擎，未调用 LLM）：{'房间布局可用' if rooms else '无房间布局数据'}，"
                f"费用{'按变更明细汇总' if not estimated else '为规则估算值'}"
            ),
            "cost_impact": cost_impact,
            "schedule_impact_days": 0,
            "design_impact": design_impact,
            "estimated": estimated,
        }
    finally:
        await designer.close()
        await budget.close()

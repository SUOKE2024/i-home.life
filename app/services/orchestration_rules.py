"""
Orchestration rules - business logic that connects modules via events.
Register all cross-module workflows here.

v1.8.1 修复（lifecycle chain）：
  - 原规则引用不存在的 BudgetService/ProcurementService/ConstructionService 类（ImportError），
    现全部改为函数式 API（get_budget / create_budget / generate_from_bom / update_task_status /
    get_task_chain）。
  - INSPECTION_PASSED 的 `pass` 占位补全为后继任务链推进。
  - 事件由 app.services.lifecycle_events 在 5 处业务点发射（受 lifecycle_orchestration_enabled flag 门控）。
"""

from app.services.event_bus import Event, EventType, get_event_bus
import logging

logger = logging.getLogger(__name__)


def register_all_rules():  # noqa: C901
    """Register all orchestration rules. Call once at app startup."""
    bus = get_event_bus()

    @bus.on(EventType.BOM_GENERATED)
    async def auto_generate_procurement(event: Event):
        """When BOM is generated, auto-create procurement order suggestions."""
        try:
            from app.services.procurement_service import generate_from_bom
            from app.database import async_session

            async with async_session() as db:
                result = await generate_from_bom(db, event.project_id)
                order_count = len(result.get("orders", [])) if isinstance(result, dict) else 0
                logger.info(
                    f"Auto-generated procurement from BOM for project "
                    f"{event.project_id}: {order_count} orders"
                )
        except Exception as e:
            logger.warning(f"Failed to auto-generate procurement for {event.project_id}: {e}")

    @bus.on(EventType.MATERIAL_DELIVERED)
    async def update_construction_on_delivery(event: Event):
        """When materials are delivered, update linked construction tasks."""
        try:
            task_id = event.data.get("task_id")
            if not task_id:
                return
            from sqlalchemy import select
            from app.models.construction import ConstructionTask
            from app.services.construction_service import update_task_status
            from app.database import async_session

            async with async_session() as db:
                # 查任务，若 pending 则推进为 ready
                result = await db.execute(
                    select(ConstructionTask).where(ConstructionTask.id == task_id)
                )
                task = result.scalar_one_or_none()
                if task and task.status == "pending":
                    await update_task_status(db, task_id, "ready")
                    logger.info(f"Task {task_id} set to ready after material delivery")
        except Exception as e:
            logger.warning(f"Failed to update construction on delivery: {e}")

    @bus.on(EventType.INSPECTION_PASSED)
    async def advance_construction_after_inspection(event: Event):
        """When inspection passes, advance the construction task and check successor chain."""
        try:
            task_id = event.data.get("task_id")
            if not task_id:
                return
            from app.services.construction_service import update_task_status, get_task_chain
            from app.database import async_session

            async with async_session() as db:
                # 标记当前任务完成
                await update_task_status(db, task_id, "completed")
                # 修复断裂 5：原 `pass` 占位 → 实现后继任务链推进
                # 查询当前任务的后继任务，若其所有前置任务均 completed，则推进为 ready
                chain = await get_task_chain(db, task_id)
                for successor in chain.get("successors", []):
                    successor_id = successor.get("id")
                    if not successor_id:
                        continue
                    # 查后继任务的所有前置任务是否均已完成
                    successor_chain = await get_task_chain(db, successor_id)
                    predecessors = successor_chain.get("predecessors", [])
                    if not predecessors:
                        continue
                    if all(p.get("status") == "completed" for p in predecessors):
                        await update_task_status(db, successor_id, "ready")
                        logger.info(
                            f"Successor task {successor_id} set to ready after "
                            f"all predecessors completed (trigger: inspection passed for {task_id})"
                        )
        except Exception as e:
            logger.warning(f"Failed to advance construction: {e}")

    @bus.on(EventType.CHANGE_ORDER_APPROVED)
    async def update_budget_on_change_order(event: Event):
        """When change order is approved, update the budget."""
        try:
            from app.services.budget_service import get_budget
            from app.models.budget import BudgetLine
            from app.database import async_session

            change_data = event.data
            async with async_session() as db:
                budget = await get_budget(db, event.project_id)
                if budget:
                    # 直接追加一条变更预算行（原 BudgetService.add_line 不存在，改用 ORM）
                    db.add(BudgetLine(
                        budget_id=budget.id,
                        category="change_order",
                        name=change_data.get("description", "变更项"),
                        estimated_amount=float(change_data.get("cost_change", 0)),
                        quantity=1.0,
                        unit=change_data.get("unit", "项"),
                    ))
                    await db.commit()
                    logger.info(
                        f"Budget updated for change order on project {event.project_id}"
                    )
        except Exception as e:
            logger.warning(f"Failed to update budget on change order: {e}")

    @bus.on(EventType.PROJECT_CREATED)
    async def auto_create_budget_on_project(event: Event):
        """When a project is created, create a default budget."""
        try:
            from app.services.budget_service import get_budget, create_budget
            from app.database import async_session

            async with async_session() as db:
                existing = await get_budget(db, event.project_id)
                if not existing:
                    await create_budget(db, {
                        "project_id": event.project_id,
                        "name": f"预算-{event.project_id[:8]}",
                        "lines": [],
                    })
                    logger.info(f"Auto-created budget for project {event.project_id}")
        except Exception as e:
            logger.warning(f"Failed to auto-create budget: {e}")

    logger.info(f"Orchestration rules registered. Total handlers: {bus.handler_count()}")

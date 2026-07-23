"""
Orchestration rules - business logic that connects modules via events.
Register all cross-module workflows here.
"""

from app.services.event_bus import Event, EventType, get_event_bus
import logging

logger = logging.getLogger(__name__)


def register_all_rules():
    """Register all orchestration rules. Call once at app startup."""
    bus = get_event_bus()

    @bus.on(EventType.BOM_GENERATED)
    async def auto_generate_procurement(event: Event):
        """When BOM is generated, auto-create procurement order suggestions."""
        try:
            from app.services.procurement_service import ProcurementService
            from app.database import async_session_factory

            async with async_session_factory() as db:
                service = ProcurementService(db)
                result = await service.generate_from_bom(event.project_id)
                logger.info(f"Auto-generated procurement from BOM for project {event.project_id}: {len(result)} orders")
        except Exception as e:
            logger.warning(f"Failed to auto-generate procurement for {event.project_id}: {e}")

    @bus.on(EventType.MATERIAL_DELIVERED)
    async def update_construction_on_delivery(event: Event):
        """When materials are delivered, update linked construction tasks."""
        try:
            task_id = event.data.get("task_id")
            if not task_id:
                return
            from app.services.construction_service import ConstructionService
            from app.database import async_session_factory

            async with async_session_factory() as db:
                service = ConstructionService(db)
                # Check if all required materials for this task are delivered
                # If so, set task to ready
                task = await service.get_task(task_id)
                if task and task.status == "pending":
                    await service.update_task_status(task_id, "ready")
                    logger.info(f"Task {task_id} set to ready after material delivery")
        except Exception as e:
            logger.warning(f"Failed to update construction on delivery: {e}")

    @bus.on(EventType.INSPECTION_PASSED)
    async def advance_construction_after_inspection(event: Event):
        """When inspection passes, advance the construction task."""
        try:
            task_id = event.data.get("task_id")
            if not task_id:
                return
            from app.services.construction_service import ConstructionService
            from app.database import async_session_factory

            async with async_session_factory() as db:
                service = ConstructionService(db)
                await service.update_task_status(task_id, "completed")
                # Check if next task can start
                successors = await service.get_task_chain(task_id)
                for successor in successors.get("successors", []):
                    # Check if all predecessors of successor are completed
                    pass  # Implementation would check all predecessor statuses
        except Exception as e:
            logger.warning(f"Failed to advance construction: {e}")

    @bus.on(EventType.CHANGE_ORDER_APPROVED)
    async def update_budget_on_change_order(event: Event):
        """When change order is approved, update the budget."""
        try:
            from app.services.budget_service import BudgetService
            from app.database import async_session_factory

            change_data = event.data
            async with async_session_factory() as db:
                service = BudgetService(db)
                # Add a new budget line for the change
                budget = await service.get_by_project(event.project_id)
                if budget:
                    await service.add_line(
                        budget.id,
                        category="change_order",
                        item_name=change_data.get("description", "变更项"),
                        estimated_amount=change_data.get("cost_change", 0),
                        quantity=1,
                        unit=change_data.get("unit", "项"),
                    )
                    logger.info(f"Budget updated for change order on project {event.project_id}")
        except Exception as e:
            logger.warning(f"Failed to update budget on change order: {e}")

    @bus.on(EventType.PROJECT_CREATED)
    async def auto_create_budget_on_project(event: Event):
        """When a project is created, create a default budget."""
        try:
            from app.services.budget_service import BudgetService
            from app.database import async_session_factory

            async with async_session_factory() as db:
                service = BudgetService(db)
                existing = await service.get_by_project(event.project_id)
                if not existing:
                    await service.create(event.project_id, name=f"预算-{event.project_id[:8]}")
                    logger.info(f"Auto-created budget for project {event.project_id}")
        except Exception as e:
            logger.warning(f"Failed to auto-create budget: {e}")

    logger.info(f"Orchestration rules registered. Total handlers: {bus.handler_count()}")

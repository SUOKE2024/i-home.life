"""
Event Bus for cross-module orchestration.
Enables loose coupling between services via pub/sub pattern.

Architecture:
- Each event has a type and payload
- Handlers subscribe to specific event types
- Events are dispatched asynchronously
- Supports sync and async handlers
"""

from enum import Enum
from dataclasses import dataclass, field
from typing import Any, Callable, Coroutine, Dict, List
import asyncio
import logging

logger = logging.getLogger(__name__)


class EventType(str, Enum):
    """Core business events that trigger cross-module workflows."""
    PROJECT_CREATED = "project.created"
    PROJECT_UPDATED = "project.updated"
    BOM_GENERATED = "bom.generated"           # BOM 生成后 → 自动创建采购建议
    BOM_UPDATED = "bom.updated"
    MATERIAL_DELIVERED = "material.delivered" # 材料到货 → 触发施工任务启动
    INSPECTION_PASSED = "inspection.passed"   # 验收通过 → 推进施工状态+结算
    INSPECTION_FAILED = "inspection.failed"
    CHANGE_ORDER_APPROVED = "change_order.approved" # 变更审批 → 更新预算+结算
    TASK_COMPLETED = "task.completed"
    TASK_STARTED = "task.started"
    BUDGET_APPROVED = "budget.approved"
    SETTLEMENT_CREATED = "settlement.created"


@dataclass
class Event:
    type: EventType
    project_id: str
    data: Dict[str, Any] = field(default_factory=dict)
    triggered_by: str | None = None  # user_id who triggered


# Handler type: async callable that receives Event and returns None
EventHandler = Callable[[Event], Coroutine[Any, Any, None]]


class EventBus:
    """
    Singleton event bus for the application.

    Usage:
        bus = get_event_bus()

        @bus.on(EventType.BOM_GENERATED)
        async def handle_bom_generated(event: Event):
            # Auto-create procurement suggestions
            ...

        await bus.emit(Event(type=EventType.BOM_GENERATED, project_id="123", data={"bom_id": "456"}))
    """

    _instance: "EventBus | None" = None

    def __init__(self):
        self._handlers: Dict[EventType, List[EventHandler]] = {
            event_type: [] for event_type in EventType
        }
        self._global_handlers: List[EventHandler] = []

    @classmethod
    def get_instance(cls) -> "EventBus":
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    def on(self, event_type: EventType | None = None):
        """Decorator to register an event handler.

        Usage:
            @bus.on(EventType.BOM_GENERATED)
            async def handler(event): ...

            @bus.on()  # listens to all events
            async def global_handler(event): ...
        """
        def decorator(handler: EventHandler):
            if event_type is None:
                self._global_handlers.append(handler)
            else:
                self._handlers[event_type].append(handler)
            logger.debug(f"Registered handler {handler.__name__} for {event_type or 'ALL'}")
            return handler
        return decorator

    async def emit(self, event: Event) -> None:
        """Dispatch an event to all registered handlers.

        Handlers are called concurrently. Errors in individual handlers are logged
        but do not prevent other handlers from executing.
        """
        handlers = list(self._handlers.get(event.type, [])) + list(self._global_handlers)

        if not handlers:
            logger.debug(f"No handlers for event {event.type}")
            return

        logger.info(f"Dispatching {event.type} for project {event.project_id} ({len(handlers)} handlers)")

        async def safe_invoke(handler: EventHandler):
            try:
                await handler(event)
            except Exception as e:
                logger.error(f"Handler {handler.__name__} failed for {event.type}: {e}", exc_info=True)

        await asyncio.gather(*[safe_invoke(h) for h in handlers])

    def handler_count(self, event_type: EventType | None = None) -> int:
        """Get count of registered handlers for debugging."""
        if event_type:
            return len(self._handlers.get(event_type, [])) + len(self._global_handlers)
        total = len(self._global_handlers)
        for handlers in self._handlers.values():
            total += len(handlers)
        return total


# Singleton accessor
def get_event_bus() -> EventBus:
    return EventBus.get_instance()

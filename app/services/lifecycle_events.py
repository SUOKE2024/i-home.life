"""项目全链路事件发射辅助层（lifecycle_orchestration_enabled flag 门控）

封装 5 个生命周期事件的发射逻辑，统一受 ``lifecycle_orchestration_enabled`` 控制：
关闭时所有 emit_* 函数 no-op 直接返回，零回归；启用时通过 event_bus 派发事件，
触发 ``orchestration_rules.register_all_rules`` 注册的跨模块编排规则。

事件与编排规则对应关系见 docs/superpowers/specs/2026-08-04-lifecycle-chain-fix-design.md。
"""

import logging
from typing import Any

from app.config import get_settings
from app.services.event_bus import Event, EventType, get_event_bus

logger = logging.getLogger(__name__)


def _enabled() -> bool:
    """读取 flag，避免在模块导入时强依赖 settings 已初始化"""
    try:
        return get_settings().lifecycle_orchestration_enabled
    except Exception:
        return False


async def _emit(event_type: EventType, project_id: str, data: dict[str, Any] | None = None,
                triggered_by: str | None = None) -> None:
    """统一发射入口：flag 关闭时 no-op，开启时派发并吞掉 handler 异常"""
    if not _enabled() or not project_id:
        return
    try:
        bus = get_event_bus()
        await bus.emit(Event(
            type=event_type,
            project_id=project_id,
            data=data or {},
            triggered_by=triggered_by,
        ))
    except Exception:
        logger.warning(
            "lifecycle_emit_failed: type=%s project=%s", event_type, project_id,
            exc_info=True,
        )


async def emit_project_created(project_id: str, owner_id: str | None = None) -> None:
    """项目创建 → 触发自动建预算（auto_create_budget_on_project）"""
    await _emit(EventType.PROJECT_CREATED, project_id, {"owner_id": owner_id} if owner_id else {})


async def emit_bom_generated(project_id: str, bom_version: int | None = None) -> None:
    """BOM 版本快照定稿 → 触发自动采购建议（auto_generate_procurement）"""
    await _emit(EventType.BOM_GENERATED, project_id, {"bom_version": bom_version} if bom_version else {})


async def emit_material_delivered(project_id: str, order_id: str, task_id: str | None = None) -> None:
    """材料到货 → 触发施工任务就绪推进（update_construction_on_delivery）"""
    await _emit(EventType.MATERIAL_DELIVERED, project_id, {
        "order_id": order_id,
        "task_id": task_id,
    })


async def emit_inspection_passed(project_id: str, task_id: str, inspection_id: str | None = None) -> None:
    """验收通过 → 触发后继任务链推进（advance_construction_after_inspection）"""
    await _emit(EventType.INSPECTION_PASSED, project_id, {
        "task_id": task_id,
        "inspection_id": inspection_id,
    })


async def emit_change_order_approved(project_id: str, change_order_id: str,
                                     cost_change: float = 0.0, description: str = "",
                                     unit: str = "项") -> None:
    """变更审批通过 → 触发预算更新（update_budget_on_change_order）"""
    await _emit(EventType.CHANGE_ORDER_APPROVED, project_id, {
        "change_order_id": change_order_id,
        "cost_change": cost_change,
        "description": description,
        "unit": unit,
    })

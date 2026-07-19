from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.models.construction import ConstructionTask, ConstructionLog, Inspection


# ── 施工任务状态机 ──
# pending      → in_progress (开始) | cancelled (取消)
# in_progress  → paused (暂停) | completed (完成) | cancelled (取消)
# paused       → in_progress (恢复) | cancelled (取消)
# completed    → 终态，不可再变
# cancelled    → 终态，不可再变
TASK_TRANSITIONS: dict[str, set[str]] = {
    "pending": {"in_progress", "cancelled"},
    "in_progress": {"paused", "completed", "cancelled"},
    "paused": {"in_progress", "cancelled"},
    "completed": set(),
    "cancelled": set(),
}

# ── 验收状态机 ──
# pending  → passed (通过) | failed (不通过)
# failed   → rework (整改) | passed (复验通过)
# rework   → pending (重新提交) | passed (通过)
# passed   → 终态，不可再变
INSPECTION_TRANSITIONS: dict[str, set[str]] = {
    "pending": {"passed", "failed"},
    "failed": {"rework", "passed"},
    "rework": {"pending", "passed"},
    "passed": set(),
}


class ConstructionStateError(Exception):
    """施工状态机校验失败"""

    def __init__(self, current_status: str, action: str, allowed: set[str]):
        self.current_status = current_status
        self.action = action
        self.allowed = allowed
        super().__init__(
            f"施工状态「{current_status}」不支持操作「{action}」，"
            f"允许的目标状态: {sorted(allowed) or '无（终态）'}"
        )


class InspectionStateError(Exception):
    """验收状态机校验失败"""

    def __init__(self, current_status: str, action: str, allowed: set[str]):
        self.current_status = current_status
        self.action = action
        self.allowed = allowed
        super().__init__(
            f"验收状态「{current_status}」不支持操作「{action}」，"
            f"允许的目标状态: {sorted(allowed) or '无（终态）'}"
        )


def _assert_task_transition(task: ConstructionTask, action: str, target: str) -> None:
    """校验施工任务状态机"""
    allowed = TASK_TRANSITIONS.get(task.status, set())
    if target not in allowed:
        raise ConstructionStateError(task.status, action, allowed)


def _assert_inspection_transition(inspection: Inspection, action: str, target: str) -> None:
    """校验验收状态机"""
    allowed = INSPECTION_TRANSITIONS.get(inspection.status, set())
    if target not in allowed:
        raise InspectionStateError(inspection.status, action, allowed)


async def get_tasks(db: AsyncSession, project_id: str) -> list[ConstructionTask]:
    result = await db.execute(
        select(ConstructionTask)
        .where(ConstructionTask.project_id == project_id)
        .order_by(ConstructionTask.phase, ConstructionTask.priority)
    )
    return list(result.scalars().all())


async def create_task(db: AsyncSession, data: dict) -> ConstructionTask:
    task = ConstructionTask(**data)
    db.add(task)
    await db.commit()
    await db.refresh(task)
    return task


async def update_task_status(db: AsyncSession, task_id: str, status: str) -> ConstructionTask | None:
    result = await db.execute(select(ConstructionTask).where(ConstructionTask.id == task_id))
    task = result.scalar_one_or_none()
    if not task:
        return None
    _assert_task_transition(task, "update_status", status)
    task.status = status
    await db.commit()
    await db.refresh(task)
    return task


async def add_log(db: AsyncSession, data: dict) -> ConstructionLog:
    log = ConstructionLog(**data)
    db.add(log)
    await db.commit()
    await db.refresh(log)
    return log


async def get_logs(db: AsyncSession, task_id: str) -> list[ConstructionLog]:
    result = await db.execute(
        select(ConstructionLog)
        .where(ConstructionLog.task_id == task_id)
        .order_by(ConstructionLog.created_at.desc())
    )
    return list(result.scalars().all())


async def create_inspection(db: AsyncSession, data: dict) -> Inspection:
    inspection = Inspection(**data)
    db.add(inspection)
    await db.commit()
    await db.refresh(inspection)
    return inspection


async def get_inspections(db: AsyncSession, task_id: str) -> list[Inspection]:
    result = await db.execute(
        select(Inspection)
        .where(Inspection.task_id == task_id)
        .order_by(Inspection.created_at.desc())
    )
    return list(result.scalars().all())


# ── 验收状态变更 ──

async def update_inspection_status(
    db: AsyncSession, inspection_id: str, status: str, action: str = "update_status",
) -> Inspection | None:
    """更新验收状态（带状态机校验）"""
    result = await db.execute(select(Inspection).where(Inspection.id == inspection_id))
    inspection = result.scalar_one_or_none()
    if not inspection:
        return None
    _assert_inspection_transition(inspection, action, status)
    inspection.status = status
    await db.commit()
    await db.refresh(inspection)
    return inspection

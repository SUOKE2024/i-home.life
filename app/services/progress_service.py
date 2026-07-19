"""F37 进度管理服务层 — 预警持久化 + 里程碑跟踪"""

from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.progress_alert import ProgressAlert, MilestoneTracker


# ── 预警状态机 ──
# active    → resolved (已解决) | ignored (已忽略)
# resolved  → 终态，不可再变
# ignored   → 终态，不可再变
ALERT_TRANSITIONS: dict[str, set[str]] = {
    "active": {"resolved", "ignored"},
    "resolved": set(),
    "ignored": set(),
}

# ── 里程碑状态机 ──
# pending      → in_progress (开始) | delayed (延期)
# in_progress  → completed (完成) | delayed (延期)
# delayed      → in_progress (恢复) | completed (完成)
# completed    → 终态，不可再变
MILESTONE_TRANSITIONS: dict[str, set[str]] = {
    "pending": {"in_progress", "delayed"},
    "in_progress": {"completed", "delayed"},
    "delayed": {"in_progress", "completed"},
    "completed": set(),
}


class ProgressAlertStateError(Exception):
    """预警状态机校验失败"""

    def __init__(self, current_status: str, action: str, allowed: set[str]):
        self.current_status = current_status
        self.action = action
        self.allowed = allowed
        super().__init__(
            f"预警状态「{current_status}」不支持操作「{action}」，"
            f"允许的目标状态: {sorted(allowed) or '无（终态）'}"
        )


class MilestoneStateError(Exception):
    """里程碑状态机校验失败"""

    def __init__(self, current_status: str, action: str, allowed: set[str]):
        self.current_status = current_status
        self.action = action
        self.allowed = allowed
        super().__init__(
            f"里程碑状态「{current_status}」不支持操作「{action}」，"
            f"允许的目标状态: {sorted(allowed) or '无（终态）'}"
        )


def _assert_alert_transition(alert: ProgressAlert, action: str, target: str) -> None:
    """校验预警状态机"""
    allowed = ALERT_TRANSITIONS.get(alert.status, set())
    if target not in allowed:
        raise ProgressAlertStateError(alert.status, action, allowed)


def _assert_milestone_transition(milestone: MilestoneTracker, action: str, target: str) -> None:
    """校验里程碑状态机"""
    allowed = MILESTONE_TRANSITIONS.get(milestone.status, set())
    if target not in allowed:
        raise MilestoneStateError(milestone.status, action, allowed)


# ── 进度预警 CRUD ──

async def create_alert(db: AsyncSession, data: dict) -> ProgressAlert:
    alert = ProgressAlert(**data)
    db.add(alert)
    await db.commit()
    await db.refresh(alert)
    return alert


async def get_alert(db: AsyncSession, alert_id: str) -> ProgressAlert | None:
    result = await db.execute(select(ProgressAlert).where(ProgressAlert.id == alert_id))
    return result.scalar_one_or_none()


async def list_alerts(
    db: AsyncSession,
    project_id: str,
    status_filter: str | None = None,
    severity: str | None = None,
) -> list[ProgressAlert]:
    stmt = (
        select(ProgressAlert)
        .where(ProgressAlert.project_id == project_id)
        .order_by(ProgressAlert.created_at.desc())
    )
    if status_filter:
        stmt = stmt.where(ProgressAlert.status == status_filter)
    if severity:
        stmt = stmt.where(ProgressAlert.severity == severity)
    result = await db.execute(stmt)
    return list(result.scalars().all())


async def resolve_alert(
    db: AsyncSession,
    alert_id: str,
    resolver: str,
    note: str | None = None,
) -> ProgressAlert | None:
    result = await db.execute(select(ProgressAlert).where(ProgressAlert.id == alert_id))
    alert = result.scalar_one_or_none()
    if not alert:
        return None
    _assert_alert_transition(alert, "resolve", "resolved")
    alert.status = "resolved"
    alert.resolved_at = datetime.now(timezone.utc)
    alert.resolved_by = resolver
    alert.resolution_note = note
    await db.commit()
    await db.refresh(alert)
    return alert


async def ignore_alert(db: AsyncSession, alert_id: str, note: str | None = None) -> ProgressAlert | None:
    result = await db.execute(select(ProgressAlert).where(ProgressAlert.id == alert_id))
    alert = result.scalar_one_or_none()
    if not alert:
        return None
    _assert_alert_transition(alert, "ignore", "ignored")
    alert.status = "ignored"
    alert.resolved_at = datetime.now(timezone.utc)
    alert.resolution_note = note
    await db.commit()
    await db.refresh(alert)
    return alert


# ── 里程碑跟踪 ──

async def upsert_milestone(db: AsyncSession, data: dict) -> MilestoneTracker:
    """创建或更新里程碑跟踪记录（按 project_id + milestone_code 唯一）"""
    project_id = data.get("project_id")
    milestone_code = data.get("milestone_code")
    existing = await db.execute(
        select(MilestoneTracker).where(
            MilestoneTracker.project_id == project_id,
            MilestoneTracker.milestone_code == milestone_code,
        )
    )
    record = existing.scalar_one_or_none()
    if record:
        for key, value in data.items():
            if hasattr(record, key) and value is not None:
                setattr(record, key, value)
    else:
        record = MilestoneTracker(**data)
        db.add(record)
    await db.commit()
    await db.refresh(record)
    return record


async def list_milestones(db: AsyncSession, project_id: str) -> list[MilestoneTracker]:
    result = await db.execute(
        select(MilestoneTracker)
        .where(MilestoneTracker.project_id == project_id)
        .order_by(MilestoneTracker.planned_percent)
    )
    return list(result.scalars().all())


async def complete_milestone(
    db: AsyncSession,
    milestone_id: str,
    actual_date: datetime | None = None,
    actual_percent: float | None = None,
    note: str | None = None,
) -> MilestoneTracker | None:
    result = await db.execute(select(MilestoneTracker).where(MilestoneTracker.id == milestone_id))
    record = result.scalar_one_or_none()
    if not record:
        return None
    _assert_milestone_transition(record, "complete", "completed")
    record.status = "completed"
    record.actual_date = actual_date or datetime.now(timezone.utc)
    record.actual_percent = actual_percent if actual_percent is not None else record.planned_percent
    if note:
        record.note = note
    await db.commit()
    await db.refresh(record)
    return record


# ── 里程碑状态变更 ──

async def update_milestone_status(
    db: AsyncSession,
    milestone_id: str,
    status: str,
    action: str = "update_status",
) -> MilestoneTracker | None:
    """更新里程碑状态（带状态机校验）"""
    result = await db.execute(select(MilestoneTracker).where(MilestoneTracker.id == milestone_id))
    record = result.scalar_one_or_none()
    if not record:
        return None
    _assert_milestone_transition(record, action, status)
    record.status = status
    await db.commit()
    await db.refresh(record)
    return record

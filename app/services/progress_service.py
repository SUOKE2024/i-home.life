"""F37 进度管理服务层 — 预警持久化 + 里程碑跟踪"""

from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.progress_alert import ProgressAlert, MilestoneTracker


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
    record.status = "completed"
    record.actual_date = actual_date or datetime.now(timezone.utc)
    record.actual_percent = actual_percent if actual_percent is not None else record.planned_percent
    if note:
        record.note = note
    await db.commit()
    await db.refresh(record)
    return record

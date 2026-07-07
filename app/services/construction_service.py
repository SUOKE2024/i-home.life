from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from sqlalchemy.orm import selectinload

from app.models.construction import ConstructionTask, ConstructionLog, Inspection


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

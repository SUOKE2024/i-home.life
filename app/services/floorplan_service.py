from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.models.floorplan import FloorPlan


async def list_floor_plans(db: AsyncSession, project_id: str) -> list[FloorPlan]:
    result = await db.execute(
        select(FloorPlan)
        .where(FloorPlan.project_id == project_id, FloorPlan.is_active == True)
        .order_by(FloorPlan.updated_at.desc())
    )
    return list(result.scalars().all())


async def get_floor_plan(db: AsyncSession, plan_id: str) -> FloorPlan | None:
    result = await db.execute(select(FloorPlan).where(FloorPlan.id == plan_id))
    return result.scalar_one_or_none()


async def create_floor_plan(db: AsyncSession, data: dict) -> FloorPlan:
    plan = FloorPlan(**data)
    db.add(plan)
    await db.commit()
    await db.refresh(plan)
    return plan


async def update_floor_plan(db: AsyncSession, plan_id: str, data: dict) -> FloorPlan | None:
    result = await db.execute(select(FloorPlan).where(FloorPlan.id == plan_id))
    plan = result.scalar_one_or_none()
    if not plan:
        return None
    for key, value in data.items():
        if hasattr(plan, key):
            setattr(plan, key, value)
    await db.commit()
    await db.refresh(plan)
    return plan


async def delete_floor_plan(db: AsyncSession, plan_id: str) -> bool:
    result = await db.execute(select(FloorPlan).where(FloorPlan.id == plan_id))
    plan = result.scalar_one_or_none()
    if not plan:
        return False
    plan.is_active = False
    await db.commit()
    return True

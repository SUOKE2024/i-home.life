from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from sqlalchemy.orm import selectinload

from app.models.project import Project, Floor, Room
from app.schemas.project import ProjectCreate, ProjectUpdate


async def get_project(db: AsyncSession, project_id: str) -> Project | None:
    result = await db.execute(
        select(Project)
        .where(Project.id == project_id)
        .options(
            selectinload(Project.floors).selectinload(Floor.rooms),
            selectinload(Project.bom_items),
        )
    )
    return result.scalar_one_or_none()


async def get_user_projects(db: AsyncSession, user_id: str) -> list[Project]:
    result = await db.execute(
        select(Project)
        .where(Project.owner_id == user_id)
        .options(selectinload(Project.floors))
        .order_by(Project.created_at.desc())
    )
    return list(result.scalars().all())


async def create_project(db: AsyncSession, user_id: str, data: ProjectCreate) -> Project:
    project = Project(
        name=data.name,
        address=data.address,
        total_area=data.total_area,
        owner_id=user_id,
    )
    db.add(project)
    await db.flush()

    for floor_data in data.floors:
        floor = Floor(
            project_id=project.id,
            name=floor_data.name,
            floor_number=floor_data.floor_number,
            area=floor_data.area,
        )
        db.add(floor)
        await db.flush()

        for room_data in floor_data.rooms:
            room = Room(
                floor_id=floor.id,
                name=room_data.name,
                room_type=room_data.room_type,
                area=room_data.area,
                width=room_data.width,
                height=room_data.height,
                length=room_data.length,
            )
            db.add(room)

    await db.commit()
    return await get_project(db, project.id)


async def update_project(db: AsyncSession, project_id: str, data: ProjectUpdate) -> Project | None:
    result = await db.execute(select(Project).where(Project.id == project_id))
    project = result.scalar_one_or_none()
    if not project:
        return None

    update_data = data.model_dump(exclude_unset=True)
    for key, value in update_data.items():
        setattr(project, key, value)

    await db.commit()
    await db.refresh(project)
    return project


async def delete_project(db: AsyncSession, project_id: str) -> bool:
    result = await db.execute(select(Project).where(Project.id == project_id))
    project = result.scalar_one_or_none()
    if not project:
        return False
    await db.delete(project)
    await db.commit()
    return True

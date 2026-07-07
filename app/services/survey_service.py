import json

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.survey import Survey


async def create_survey(db: AsyncSession, data: dict, rooms: list[dict]) -> Survey:
    """创建测量记录,自动计算总面积和每个房间面积"""
    # 自动计算每个房间的面积 (width × length)
    total = 0.0
    for r in rooms:
        w = r.get("width", 0)
        h = r.get("length", 0)
        if "area" not in r or r["area"] is None:
            r["area"] = round(w * h, 2)
        total += r["area"]

    survey = Survey(
        project_id=data["project_id"],
        name=data.get("name", "现场测量"),
        surveyor=data.get("surveyor"),
        method=data.get("method", "manual"),
        wall_height=data.get("wall_height", 2.8),
        total_area=round(total, 2),
        rooms_data=json.dumps(rooms, ensure_ascii=False),
        notes=data.get("notes"),
    )
    db.add(survey)
    await db.commit()
    await db.refresh(survey)
    return survey


async def get_surveys_by_project(db: AsyncSession, project_id: str) -> list[Survey]:
    result = await db.execute(
        select(Survey).where(Survey.project_id == project_id).order_by(Survey.created_at.desc())
    )
    return list(result.scalars().all())


async def get_survey(db: AsyncSession, survey_id: str) -> Survey | None:
    result = await db.execute(select(Survey).where(Survey.id == survey_id))
    return result.scalar_one_or_none()


async def update_survey(db: AsyncSession, survey: Survey, data: dict) -> Survey:
    for field in ("name", "surveyor", "method", "wall_height", "status", "notes"):
        if field in data and data[field] is not None:
            setattr(survey, field, data[field])
    if "rooms" in data and data["rooms"] is not None:
        rooms = data["rooms"]
        total = 0.0
        for r in rooms:
            w = r.get("width", 0)
            h = r.get("length", 0)
            if "area" not in r or r["area"] is None:
                r["area"] = round(w * h, 2)
            total += r["area"]
        survey.rooms = rooms
        survey.total_area = round(total, 2)
    await db.commit()
    await db.refresh(survey)
    return survey


async def delete_survey(db: AsyncSession, survey: Survey) -> None:
    await db.delete(survey)
    await db.commit()


async def apply_survey_to_project(db: AsyncSession, survey: Survey) -> dict:
    """将测量数据应用到项目的楼层和房间"""
    from app.models.project import Project, Floor, Room
    from sqlalchemy import select as sa_select

    # 直接查询项目而非使用 relationship(避免 lazy-load greenlet 问题)
    result = await db.execute(sa_select(Project).where(Project.id == survey.project_id))
    project = result.scalar_one_or_none()

    if project:
        project.total_area = survey.total_area
    await db.flush()

    # 创建或更新第1层
    result = await db.execute(
        select(Floor).where(Floor.project_id == survey.project_id, Floor.floor_number == 1)
    )
    floor = result.scalar_one_or_none()
    if not floor:
        floor = Floor(project_id=survey.project_id, name="1层", floor_number=1, area=survey.total_area)
        db.add(floor)
        await db.flush()
    else:
        floor.area = survey.total_area

    # 同步房间
    rooms = survey.rooms
    result = await db.execute(select(Room).where(Room.floor_id == floor.id))
    existing_rooms = {r.name: r for r in result.scalars().all()}

    added, updated = 0, 0
    for rd in rooms:
        name = rd.get("name", "")
        rtype = rd.get("room_type", "bedroom")
        area = rd.get("area", 0)
        w = rd.get("width", 0)
        h = rd.get("length", 0)

        if name in existing_rooms:
            r = existing_rooms[name]
            r.room_type = rtype
            r.area = area
            r.width = w
            r.length = h
            updated += 1
        else:
            db.add(Room(floor_id=floor.id, name=name, room_type=rtype, area=area, width=w, length=h))
            added += 1

    survey.status = "completed"
    await db.commit()
    return {"added": added, "updated": updated, "total_area": survey.total_area}

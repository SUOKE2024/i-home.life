from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models.user import User
from app.schemas.project import (
    ProjectCreate,
    ProjectUpdate,
    ProjectResponse,
    ProjectListResponse,
)
from app.auth import get_current_user
from app.services.project_service import (
    get_user_projects,
    get_project,
    create_project,
    update_project,
    delete_project,
)
from app.ws import ws_manager

router = APIRouter(prefix="/projects", tags=["项目"])


@router.get("", response_model=list[ProjectListResponse])
async def list_projects(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    projects = await get_user_projects(db, current_user.id)
    return [ProjectListResponse.model_validate(p) for p in projects]


@router.get("/{project_id}", response_model=ProjectResponse)
async def get_project_detail(
    project_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    project = await get_project(db, project_id)
    if not project:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="项目不存在")
    if project.owner_id != current_user.id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="无权访问该项目")
    return ProjectResponse.model_validate(project)


@router.post("", response_model=ProjectResponse, status_code=status.HTTP_201_CREATED)
async def create_project_handler(
    data: ProjectCreate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    project = await create_project(db, current_user.id, data)
    resp = ProjectResponse.model_validate(project)
    await ws_manager.broadcast_to_project(project.id, "project.created", resp.model_dump())
    return resp


@router.patch("/{project_id}", response_model=ProjectResponse)
async def update_project_handler(
    project_id: str,
    data: ProjectUpdate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    project = await get_project(db, project_id)
    if not project:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="项目不存在")
    if project.owner_id != current_user.id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="无权修改该项目")

    updated = await update_project(db, project_id, data)
    resp = ProjectResponse.model_validate(updated)
    await ws_manager.broadcast_to_project(project_id, "project.updated", resp.model_dump())
    return resp


@router.delete("/{project_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_project_handler(
    project_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    project = await get_project(db, project_id)
    if not project:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="项目不存在")
    if project.owner_id != current_user.id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="无权删除该项目")

    await delete_project(db, project_id)
    await ws_manager.broadcast_to_project(project_id, "project.deleted", {"id": project_id})

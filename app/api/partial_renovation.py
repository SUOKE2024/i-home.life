"""F42 局部焕新 API 端点（v1.5.0, PRD v3.1 F42）"""

from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, ConfigDict
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth import get_current_user
from app.config import get_settings
from app.database import get_db
from app.models.user import User
from app.rbac import verify_project_access
from app.services import partial_renovation_service

router = APIRouter(prefix="/partial-renovation", tags=["局部焕新"])

settings = get_settings()


def _check_enabled() -> None:
    if not settings.partial_renovation_enabled:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="该功能未启用")


class PlanCreate(BaseModel):
    project_id: str
    name: str
    # kitchen_refresh / bathroom_refresh / wall_refresh / single_room / full_renovation
    scope_type: str
    # economic / comfort / quality
    budget_level: str = "comfort"


class PlanResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    project_id: str
    name: str
    scope_type: str
    budget_level: str
    duration_days: int
    budget_lower: float
    budget_upper: float
    tasks: list | None = None
    interference_plan: dict | None = None
    status: str
    notes: str | None = None
    created_at: datetime | None = None
    updated_at: datetime | None = None


@router.post("/plans", response_model=PlanResponse, status_code=status.HTTP_201_CREATED)
async def create_plan(
    data: PlanCreate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """按模板创建局部焕新计划"""
    _check_enabled()
    await verify_project_access(project_id=data.project_id, current_user=current_user, db=db)
    try:
        plan = await partial_renovation_service.generate_plan_from_template(
            db,
            project_id=data.project_id,
            name=data.name,
            scope_type=data.scope_type,
            budget_level=data.budget_level,
        )
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))
    return PlanResponse.model_validate(plan)


@router.get("/plans/project/{project_id}", response_model=list[PlanResponse])
async def list_plans(
    project_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """按项目列出局部焕新计划"""
    _check_enabled()
    await verify_project_access(project_id=project_id, current_user=current_user, db=db)
    plans = await partial_renovation_service.list_plans(db, project_id)
    return [PlanResponse.model_validate(p) for p in plans]


@router.get("/plans/{plan_id}", response_model=PlanResponse)
async def get_plan(
    plan_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """局部焕新计划详情"""
    _check_enabled()
    plan = await partial_renovation_service.get_plan(db, plan_id)
    if not plan:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="局部焕新计划不存在")
    await verify_project_access(project_id=plan.project_id, current_user=current_user, db=db)
    return PlanResponse.model_validate(plan)


@router.get("/templates")
async def list_templates(
    current_user: User = Depends(get_current_user),
):
    """可用局部焕新模板列表（含 name/duration_days/budget_range/task_count）"""
    _check_enabled()
    return partial_renovation_service.list_templates()


@router.delete("/plans/{plan_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_plan(
    plan_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """删除局部焕新计划"""
    _check_enabled()
    plan = await partial_renovation_service.get_plan(db, plan_id)
    if not plan:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="局部焕新计划不存在")
    await verify_project_access(project_id=plan.project_id, current_user=current_user, db=db)
    deleted = await partial_renovation_service.delete_plan(db, plan_id)
    if not deleted:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="局部焕新计划不存在")

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models.user import User
from app.schemas.floorplan import (
    FloorPlanCreate,
    FloorPlanResponse,
    FloorPlanListItem,
)
from app.auth import get_current_user
from app.services import floorplan_service
from app.ws import ws_manager

router = APIRouter(prefix="/floorplans", tags=["户型"])


@router.get("/project/{project_id}", response_model=list[FloorPlanListItem])
async def list_plans(
    project_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    plans = await floorplan_service.list_floor_plans(db, project_id)
    return [FloorPlanListItem.model_validate(p) for p in plans]


@router.get("/{plan_id}", response_model=FloorPlanResponse)
async def get_plan(
    plan_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    plan = await floorplan_service.get_floor_plan(db, plan_id)
    if not plan:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="方案不存在")
    return FloorPlanResponse.model_validate(plan)


@router.post("", response_model=FloorPlanResponse, status_code=status.HTTP_201_CREATED)
async def create_plan(
    data: FloorPlanCreate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    plan = await floorplan_service.create_floor_plan(db, data.model_dump())
    resp = FloorPlanResponse.model_validate(plan)
    await ws_manager.broadcast_to_project(plan.project_id, "floorplan.created", resp.model_dump())
    return resp


@router.put("/{plan_id}", response_model=FloorPlanResponse)
async def update_plan(
    plan_id: str,
    data: FloorPlanCreate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    plan = await floorplan_service.update_floor_plan(db, plan_id, data.model_dump())
    if not plan:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="方案不存在")
    resp = FloorPlanResponse.model_validate(plan)
    await ws_manager.broadcast_to_project(plan.project_id, "floorplan.updated", resp.model_dump())
    return resp


@router.delete("/{plan_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_plan(
    plan_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    plan = await floorplan_service.get_floor_plan(db, plan_id)
    if not plan:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="方案不存在")
    project_id = plan.project_id
    deleted = await floorplan_service.delete_floor_plan(db, plan_id)
    if not deleted:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="方案不存在")
    await ws_manager.broadcast_to_project(project_id, "floorplan.deleted", {"id": plan_id})

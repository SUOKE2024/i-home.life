from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models.user import User
from app.schemas.floorplan import (
    FloorPlanCreate,
    FloorPlanResponse,
    FloorPlanListItem,
    FloorPlanUpdate,
)
from app.auth import get_current_user
from app.config import get_settings
from app.rbac import verify_project_access, verify_project_collaborator_access
from app.services import floorplan_service, spatial_semantics_service
from app.ws import ws_manager

router = APIRouter(prefix="/floorplans", tags=["户型"])


@router.get("/project/{project_id}", response_model=list[FloorPlanListItem])
async def list_plans(
    project_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    await verify_project_collaborator_access(project_id=project_id, current_user=current_user, db=db)
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
    await verify_project_collaborator_access(project_id=plan.project_id, current_user=current_user, db=db)
    return FloorPlanResponse.model_validate(plan)


@router.get("/{plan_id}/semantics")
async def get_plan_semantics(
    plan_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """确定性语义空间理解 + 几何一致性校验（v1.14.0，纯规则无外部依赖）。

    返回 {semantics, consistency}；受 spatial_semantics_enabled 门控，关闭 503 诚实降级。
    """
    plan = await floorplan_service.get_floor_plan(db, plan_id)
    if not plan:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="方案不存在")
    await verify_project_collaborator_access(project_id=plan.project_id, current_user=current_user, db=db)
    if not get_settings().spatial_semantics_enabled:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="语义空间理解未启用")
    return {
        "plan_id": plan.id,
        "semantics": spatial_semantics_service.analyze_spatial_semantics(plan.data),
        "consistency": spatial_semantics_service.validate_floorplan_consistency(plan.data),
    }


@router.get("/{plan_id}/spatial-foundation")
async def get_plan_spatial_foundation(
    plan_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """确定性空间数字底座（Robot-Ready Home，v1.14.0，纯规则零外部依赖）。

    返回房间语义标注 + 邻接图 + 关键动线导航 + 毫米尺度；受 spatial_semantics_enabled 门控。
    """
    plan = await floorplan_service.get_floor_plan(db, plan_id)
    if not plan:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="方案不存在")
    await verify_project_collaborator_access(project_id=plan.project_id, current_user=current_user, db=db)
    if not get_settings().spatial_semantics_enabled:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="空间数字底座未启用")
    return spatial_semantics_service.build_spatial_foundation(plan.data)


@router.post("", response_model=FloorPlanResponse, status_code=status.HTTP_201_CREATED)
async def create_plan(
    data: FloorPlanCreate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    await verify_project_access(project_id=data.project_id, current_user=current_user, db=db)
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
    existing = await floorplan_service.get_floor_plan(db, plan_id)
    if not existing:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="方案不存在")
    await verify_project_access(project_id=existing.project_id, current_user=current_user, db=db)
    plan = await floorplan_service.update_floor_plan(db, plan_id, data.model_dump())
    if not plan:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="方案不存在")
    resp = FloorPlanResponse.model_validate(plan)
    await ws_manager.broadcast_to_project(plan.project_id, "floorplan.updated", resp.model_dump())
    return resp


@router.patch("/{plan_id}", response_model=FloorPlanResponse)
async def patch_plan(
    plan_id: str,
    data: FloorPlanUpdate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """部分更新户型方案（如仅切换 is_active 状态）"""
    existing = await floorplan_service.get_floor_plan(db, plan_id)
    if not existing:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="方案不存在")
    await verify_project_access(project_id=existing.project_id, current_user=current_user, db=db)
    update_data = data.model_dump(exclude_none=True)
    plan = await floorplan_service.update_floor_plan(db, plan_id, update_data)
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
    await verify_project_access(project_id=plan.project_id, current_user=current_user, db=db)
    project_id = plan.project_id
    deleted = await floorplan_service.delete_floor_plan(db, plan_id)
    if not deleted:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="方案不存在")
    await ws_manager.broadcast_to_project(project_id, "floorplan.deleted", {"id": plan_id})

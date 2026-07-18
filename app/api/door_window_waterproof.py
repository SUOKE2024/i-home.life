"""F23 门窗/防水工程 API 端点"""

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models.project import Project
from app.models.user import User
from app.schemas.door_window_waterproof import (
    DoorWindowSpecCreate,
    DoorWindowSpecResponse,
    DoorWindowRecommendRequest,
    WaterproofPlanCreate,
    WaterproofPlanResponse,
    WaterproofAreaRequest,
)
from app.auth import get_current_user
from app.rbac import verify_project_access
from app.services import door_window_waterproof_service as svc
from app.ws import ws_manager

router = APIRouter(prefix="/door-window-waterproof", tags=["门窗/防水工程"])


# ── 门窗选型 ──


@router.post("/door-windows", response_model=DoorWindowSpecResponse, status_code=status.HTTP_201_CREATED)
async def create_door_window(
    data: DoorWindowSpecCreate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """创建门窗选型"""
    project = await db.get(Project, data.project_id)
    if not project or project.owner_id != current_user.id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="无权访问该项目")
    spec = await svc.create_door_window(db, data.model_dump())
    resp = DoorWindowSpecResponse.model_validate(spec)
    await ws_manager.broadcast_to_project(spec.project_id, "dw_waterproof.door_window_created", resp.model_dump())
    return resp


@router.get("/door-windows/project/{project_id}", response_model=list[DoorWindowSpecResponse])
async def list_door_windows(
    project_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """列出项目门窗选型"""
    await verify_project_access(project_id=project_id, current_user=current_user, db=db)
    specs = await svc.list_door_windows(db, project_id)
    return [DoorWindowSpecResponse.model_validate(s) for s in specs]


@router.get("/door-windows/{spec_id}", response_model=DoorWindowSpecResponse)
async def get_door_window(
    spec_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """门窗选型详情"""
    spec = await svc.get_door_window(db, spec_id)
    if not spec:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="门窗选型不存在")
    await verify_project_access(project_id=spec.project_id, current_user=current_user, db=db)
    return DoorWindowSpecResponse.model_validate(spec)


@router.post("/door-windows/recommend")
async def recommend_door_window(
    data: DoorWindowRecommendRequest,
    current_user: User = Depends(get_current_user),
):
    """门窗推荐"""
    return svc.recommend_door_window(data.spec_type, data.room_type, data.opening_direction)


@router.delete("/door-windows/{spec_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_door_window(
    spec_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """删除门窗选型"""
    spec = await svc.get_door_window(db, spec_id)
    if not spec:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="门窗选型不存在")
    project = await db.get(Project, spec.project_id)
    if not project or project.owner_id != current_user.id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="无权访问该项目")
    project_id = spec.project_id
    deleted = await svc.delete_door_window(db, spec_id)
    if not deleted:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="门窗选型不存在")
    await ws_manager.broadcast_to_project(project_id, "dw_waterproof.door_window_deleted", {"id": spec_id})


# ── 防水方案 ──


@router.post("/waterproof", response_model=WaterproofPlanResponse, status_code=status.HTTP_201_CREATED)
async def create_waterproof(
    data: WaterproofPlanCreate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """创建防水方案"""
    project = await db.get(Project, data.project_id)
    if not project or project.owner_id != current_user.id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="无权访问该项目")
    plan = await svc.create_waterproof(db, data.model_dump())
    resp = WaterproofPlanResponse.model_validate(plan)
    await ws_manager.broadcast_to_project(plan.project_id, "dw_waterproof.waterproof_created", resp.model_dump())
    return resp


@router.get("/waterproof/project/{project_id}", response_model=list[WaterproofPlanResponse])
async def list_waterproofs(
    project_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """列出项目防水方案"""
    await verify_project_access(project_id=project_id, current_user=current_user, db=db)
    plans = await svc.list_waterproofs(db, project_id)
    return [WaterproofPlanResponse.model_validate(p) for p in plans]


@router.get("/waterproof/{plan_id}", response_model=WaterproofPlanResponse)
async def get_waterproof(
    plan_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """防水方案详情"""
    plan = await svc.get_waterproof(db, plan_id)
    if not plan:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="防水方案不存在")
    await verify_project_access(project_id=plan.project_id, current_user=current_user, db=db)
    return WaterproofPlanResponse.model_validate(plan)


@router.post("/waterproof/{plan_id}/compute-area")
async def compute_waterproof_area_endpoint(
    plan_id: str,
    data: WaterproofAreaRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """防水面积计算"""
    plan = await svc.get_waterproof(db, plan_id)
    if not plan:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="防水方案不存在")
    await verify_project_access(project_id=plan.project_id, current_user=current_user, db=db)
    result = svc.compute_waterproof_area(plan.room_type, data.room_width, data.room_length, data.wall_height_mm)
    return {"plan_id": plan_id, **result}


@router.get("/waterproof/{plan_id}/validation")
async def validate_waterproof(
    plan_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """防水规范校验"""
    plan = await svc.get_waterproof(db, plan_id)
    if not plan:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="防水方案不存在")
    await verify_project_access(project_id=plan.project_id, current_user=current_user, db=db)
    result = svc.validate_waterproof_spec(plan)
    return {"plan_id": plan_id, **result}


@router.delete("/waterproof/{plan_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_waterproof(
    plan_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """删除防水方案"""
    plan = await svc.get_waterproof(db, plan_id)
    if not plan:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="防水方案不存在")
    project = await db.get(Project, plan.project_id)
    if not project or project.owner_id != current_user.id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="无权访问该项目")
    project_id = plan.project_id
    deleted = await svc.delete_waterproof(db, plan_id)
    if not deleted:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="防水方案不存在")
    await ws_manager.broadcast_to_project(project_id, "dw_waterproof.waterproof_deleted", {"id": plan_id})

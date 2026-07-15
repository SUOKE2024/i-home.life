"""F18 厨卫水电 API 端点"""

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models.project import Project
from app.models.user import User
from app.schemas.kitchen_bath_mep import (
    KitchenBathMEPPlanCreate,
    KitchenBathMEPPlanResponse,
    MEPPointCreate,
    MEPPointResponse,
    AutoGenerateRequest,
)
from app.auth import get_current_user
from app.rbac import verify_project_access
from app.services import kitchen_bath_mep_service as svc
from app.ws import ws_manager

router = APIRouter(prefix="/mep-kb", tags=["厨卫水电"])


@router.post("/plans", response_model=KitchenBathMEPPlanResponse, status_code=status.HTTP_201_CREATED)
async def create_plan(
    data: KitchenBathMEPPlanCreate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """创建厨卫水电方案"""
    project = await db.get(Project, data.project_id)
    if not project or project.owner_id != current_user.id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="无权访问该项目")
    plan = await svc.create_plan(db, data.model_dump())
    resp = KitchenBathMEPPlanResponse.model_validate(plan)
    await ws_manager.broadcast_to_project(plan.project_id, "mep_kb.plan_created", resp.model_dump())
    return resp


@router.get("/plans/project/{project_id}", response_model=list[KitchenBathMEPPlanResponse])
async def list_plans(
    project_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """列出项目厨卫水电方案"""
    plans = await svc.list_plans(db, project_id)
    return [KitchenBathMEPPlanResponse.model_validate(p) for p in plans]


@router.get("/plans/{plan_id}", response_model=KitchenBathMEPPlanResponse)
async def get_plan(
    plan_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """厨卫水电方案详情"""
    plan = await svc.get_plan(db, plan_id)
    if not plan:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="厨卫水电方案不存在")
    return KitchenBathMEPPlanResponse.model_validate(plan)


@router.post("/plans/{plan_id}/auto-generate")
async def auto_generate(
    plan_id: str,
    data: AutoGenerateRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """自动生成水电点位 (基于 room_type 和设备清单)"""
    plan = await svc.get_plan(db, plan_id)
    if not plan:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="厨卫水电方案不存在")
    await verify_project_access(project_id=plan.project_id, current_user=current_user, db=db)

    # 生成给排水点位
    water_result = svc.generate_water_inlets(plan.room_type, data.devices)
    # 生成点位记录
    created_points = []
    for inlet in water_result["water_inlets"]:
        point_data = {
            "plan_id": plan_id,
            "point_type": "water_inlet",
            "device": inlet["device"],
            "position_x": inlet["position"]["x"],
            "position_y": inlet["position"]["y"],
            "position_z": inlet["position"]["z"],
            "spec": inlet["spec"],
            "notes": inlet.get("note"),
        }
        point = await svc.add_point(db, point_data)
        created_points.append(MEPPointResponse.model_validate(point))
    for drain in water_result["drains"]:
        point_data = {
            "plan_id": plan_id,
            "point_type": "drain",
            "device": drain["device"],
            "position_x": drain["position"]["x"],
            "position_y": drain["position"]["y"],
            "position_z": drain["position"]["z"],
        }
        point = await svc.add_point(db, point_data)
        created_points.append(MEPPointResponse.model_validate(point))

    await ws_manager.broadcast_to_project(
        plan.project_id,
        "mep_kb.auto_generated",
        {"plan_id": plan_id, "point_count": len(created_points)},
    )
    return {
        "plan_id": plan_id,
        "water_inlets": water_result["water_inlets"],
        "drains": water_result["drains"],
        "points": created_points,
        "total": len(created_points),
    }


@router.get("/plans/{plan_id}/circuits")
async def design_circuits(
    plan_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """厨房回路设计"""
    plan = await svc.get_plan(db, plan_id)
    if not plan:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="厨卫水电方案不存在")
    # 从已有点位提取设备清单
    devices: list[str] = []
    seen = set()
    for p in plan.points:
        if p.device and p.device not in seen:
            devices.append(p.device)
            seen.add(p.device)
    if not devices:
        # 默认厨房设备
        devices = ["烤箱", "洗碗机", "热水器", "垃圾处理器"]
    result = svc.design_kitchen_circuits(devices)
    return {"plan_id": plan_id, **result}


@router.get("/plans/{plan_id}/equipotential")
async def validate_equipotential(
    plan_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """等电位校验"""
    plan = await svc.get_plan(db, plan_id)
    if not plan:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="厨卫水电方案不存在")
    result = svc.validate_bathroom_equipotential(plan)
    return {"plan_id": plan_id, **result}


@router.get("/plans/{plan_id}/gas")
async def plan_gas(
    plan_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """燃气管道规划"""
    plan = await svc.get_plan(db, plan_id)
    if not plan:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="厨卫水电方案不存在")
    result = svc.plan_gas_pipe(plan)
    return {"plan_id": plan_id, **result}


@router.post("/plans/{plan_id}/points", response_model=MEPPointResponse, status_code=status.HTTP_201_CREATED)
async def add_point(
    plan_id: str,
    data: MEPPointCreate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """添加点位"""
    plan = await svc.get_plan(db, plan_id)
    if not plan:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="厨卫水电方案不存在")
    await verify_project_access(project_id=plan.project_id, current_user=current_user, db=db)
    point_data = data.model_dump()
    point_data["plan_id"] = plan_id
    point = await svc.add_point(db, point_data)
    resp = MEPPointResponse.model_validate(point)
    await ws_manager.broadcast_to_project(plan.project_id, "mep_kb.point_added", resp.model_dump())
    return resp


@router.get("/plans/{plan_id}/points", response_model=list[MEPPointResponse])
async def list_points(
    plan_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """列出点位"""
    points = await svc.list_points(db, plan_id)
    return [MEPPointResponse.model_validate(p) for p in points]


@router.delete("/points/{point_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_point(
    point_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """删除点位"""
    deleted = await svc.delete_point(db, point_id)
    if not deleted:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="点位不存在")


@router.delete("/plans/{plan_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_plan(
    plan_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """删除厨卫水电方案"""
    plan = await svc.get_plan(db, plan_id)
    if not plan:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="厨卫水电方案不存在")
    project = await db.get(Project, plan.project_id)
    if not project or project.owner_id != current_user.id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="无权访问该项目")
    project_id = plan.project_id
    deleted = await svc.delete_plan(db, plan_id)
    if not deleted:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="厨卫水电方案不存在")
    await ws_manager.broadcast_to_project(project_id, "mep_kb.plan_deleted", {"id": plan_id})

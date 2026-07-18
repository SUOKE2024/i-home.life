"""F31 智能家居方案设计器 API"""

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models.project import Project
from app.models.user import User
from app.auth import get_current_user
from app.schemas.smart_home import (
    SmartHomeSchemeCreate,
    SmartHomeSchemeResponse,
    SmartDeviceCreate,
    SmartDeviceResponse,
    AutoRecommendResult,
    WiringPlanResult,
    ProtocolAdviceResult,
    PriceComputeResult,
)
from app.rbac import verify_project_access
from app.services import smart_home_service as svc
from app.ws import ws_manager

router = APIRouter(prefix="/smart-home", tags=["智能家居方案"])


# ── 方案 ──


@router.post("/schemes", response_model=SmartHomeSchemeResponse, status_code=status.HTTP_201_CREATED)
async def create_scheme(
    data: SmartHomeSchemeCreate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    project = await db.get(Project, data.project_id)
    if not project or project.owner_id != current_user.id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="无权访问该项目")
    scheme = await svc.create_scheme(db, data.model_dump())
    resp = SmartHomeSchemeResponse.model_validate(scheme)
    await ws_manager.broadcast_to_project(scheme.project_id, "smart.scheme.created", resp.model_dump())
    return resp


@router.get("/schemes/project/{project_id}", response_model=list[SmartHomeSchemeResponse])
async def list_schemes_by_project(
    project_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    await verify_project_access(project_id=project_id, current_user=current_user, db=db)
    schemes = await svc.list_schemes_by_project(db, project_id)
    return [SmartHomeSchemeResponse.model_validate(s) for s in schemes]


@router.get("/schemes/{scheme_id}", response_model=SmartHomeSchemeResponse)
async def get_scheme(
    scheme_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    scheme = await svc.get_scheme(db, scheme_id)
    if not scheme:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="方案不存在")
    await verify_project_access(project_id=scheme.project_id, current_user=current_user, db=db)
    return SmartHomeSchemeResponse.model_validate(scheme)


@router.delete("/schemes/{scheme_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_scheme(
    scheme_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    scheme = await svc.get_scheme(db, scheme_id)
    if not scheme:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="方案不存在")
    project = await db.get(Project, scheme.project_id)
    if not project or project.owner_id != current_user.id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="无权访问该项目")
    project_id = scheme.project_id
    deleted = await svc.delete_scheme(db, scheme_id)
    if not deleted:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="方案不存在")
    await ws_manager.broadcast_to_project(project_id, "smart.scheme.deleted", {"id": scheme_id})


# ── 自动推荐设备 ──


@router.post("/schemes/{scheme_id}/auto-recommend", response_model=AutoRecommendResult)
async def auto_recommend(
    scheme_id: str,
    body: dict,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    scheme = await svc.get_scheme(db, scheme_id)
    if not scheme:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="方案不存在")
    await verify_project_access(project_id=scheme.project_id, current_user=current_user, db=db)
    room_type = body.get("room_type") or scheme.room_type
    room_area = float(body.get("room_area") or 20.0)
    protocol = body.get("protocol") or scheme.protocol
    hub_brand = body.get("hub_brand") or scheme.hub_brand
    result = await svc.auto_recommend_devices(db, scheme, room_type, room_area, protocol, hub_brand)
    await ws_manager.broadcast_to_project(
        scheme.project_id,
        "smart.scheme.auto_recommended",
        {"scheme_id": scheme_id, "device_count": len(result["recommended_devices"])},
    )
    return AutoRecommendResult(**result)


# ── 布线规划 ──


@router.get("/schemes/{scheme_id}/wiring", response_model=WiringPlanResult)
async def wiring_plan(
    scheme_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    scheme = await svc.get_scheme(db, scheme_id)
    if not scheme:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="方案不存在")
    await verify_project_access(project_id=scheme.project_id, current_user=current_user, db=db)
    result = await svc.plan_wiring(db, scheme)
    return WiringPlanResult(**result)


# ── 协议选型建议 ──


@router.get("/schemes/{scheme_id}/protocol-advice", response_model=ProtocolAdviceResult)
async def protocol_advice(
    scheme_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    scheme = await svc.get_scheme(db, scheme_id)
    if not scheme:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="方案不存在")
    await verify_project_access(project_id=scheme.project_id, current_user=current_user, db=db)
    devices = scheme.devices or await svc.list_devices(db, scheme_id)
    result = svc.recommend_protocol(scheme.hub_brand, devices)
    return ProtocolAdviceResult(**result)


# ── 方案总价 ──


@router.get("/schemes/{scheme_id}/price", response_model=PriceComputeResult)
async def compute_price(
    scheme_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    scheme = await svc.get_scheme(db, scheme_id)
    if not scheme:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="方案不存在")
    await verify_project_access(project_id=scheme.project_id, current_user=current_user, db=db)
    result = await svc.compute_total_price(db, scheme)
    return PriceComputeResult(**result)


# ── 设备 ──


@router.post("/schemes/{scheme_id}/devices", response_model=SmartDeviceResponse, status_code=status.HTTP_201_CREATED)
async def add_device(
    scheme_id: str,
    data: SmartDeviceCreate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    scheme = await svc.get_scheme(db, scheme_id)
    if not scheme:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="方案不存在")
    await verify_project_access(project_id=scheme.project_id, current_user=current_user, db=db)
    device = await svc.add_device(db, scheme_id, data.model_dump())
    resp = SmartDeviceResponse.model_validate(device)
    await ws_manager.broadcast_to_project(scheme.project_id, "smart.device.added", resp.model_dump())
    return resp


@router.get("/schemes/{scheme_id}/devices", response_model=list[SmartDeviceResponse])
async def list_devices(
    scheme_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    scheme = await svc.get_scheme(db, scheme_id)
    if not scheme:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="方案不存在")
    await verify_project_access(project_id=scheme.project_id, current_user=current_user, db=db)
    devices = await svc.list_devices(db, scheme_id)
    return [SmartDeviceResponse.model_validate(d) for d in devices]


@router.delete("/devices/{device_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_device(
    device_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    from sqlalchemy import select
    from app.models.smart_home import SmartDevice
    result = await db.execute(select(SmartDevice).where(SmartDevice.id == device_id))
    device = result.scalar_one_or_none()
    if not device:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="设备不存在")
    scheme = await svc.get_scheme(db, device.scheme_id)
    if scheme:
        await verify_project_access(project_id=scheme.project_id, current_user=current_user, db=db)
    deleted = await svc.delete_device(db, device_id)
    if not deleted:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="设备不存在")

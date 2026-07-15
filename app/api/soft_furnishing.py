"""F24/F25 软装搭配 + 收纳系统 API"""

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models.user import User
from app.auth import get_current_user
from app.schemas.soft_furnishing import (
    SoftFurnishingSchemeCreate,
    SoftFurnishingSchemeResponse,
    SoftFurnishingItemCreate,
    SoftFurnishingItemResponse,
    SoftFurnishingItemStatusUpdate,
    StorageSystemCreate,
    StorageSystemResponse,
    ColorHarmonyResult,
    BudgetUsageResult,
    StorageRecommendResult,
    StorageCapacityResult,
)
from app.rbac import verify_project_access
from app.services import soft_furnishing_service as svc
from app.ws import ws_manager

router = APIRouter(prefix="/soft-furnishing", tags=["软装收纳"])


# ── 方案 ──


@router.post("/schemes", response_model=SoftFurnishingSchemeResponse, status_code=status.HTTP_201_CREATED)
async def create_scheme(
    data: SoftFurnishingSchemeCreate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    await verify_project_access(project_id=data.project_id, current_user=current_user, db=db)
    scheme = await svc.create_scheme(db, data.model_dump())
    resp = SoftFurnishingSchemeResponse.model_validate(scheme)
    await ws_manager.broadcast_to_project(scheme.project_id, "soft.scheme.created", resp.model_dump())
    return resp


@router.get("/schemes/project/{project_id}", response_model=list[SoftFurnishingSchemeResponse])
async def list_schemes_by_project(
    project_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    await verify_project_access(project_id=project_id, current_user=current_user, db=db)
    schemes = await svc.list_schemes_by_project(db, project_id)
    return [SoftFurnishingSchemeResponse.model_validate(s) for s in schemes]


@router.get("/schemes/{scheme_id}", response_model=SoftFurnishingSchemeResponse)
async def get_scheme(
    scheme_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    scheme = await svc.get_scheme(db, scheme_id)
    if not scheme:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="方案不存在")
    await verify_project_access(project_id=scheme.project_id, current_user=current_user, db=db)
    return SoftFurnishingSchemeResponse.model_validate(scheme)


@router.delete("/schemes/{scheme_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_scheme(
    scheme_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    scheme = await svc.get_scheme(db, scheme_id)
    if not scheme:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="方案不存在")
    await verify_project_access(project_id=scheme.project_id, current_user=current_user, db=db)
    project_id = scheme.project_id
    deleted = await svc.delete_scheme(db, scheme_id)
    if not deleted:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="方案不存在")
    await ws_manager.broadcast_to_project(project_id, "soft.scheme.deleted", {"id": scheme_id})


# ── AI 搭配 ──


@router.post("/schemes/{scheme_id}/ai-match", response_model=dict)
async def ai_match(
    scheme_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    scheme = await svc.get_scheme(db, scheme_id)
    if not scheme:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="方案不存在")
    await verify_project_access(project_id=scheme.project_id, current_user=current_user, db=db)
    result = await svc.ai_match_soft_furnishing(db, scheme)
    await ws_manager.broadcast_to_project(scheme.project_id, "soft.ai.matched", result)
    return result


# ── 配色和谐度 ──


@router.get("/schemes/{scheme_id}/color-harmony", response_model=ColorHarmonyResult)
async def color_harmony(
    scheme_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    scheme = await svc.get_scheme(db, scheme_id)
    if not scheme:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="方案不存在")
    await verify_project_access(project_id=scheme.project_id, current_user=current_user, db=db)
    return ColorHarmonyResult(**svc.compute_color_harmony(scheme))


# ── 预算 ──


@router.get("/schemes/{scheme_id}/budget", response_model=BudgetUsageResult)
async def budget_usage(
    scheme_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    scheme = await svc.get_scheme(db, scheme_id)
    if not scheme:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="方案不存在")
    await verify_project_access(project_id=scheme.project_id, current_user=current_user, db=db)
    return BudgetUsageResult(**svc.compute_budget_usage(scheme))


# ── 单品 ──


@router.post(
    "/schemes/{scheme_id}/items",
    response_model=SoftFurnishingItemResponse,
    status_code=status.HTTP_201_CREATED,
)
async def add_item(
    scheme_id: str,
    data: SoftFurnishingItemCreate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    scheme = await svc.get_scheme(db, scheme_id)
    if not scheme:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="方案不存在")
    await verify_project_access(project_id=scheme.project_id, current_user=current_user, db=db)
    item = await svc.add_item(db, scheme_id, data.model_dump())
    resp = SoftFurnishingItemResponse.model_validate(item)
    await ws_manager.broadcast_to_project(scheme.project_id, "soft.item.added", resp.model_dump())
    return resp


@router.get("/schemes/{scheme_id}/items", response_model=list[SoftFurnishingItemResponse])
async def list_items(
    scheme_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    scheme = await svc.get_scheme(db, scheme_id)
    if not scheme:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="方案不存在")
    await verify_project_access(project_id=scheme.project_id, current_user=current_user, db=db)
    items = await svc.list_items(db, scheme_id)
    return [SoftFurnishingItemResponse.model_validate(i) for i in items]


@router.delete("/items/{item_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_item(
    item_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    from sqlalchemy import select
    from app.models.soft_furnishing import SoftFurnishingItem
    item_result = await db.execute(select(SoftFurnishingItem).where(SoftFurnishingItem.id == item_id))
    existing = item_result.scalar_one_or_none()
    if not existing:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="单品不存在")
    scheme = await svc.get_scheme(db, existing.scheme_id)
    if scheme:
        await verify_project_access(project_id=scheme.project_id, current_user=current_user, db=db)
    deleted = await svc.delete_item(db, item_id)
    if not deleted:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="单品不存在")


@router.patch("/items/{item_id}/status", response_model=SoftFurnishingItemResponse)
async def update_item_status(
    item_id: str,
    data: SoftFurnishingItemStatusUpdate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    item = await svc.update_item_status(db, item_id, data.status)
    if not item:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="单品不存在")
    resp = SoftFurnishingItemResponse.model_validate(item)
    # 项目级广播(查 scheme.project_id)
    scheme = await svc.get_scheme(db, item.scheme_id)
    if scheme:
        await verify_project_access(project_id=scheme.project_id, current_user=current_user, db=db)
        await ws_manager.broadcast_to_project(scheme.project_id, "soft.item.status_changed", resp.model_dump())
    return resp


# ── 收纳系统 ──


@router.post("/schemes/{scheme_id}/storage", response_model=StorageSystemResponse, status_code=status.HTTP_201_CREATED)
async def add_storage(
    scheme_id: str,
    data: StorageSystemCreate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    scheme = await svc.get_scheme(db, scheme_id)
    if not scheme:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="方案不存在")
    await verify_project_access(project_id=scheme.project_id, current_user=current_user, db=db)
    storage = await svc.add_storage(db, scheme_id, data.model_dump())
    resp = StorageSystemResponse.model_validate(storage)
    await ws_manager.broadcast_to_project(scheme.project_id, "soft.storage.added", resp.model_dump())
    return resp


@router.get("/schemes/{scheme_id}/storage", response_model=list[StorageSystemResponse])
async def list_storages(
    scheme_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    scheme = await svc.get_scheme(db, scheme_id)
    if not scheme:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="方案不存在")
    await verify_project_access(project_id=scheme.project_id, current_user=current_user, db=db)
    storages = await svc.list_storages(db, scheme_id)
    return [StorageSystemResponse.model_validate(s) for s in storages]


@router.get("/storage/{storage_id}/capacity", response_model=StorageCapacityResult)
async def storage_capacity(
    storage_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """获取指定收纳系统的容量计算结果"""
    from sqlalchemy import select
    from app.models.soft_furnishing import StorageSystem
    result = await db.execute(select(StorageSystem).where(StorageSystem.id == storage_id))
    storage = result.scalar_one_or_none()
    if not storage:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="收纳系统不存在")
    scheme = await svc.get_scheme(db, storage.scheme_id)
    if scheme:
        await verify_project_access(project_id=scheme.project_id, current_user=current_user, db=db)
    return StorageCapacityResult(**svc.compute_storage_capacity(storage))


@router.post("/storage/recommend", response_model=StorageRecommendResult)
async def recommend_storage(body: dict, current_user: User = Depends(get_current_user)):
    """收纳方案推荐 — body: { room_name, room_area, family_size }"""
    room_name = body.get("room_name") or ""
    room_area = float(body.get("room_area") or 0)
    family_size = int(body.get("family_size") or 1)
    result = svc.recommend_storage_solution(room_name, room_area, family_size)
    return StorageRecommendResult(**result)

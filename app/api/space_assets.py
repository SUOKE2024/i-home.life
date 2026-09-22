"""空间资产台账 API — Phase 3 存量空间资产化（2026-09-13）

端点（均需 PASETO 鉴权）：
- GET    /api/space-assets/enums              业态/类别/状态枚举（对齐索克生活口径）
- GET    /api/space-assets/summary            资产组合汇总（台账看板）
- POST   /api/space-assets                    登记资产
- GET    /api/space-assets                    列出资产（owner 归属隔离）
- GET    /api/space-assets/{asset_id}         资产详情
- PATCH  /api/space-assets/{asset_id}         更新资产
- DELETE /api/space-assets/{asset_id}         删除资产
- POST   /api/space-assets/{asset_id}/status  改造状态机流转
- GET    /api/space-assets/{asset_id}/readiness 智能化就绪度评分明细

越权防护：所有单资产操作校验 owner_id == current_user.id 或 admin（403）；
传入 project_id 时额外走 verify_project_access 项目归属校验。
轻资产约束：platform_role 只读输出，写入被 service 层强制覆盖为 service_provider。
"""

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth import get_current_user
from app.config import get_settings
from app.database import get_db
from app.models.user import User
from app.rbac import verify_project_access
from app.schemas.space_asset import (
    EnumsResponse,
    PortfolioSummaryResponse,
    ReadinessBreakdownResponse,
    SpaceAssetCreate,
    SpaceAssetResponse,
    SpaceAssetUpdate,
    StatusTransitionRequest,
)
from app.models.space_asset import (
    ASSET_CATEGORIES,
    BUSINESS_FORMATS,
    HOLDER_TYPES,
    PLATFORM_ROLE,
    RENOVATION_STATUSES,
)
from app.services import space_asset_service as svc

router = APIRouter(prefix="/space-assets", tags=["空间资产台账"])

settings = get_settings()


def _require_feature() -> None:
    if not settings.space_asset_ledger_enabled:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="空间资产台账未启用（space_asset_ledger_enabled=False）",
        )


async def _load_owned_asset(
    db: AsyncSession, asset_id: str, current_user: User
):
    """加载资产并校验归属（owner 本人或平台管理员）。"""
    asset = await svc.get_asset(db, asset_id)
    if not asset:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="空间资产不存在")
    if asset.owner_id != current_user.id and current_user.role != "admin":
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="无权访问该空间资产")
    return asset


@router.get("/enums", response_model=EnumsResponse)
async def get_enums(current_user: User = Depends(get_current_user)):
    """返回业态/类别/持有方类型/改造状态枚举（与索克生活 lodge 业态口径对齐）。"""
    _require_feature()
    return EnumsResponse(
        asset_categories=list(ASSET_CATEGORIES),
        business_formats=list(BUSINESS_FORMATS),
        holder_types=list(HOLDER_TYPES),
        renovation_statuses=list(RENOVATION_STATUSES),
        platform_role=PLATFORM_ROLE,
    )


@router.get("/summary", response_model=PortfolioSummaryResponse)
async def portfolio_summary(
    all_owners: bool = Query(default=False, description="仅管理员可跨 owner 汇总"),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """资产组合汇总（台账看板）。非管理员仅能汇总自己的资产。"""
    _require_feature()
    if all_owners and current_user.role != "admin":
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="仅管理员可跨 owner 汇总")
    owner_id = None if all_owners else current_user.id
    return PortfolioSummaryResponse(**await svc.portfolio_summary(db, owner_id=owner_id))


@router.post("", response_model=SpaceAssetResponse, status_code=status.HTTP_201_CREATED)
async def create_asset(
    data: SpaceAssetCreate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """登记空间资产（轻资产：持有方必须为外部主体）。"""
    _require_feature()
    if data.project_id:
        await verify_project_access(
            project_id=data.project_id, current_user=current_user, db=db
        )
    payload = data.model_dump(exclude_none=True)
    payload["owner_id"] = current_user.id
    try:
        asset = await svc.create_asset(db, payload)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_CONTENT, detail=str(e))
    return SpaceAssetResponse.model_validate(asset)


@router.get("", response_model=list[SpaceAssetResponse])
async def list_assets(
    asset_category: str | None = None,
    renovation_status: str | None = None,
    city: str | None = None,
    limit: int = Query(default=50, ge=1, le=200),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """列出空间资产（非管理员仅返回自己的资产）。"""
    _require_feature()
    owner_id = None if current_user.role == "admin" else current_user.id
    assets = await svc.list_assets(
        db, owner_id=owner_id, asset_category=asset_category,
        renovation_status=renovation_status, city=city, limit=limit,
    )
    return [SpaceAssetResponse.model_validate(a) for a in assets]


@router.get("/{asset_id}", response_model=SpaceAssetResponse)
async def get_asset(
    asset_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    _require_feature()
    asset = await _load_owned_asset(db, asset_id, current_user)
    return SpaceAssetResponse.model_validate(asset)


@router.patch("/{asset_id}", response_model=SpaceAssetResponse)
async def update_asset(
    asset_id: str,
    data: SpaceAssetUpdate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """更新资产（状态流转须走 /status 端点；platform_role 不可改写）。"""
    _require_feature()
    await _load_owned_asset(db, asset_id, current_user)
    if data.project_id:
        await verify_project_access(
            project_id=data.project_id, current_user=current_user, db=db
        )
    try:
        asset = await svc.update_asset(db, asset_id, data.model_dump(exclude_none=True))
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_CONTENT, detail=str(e))
    if not asset:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="空间资产不存在")
    return SpaceAssetResponse.model_validate(asset)


@router.delete("/{asset_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_asset(
    asset_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    _require_feature()
    await _load_owned_asset(db, asset_id, current_user)
    await svc.delete_asset(db, asset_id)


@router.post("/{asset_id}/status", response_model=SpaceAssetResponse)
async def transition_status(
    asset_id: str,
    data: StatusTransitionRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """改造状态机流转（非法流转 409）。"""
    _require_feature()
    await _load_owned_asset(db, asset_id, current_user)
    asset, error = await svc.transition_renovation_status(db, asset_id, data.new_status)
    if asset is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="空间资产不存在")
    if error:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=error)
    return SpaceAssetResponse.model_validate(asset)


@router.get("/{asset_id}/readiness", response_model=ReadinessBreakdownResponse)
async def get_readiness(
    asset_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """智能化就绪度评分明细（四维确定性评分，无数据计 0 不虚增）。"""
    _require_feature()
    asset = await _load_owned_asset(db, asset_id, current_user)
    score, breakdown = svc.compute_smart_readiness(
        matter_device_count=asset.matter_device_count or 0,
        sensor_count=asset.sensor_count or 0,
        scene_automation_count=asset.scene_automation_count or 0,
        accessibility_status=asset.accessibility_status or "unknown",
        fire_safety_status=asset.fire_safety_status or "unknown",
    )
    return ReadinessBreakdownResponse(
        asset_id=asset.id, score=score, smart_ready=asset.smart_ready, breakdown=breakdown,
    )

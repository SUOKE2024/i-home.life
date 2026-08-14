"""窗帘智能展厅 API — 单店铺固定展厅目录查询

复用现有 /api/materials/bom 加入 BOM（curtain_products.material_id 映射 materials.id）。
"""

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth import get_current_user
from app.database import get_db
from app.models.user import User
from app.schemas.curtain_showroom import (
    CurtainProductResponse,
    CurtainShowroomAreaResponse,
    CurtainShowroomOverviewResponse,
    CurtainShowroomResponse,
    CurtainSeriesResponse,
    CurtainInstallationResponse,
    CurtainLightingPresetResponse,
)
from app.services import curtain_showroom_service

router = APIRouter(prefix="/curtain-showroom", tags=["窗帘展厅"])


@router.get(
    "/overview",
    response_model=CurtainShowroomOverviewResponse,
    summary="窗帘展厅总览",
    description="返回展厅店铺 + 系列 + 安装方式 + 灯光预设 + 展示区域（单店铺固定）。",
)
async def get_overview(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    showroom = await curtain_showroom_service.get_showroom(db)
    if not showroom:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="窗帘展厅未配置（请先执行 seed_curtain_showroom）",
        )
    series = await curtain_showroom_service.list_series(db, showroom.id)
    installations = await curtain_showroom_service.list_installations(db)
    lighting = await curtain_showroom_service.list_lighting_presets(db)
    areas = await curtain_showroom_service.list_areas(db, showroom.id)
    return CurtainShowroomOverviewResponse(
        showroom=CurtainShowroomResponse.model_validate(showroom),
        series=[CurtainSeriesResponse.model_validate(s) for s in series],
        installations=[CurtainInstallationResponse.model_validate(i) for i in installations],
        lighting_presets=[CurtainLightingPresetResponse.model_validate(lp) for lp in lighting],
        areas=[CurtainShowroomAreaResponse.model_validate(a) for a in areas],
    )


@router.get(
    "/products",
    response_model=list[CurtainProductResponse],
    summary="窗帘展品列表",
    description="按系列/品牌/材质筛选展品（3D 换装数据源）。",
)
async def list_products(
    series_id: str | None = Query(None),
    brand: str | None = Query(None),
    fabric: str | None = Query(None),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    showroom = await curtain_showroom_service.get_showroom(db)
    if not showroom:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="窗帘展厅未配置（请先执行 seed_curtain_showroom）",
        )
    products = await curtain_showroom_service.list_products(
        db, showroom.id, series_id=series_id, brand=brand, fabric=fabric
    )
    return [CurtainProductResponse.model_validate(p) for p in products]

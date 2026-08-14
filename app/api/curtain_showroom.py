"""窗帘智能展厅 API — 单店铺固定展厅目录查询

复用现有 /api/materials/bom 加入 BOM（curtain_products.material_id 映射 materials.id）。
"""

from fastapi import APIRouter, Depends, File, HTTPException, Query, UploadFile, status
from fastapi.responses import Response
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

# 贴图三件套字段映射：map_type → (url 字段, 数据字段, MIME 字段)
_MAP_TYPE_FIELDS = {
    "texture": ("texture_url", "texture_data", "texture_content_type"),
    "normal": ("normal_url", "normal_data", "normal_content_type"),
    "roughness": ("roughness_url", "roughness_data", "roughness_content_type"),
}
_ALLOWED_IMAGE_TYPES = {"image/jpeg", "image/png", "image/webp"}


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


@router.post(
    "/products/{product_id}/maps/{map_type}",
    response_model=CurtainProductResponse,
    summary="上传面料贴图（三件套）",
    description="上传 albedo(normal/roughness) 贴图（jpeg/png/webp，≤5MB）。map_type: texture/normal/roughness。",
)
async def upload_product_map(
    product_id: str,
    map_type: str,
    file: UploadFile = File(...),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    if map_type not in _MAP_TYPE_FIELDS:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="map_type 仅支持 texture/normal/roughness")
    if file.content_type not in _ALLOWED_IMAGE_TYPES:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="仅支持 jpeg/png/webp 图片")
    data = await file.read()
    if len(data) > 5 * 1024 * 1024:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="贴图过大（≤5MB）")
    product = await curtain_showroom_service.get_product(db, product_id)
    if not product:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="展品不存在")
    url_attr, data_attr, ct_attr = _MAP_TYPE_FIELDS[map_type]
    setattr(product, data_attr, data)
    setattr(product, ct_attr, file.content_type or "image/png")
    setattr(product, url_attr, f"/api/curtain-showroom/products/{product_id}/maps/{map_type}")
    await db.commit()
    await db.refresh(product)
    return CurtainProductResponse.model_validate(product)


@router.get(
    "/products/{product_id}/maps/{map_type}",
    summary="获取面料贴图（三件套）",
    description="返回展品已上传的贴图原始字节。map_type: texture/normal/roughness。",
)
async def get_product_map(
    product_id: str,
    map_type: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    if map_type not in _MAP_TYPE_FIELDS:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="map_type 仅支持 texture/normal/roughness")
    product = await curtain_showroom_service.get_product(db, product_id)
    if not product:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="展品不存在")
    _, data_attr, ct_attr = _MAP_TYPE_FIELDS[map_type]
    data = getattr(product, data_attr)
    if not data:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="贴图不存在")
    return Response(
        content=data,
        media_type=getattr(product, ct_attr) or "image/png",
    )

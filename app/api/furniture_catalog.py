"""F26 家具品类库 API"""

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models.user import User
from app.auth import get_current_user
from app.schemas.furniture_catalog import (
    FurnitureCatalogItemCreate,
    FurnitureCatalogItemUpdate,
    FurnitureCatalogItemResponse,
    ARPlacementResult,
    RoomRecommendResult,
)
from app.services import furniture_catalog_service as svc

router = APIRouter(prefix="/furniture-catalog", tags=["家具品类库"])


@router.get("", response_model=list[FurnitureCatalogItemResponse])
async def list_furniture(
    category: str | None = Query(None, description="品类"),
    subcategory: str | None = Query(None, description="子品类"),
    brand: str | None = Query(None, description="品牌"),
    style: str | None = Query(None, description="风格"),
    material: str | None = Query(None, description="材质"),
    color: str | None = Query(None, description="颜色"),
    price_min: float | None = Query(None, description="最低价"),
    price_max: float | None = Query(None, description="最高价"),
    keyword: str | None = Query(None, description="关键词"),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    filters = {
        "category": category,
        "subcategory": subcategory,
        "brand": brand,
        "style": style,
        "material": material,
        "color": color,
        "price_min": price_min,
        "price_max": price_max,
        "keyword": keyword,
    }
    items = await svc.search_furniture(db, filters)
    return [FurnitureCatalogItemResponse.model_validate(i) for i in items]


@router.post("", response_model=FurnitureCatalogItemResponse, status_code=status.HTTP_201_CREATED)
async def create_furniture(
    data: FurnitureCatalogItemCreate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    item = await svc.create_item(db, data.model_dump())
    resp = FurnitureCatalogItemResponse.model_validate(item)
    return resp


@router.get("/recommend", response_model=RoomRecommendResult)
async def recommend_for_room(
    room_type: str = Query(..., description="房间类型"),
    room_area: float = Query(20.0, description="房间面积㎡"),
    style: str = Query("modern", description="风格"),
    budget: float = Query(50000.0, description="预算"),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await svc.recommend_for_room(db, room_type, room_area, style, budget)
    return RoomRecommendResult(**result)


@router.get("/{item_id}", response_model=FurnitureCatalogItemResponse)
async def get_furniture(
    item_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    item = await svc.get_item(db, item_id)
    if not item:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="家具不存在")
    # 同时累加浏览量
    await svc.increment_views(db, item_id)
    return FurnitureCatalogItemResponse.model_validate(item)


@router.patch("/{item_id}", response_model=FurnitureCatalogItemResponse)
async def update_furniture(
    item_id: str,
    data: FurnitureCatalogItemUpdate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    item = await svc.update_item(db, item_id, data.model_dump(exclude_unset=True))
    if not item:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="家具不存在")
    resp = FurnitureCatalogItemResponse.model_validate(item)
    return resp


@router.delete("/{item_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_furniture(
    item_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    deleted = await svc.delete_item(db, item_id)
    if not deleted:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="家具不存在")


@router.get("/{item_id}/ar-placement", response_model=ARPlacementResult)
async def ar_placement(
    item_id: str,
    room_width: float = Query(..., description="房间宽 mm"),
    room_length: float = Query(..., description="房间长 mm"),
    room_height: float = Query(2800.0, description="房间高 mm"),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    item = await svc.get_item(db, item_id)
    if not item:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="家具不存在")
    result = svc.compute_ar_placement(
        item,
        {"width": room_width, "length": room_length, "height": room_height},
    )
    return ARPlacementResult(**result)


@router.get("/{item_id}/similar", response_model=list[FurnitureCatalogItemResponse])
async def similar_items(
    item_id: str,
    limit: int = Query(5, ge=1, le=20, description="返回数量"),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    items = await svc.get_similar_items(db, item_id, limit)
    return [FurnitureCatalogItemResponse.model_validate(i) for i in items]

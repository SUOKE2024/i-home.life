"""F19 电器品类库 + F20 电器点位规划 API 端点"""

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models.user import User
from app.schemas.appliance import (
    ApplianceCategoryCreate,
    ApplianceCategoryUpdate,
    ApplianceCategoryResponse,
    ApplianceCreate,
    ApplianceUpdate,
    ApplianceResponse,
    AppliancePointCreate,
    AppliancePointUpdate,
    AppliancePointResponse,
    ApplianceLoadCalcResponse,
    LoadCalcResult,
    CabinetMatchRequest,
    CabinetMatchResult,
    EmbeddingPlanResult,
    RoomApplianceRecommendResult,
)
from app.auth import get_current_user
from app.rbac import verify_project_access
from app.services import appliance_service as svc

router = APIRouter(prefix="/appliances", tags=["电器模块"])


# ════════════════════════════════════════════════════════════════
# 电器品类 CRUD (全局目录, 无 project_id)
# ════════════════════════════════════════════════════════════════


@router.post("/categories", response_model=ApplianceCategoryResponse, status_code=status.HTTP_201_CREATED)
async def create_category(
    data: ApplianceCategoryCreate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """创建电器品类"""
    cat = await svc.create_category(db, data.model_dump())
    return ApplianceCategoryResponse.model_validate(cat)


@router.get("/categories", response_model=list[ApplianceCategoryResponse])
async def list_categories(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """列出所有电器品类"""
    cats = await svc.list_categories(db)
    return [ApplianceCategoryResponse.model_validate(c) for c in cats]


@router.get("/categories/{cat_id}", response_model=ApplianceCategoryResponse)
async def get_category(
    cat_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """电器品类详情"""
    cat = await svc.get_category(db, cat_id)
    if not cat:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="电器品类不存在")
    return ApplianceCategoryResponse.model_validate(cat)


@router.put("/categories/{cat_id}", response_model=ApplianceCategoryResponse)
async def update_category(
    cat_id: str,
    data: ApplianceCategoryUpdate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """更新电器品类"""
    cat = await svc.update_category(db, cat_id, data.model_dump(exclude_unset=True))
    if not cat:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="电器品类不存在")
    return ApplianceCategoryResponse.model_validate(cat)


@router.delete("/categories/{cat_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_category(
    cat_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """删除电器品类"""
    deleted = await svc.delete_category(db, cat_id)
    if not deleted:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="电器品类不存在")


# ════════════════════════════════════════════════════════════════
# 电器实例 CRUD + 搜索 (全局目录, 无 project_id)
# ════════════════════════════════════════════════════════════════


@router.post("", response_model=ApplianceResponse, status_code=status.HTTP_201_CREATED)
async def create_appliance(
    data: ApplianceCreate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """创建电器实例"""
    appliance = await svc.create_appliance(db, data.model_dump())
    return ApplianceResponse.model_validate(appliance)


@router.get("/search", response_model=list[ApplianceResponse])
async def search_appliances(
    category_id: str | None = None,
    subcategory: str | None = None,
    brand: str | None = None,
    energy_label: str | None = None,
    keyword: str | None = None,
    price_min: float | None = None,
    price_max: float | None = None,
    sort_by: str = "price",
    sort_order: str = "asc",
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """搜索/筛选电器"""
    filters = {
        "category_id": category_id,
        "subcategory": subcategory,
        "brand": brand,
        "energy_label": energy_label,
        "keyword": keyword,
        "price_min": price_min,
        "price_max": price_max,
        "sort_by": sort_by,
        "sort_order": sort_order,
    }
    appliances = await svc.search_appliances(db, filters)
    return [ApplianceResponse.model_validate(a) for a in appliances]


@router.get("/{appliance_id}", response_model=ApplianceResponse)
async def get_appliance(
    appliance_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """电器详情"""
    appliance = await svc.get_appliance(db, appliance_id)
    if not appliance:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="电器不存在")
    return ApplianceResponse.model_validate(appliance)


@router.put("/{appliance_id}", response_model=ApplianceResponse)
async def update_appliance(
    appliance_id: str,
    data: ApplianceUpdate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """更新电器"""
    appliance = await svc.update_appliance(db, appliance_id, data.model_dump(exclude_unset=True))
    if not appliance:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="电器不存在")
    return ApplianceResponse.model_validate(appliance)


@router.delete("/{appliance_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_appliance(
    appliance_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """删除电器"""
    deleted = await svc.delete_appliance(db, appliance_id)
    if not deleted:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="电器不存在")


# ════════════════════════════════════════════════════════════════
# 电器点位规划 CRUD (项目维度)
# ════════════════════════════════════════════════════════════════


@router.post("/points", response_model=AppliancePointResponse, status_code=status.HTTP_201_CREATED)
async def create_point(
    data: AppliancePointCreate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """创建电器点位"""
    await verify_project_access(project_id=data.project_id, current_user=current_user, db=db)
    point = await svc.create_point(db, data.model_dump())
    return AppliancePointResponse.model_validate(point)


@router.get("/projects/{project_id}/points", response_model=list[AppliancePointResponse])
async def list_points_by_project(
    project_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """列出项目的所有电器点位"""
    await verify_project_access(project_id=project_id, current_user=current_user, db=db)
    points = await svc.list_points_by_project(db, project_id)
    return [AppliancePointResponse.model_validate(p) for p in points]


@router.get("/points/{point_id}", response_model=AppliancePointResponse)
async def get_point(
    point_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """电器点位详情"""
    point = await svc.get_point(db, point_id)
    if not point:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="电器点位不存在")
    await verify_project_access(project_id=point.project_id, current_user=current_user, db=db)
    return AppliancePointResponse.model_validate(point)


@router.put("/points/{point_id}", response_model=AppliancePointResponse)
async def update_point(
    point_id: str,
    data: AppliancePointUpdate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """更新电器点位"""
    point = await svc.get_point(db, point_id)
    if not point:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="电器点位不存在")
    await verify_project_access(project_id=point.project_id, current_user=current_user, db=db)
    updated = await svc.update_point(db, point_id, data.model_dump(exclude_unset=True))
    return AppliancePointResponse.model_validate(updated)


@router.delete("/points/{point_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_point(
    point_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """删除电器点位"""
    point = await svc.get_point(db, point_id)
    if not point:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="电器点位不存在")
    await verify_project_access(project_id=point.project_id, current_user=current_user, db=db)
    await svc.delete_point(db, point_id)


# ════════════════════════════════════════════════════════════════
# 全屋负载计算
# ════════════════════════════════════════════════════════════════


@router.post("/projects/{project_id}/load-calc", response_model=LoadCalcResult)
async def compute_load_calc(
    project_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """全屋负载计算 — 按回路分组统计功率、计算电流、校验线径"""
    await verify_project_access(project_id=project_id, current_user=current_user, db=db)
    result = await svc.compute_load_calc(db, project_id)
    return result


@router.get("/projects/{project_id}/load-calcs", response_model=list[ApplianceLoadCalcResponse])
async def get_load_calcs(
    project_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """获取项目负载计算结果"""
    await verify_project_access(project_id=project_id, current_user=current_user, db=db)
    calcs = await svc.get_load_calcs(db, project_id)
    return [ApplianceLoadCalcResponse.model_validate(c) for c in calcs]


# ════════════════════════════════════════════════════════════════
# 嵌入式电器尺寸匹配检查
# ════════════════════════════════════════════════════════════════


@router.post("/cabinet-match", response_model=CabinetMatchResult)
async def check_cabinet_match(
    data: CabinetMatchRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """嵌入式电器与柜体尺寸匹配检查"""
    appliance = await svc.get_appliance(db, data.appliance_id)
    if not appliance:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="电器不存在")
    result = svc.check_cabinet_match(
        appliance,
        data.cabinet_width,
        data.cabinet_depth,
        data.cabinet_height,
    )
    return result


# ════════════════════════════════════════════════════════════════
# 预埋规划引擎
# ════════════════════════════════════════════════════════════════


@router.get("/projects/{project_id}/embedding-plan", response_model=EmbeddingPlanResult)
async def get_embedding_plan(
    project_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """预埋规划引擎 — 按品类生成预埋要求清单"""
    await verify_project_access(project_id=project_id, current_user=current_user, db=db)
    result = await svc.plan_embedding(db, project_id)
    return result


# ════════════════════════════════════════════════════════════════
# 按房间推荐电器
# ════════════════════════════════════════════════════════════════


@router.get("/rooms/{room_id}/recommend", response_model=RoomApplianceRecommendResult)
async def recommend_for_room(
    room_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """按房间推荐电器"""
    result = await svc.recommend_for_room(db, room_id)
    return result

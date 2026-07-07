"""F16 厨房设计器 API 端点"""

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models.user import User
from app.schemas.kitchen import (
    KitchenDesignCreate,
    KitchenDesignResponse,
    KitchenComponentCreate,
    KitchenComponentResponse,
)
from app.auth import get_current_user
from app.services import kitchen_service
from app.ws import ws_manager

router = APIRouter(prefix="/kitchen", tags=["厨房设计器"])


@router.post("/designs", response_model=KitchenDesignResponse, status_code=status.HTTP_201_CREATED)
async def create_design(
    data: KitchenDesignCreate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """创建厨房设计"""
    design = await kitchen_service.create_design(db, data.model_dump())
    resp = KitchenDesignResponse.model_validate(design)
    await ws_manager.broadcast_to_project(design.project_id, "kitchen.design_created", resp.model_dump())
    return resp


@router.get("/designs/project/{project_id}", response_model=list[KitchenDesignResponse])
async def list_designs(
    project_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """列出项目厨房设计"""
    designs = await kitchen_service.list_designs(db, project_id)
    return [KitchenDesignResponse.model_validate(d) for d in designs]


@router.get("/designs/{design_id}", response_model=KitchenDesignResponse)
async def get_design(
    design_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """厨房设计详情"""
    design = await kitchen_service.get_design(db, design_id)
    if not design:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="厨房设计不存在")
    return KitchenDesignResponse.model_validate(design)


@router.post("/designs/{design_id}/auto-layout")
async def auto_layout(
    design_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """自动布局 — 根据布局类型生成橱柜排布"""
    design = await kitchen_service.get_design(db, design_id)
    if not design:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="厨房设计不存在")

    components_data = kitchen_service.generate_kitchen_layout(design)

    created = []
    for comp_data in components_data:
        comp_data["design_id"] = design_id
        comp = await kitchen_service.add_component(db, comp_data)
        created.append(KitchenComponentResponse.model_validate(comp))

    await ws_manager.broadcast_to_project(
        design.project_id,
        "kitchen.auto_layout_completed",
        {"design_id": design_id, "component_count": len(created)},
    )
    return {
        "design_id": design_id,
        "layout_type": design.layout_type,
        "components": created,
        "total": len(created),
    }


@router.get("/designs/{design_id}/workflow")
async def analyze_workflow(
    design_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """动线分析 — 冰箱→水槽→备餐→灶台→装盘 三角动线"""
    design = await kitchen_service.get_design(db, design_id)
    if not design:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="厨房设计不存在")
    result = kitchen_service.analyze_kitchen_workflow(design)
    return {"design_id": design_id, **result}


@router.get("/designs/{design_id}/compliance")
async def validate_compliance(
    design_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """规范校验"""
    design = await kitchen_service.get_design(db, design_id)
    if not design:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="厨房设计不存在")
    result = kitchen_service.validate_kitchen_compliance(design)
    return {"design_id": design_id, **result}


@router.post("/designs/{design_id}/components", response_model=KitchenComponentResponse, status_code=status.HTTP_201_CREATED)
async def add_component(
    design_id: str,
    data: KitchenComponentCreate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """添加厨房组件"""
    design = await kitchen_service.get_design(db, design_id)
    if not design:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="厨房设计不存在")
    comp_data = data.model_dump()
    comp_data["design_id"] = design_id
    component = await kitchen_service.add_component(db, comp_data)
    resp = KitchenComponentResponse.model_validate(component)
    await ws_manager.broadcast_to_project(design.project_id, "kitchen.component_added", resp.model_dump())
    return resp


@router.get("/designs/{design_id}/components", response_model=list[KitchenComponentResponse])
async def list_components(
    design_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """列出厨房组件"""
    components = await kitchen_service.list_components(db, design_id)
    return [KitchenComponentResponse.model_validate(c) for c in components]


@router.delete("/components/{component_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_component(
    component_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """删除厨房组件"""
    deleted = await kitchen_service.delete_component(db, component_id)
    if not deleted:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="厨房组件不存在")


@router.delete("/designs/{design_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_design(
    design_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """删除厨房设计"""
    design = await kitchen_service.get_design(db, design_id)
    if not design:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="厨房设计不存在")
    project_id = design.project_id
    deleted = await kitchen_service.delete_design(db, design_id)
    if not deleted:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="厨房设计不存在")
    await ws_manager.broadcast_to_project(project_id, "kitchen.design_deleted", {"id": design_id})

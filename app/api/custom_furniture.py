"""F27 定制家具设计器 API"""

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models.user import User
from app.models.project import Project
from app.models.custom_furniture import CustomFurnitureDesign
from app.auth import get_current_user
from app.schemas.custom_furniture import (
    CustomFurnitureDesignCreate,
    CustomFurnitureDesignResponse,
    FurnitureModuleCreate,
    FurnitureModuleResponse,
    FurnitureBOMResponse,
    PanelComputeResult,
    PriceEstimateResult,
    ValidationResult,
)
from app.services import custom_furniture_service as svc
from app.ws import ws_manager

router = APIRouter(prefix="/custom-furniture", tags=["定制家具"])


async def _verify_project_owner(db: AsyncSession, project_id: str, user: User) -> Project:
    """校验当前用户是项目所有者（admin 豁免），否则抛 403/404"""
    project = await db.get(Project, project_id)
    if not project:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="项目不存在")
    if user.role != "admin" and project.owner_id != user.id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="无权访问该项目")
    return project


async def _verify_design_owner(db: AsyncSession, design_id: str, user: User) -> CustomFurnitureDesign:
    """校验设计存在且其所属项目归当前用户所有（admin 豁免），否则抛 403/404"""
    design = await svc.get_design(db, design_id)
    if not design:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="设计不存在")
    await _verify_project_owner(db, design.project_id, user)
    return design


# ── 设计 ──


@router.post("/designs", response_model=CustomFurnitureDesignResponse, status_code=status.HTTP_201_CREATED)
async def create_design(
    data: CustomFurnitureDesignCreate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    await _verify_project_owner(db, data.project_id, current_user)
    design = await svc.create_design(db, data.model_dump())
    resp = CustomFurnitureDesignResponse.model_validate(design)
    await ws_manager.broadcast_to_project(design.project_id, "furniture.design.created", resp.model_dump())
    return resp


@router.get("/designs/project/{project_id}", response_model=list[CustomFurnitureDesignResponse])
async def list_designs_by_project(
    project_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    await _verify_project_owner(db, project_id, current_user)
    designs = await svc.list_designs_by_project(db, project_id)
    return [CustomFurnitureDesignResponse.model_validate(d) for d in designs]


@router.get("/designs/{design_id}", response_model=CustomFurnitureDesignResponse)
async def get_design(
    design_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    design = await _verify_design_owner(db, design_id, current_user)
    return CustomFurnitureDesignResponse.model_validate(design)


@router.delete("/designs/{design_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_design(
    design_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    design = await _verify_design_owner(db, design_id, current_user)
    project_id = design.project_id
    deleted = await svc.delete_design(db, design_id)
    if not deleted:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="设计不存在")
    await ws_manager.broadcast_to_project(project_id, "furniture.design.deleted", {"id": design_id})


# ── 参数化设计 ──


@router.post("/designs/{design_id}/parametric", response_model=list[FurnitureModuleResponse])
async def parametric_design(
    design_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    design = await _verify_design_owner(db, design_id, current_user)
    modules = await svc.apply_parametric_design(db, design)
    await ws_manager.broadcast_to_project(
        design.project_id,
        "furniture.design.parametric",
        {"design_id": design_id, "module_count": len(modules)},
    )
    return [FurnitureModuleResponse.model_validate(m) for m in modules]


# ── 模块 ──


@router.post(
    "/designs/{design_id}/modules",
    response_model=FurnitureModuleResponse,
    status_code=status.HTTP_201_CREATED,
)
async def add_module(
    design_id: str,
    data: FurnitureModuleCreate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    design = await _verify_design_owner(db, design_id, current_user)
    module = await svc.add_module(db, design_id, data.model_dump())
    resp = FurnitureModuleResponse.model_validate(module)
    await ws_manager.broadcast_to_project(design.project_id, "furniture.module.added", resp.model_dump())
    return resp


@router.get("/designs/{design_id}/modules", response_model=list[FurnitureModuleResponse])
async def list_modules(
    design_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    await _verify_design_owner(db, design_id, current_user)
    modules = await svc.list_modules(db, design_id)
    return [FurnitureModuleResponse.model_validate(m) for m in modules]


@router.delete("/modules/{module_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_module(
    module_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    deleted, design_id = await svc.delete_module(db, module_id)
    if not deleted:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="模块不存在")
    if design_id:
        try:
            await _verify_design_owner(db, design_id, current_user)
        except HTTPException:
            # 设计可能已删除，仅做广播
            pass
    design = await svc.get_design(db, design_id)
    if design:
        await ws_manager.broadcast_to_project(design.project_id, "furniture.module.deleted", {"id": module_id})


# ── BOM ──


@router.post("/designs/{design_id}/bom", response_model=list[FurnitureBOMResponse])
async def generate_bom(
    design_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    design = await _verify_design_owner(db, design_id, current_user)
    if not design.modules:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="尚未生成模块,请先执行参数化设计")
    boms = await svc.generate_bom(db, design)
    await ws_manager.broadcast_to_project(
        design.project_id,
        "furniture.bom.generated",
        {"design_id": design_id, "bom_count": len(boms), "total_price": design.total_price},
    )
    return [FurnitureBOMResponse.model_validate(b) for b in boms]


@router.get("/designs/{design_id}/bom", response_model=list[FurnitureBOMResponse])
async def get_bom(
    design_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    await _verify_design_owner(db, design_id, current_user)
    boms = await svc.list_boms(db, design_id)
    return [FurnitureBOMResponse.model_validate(b) for b in boms]


# ── 价格估算 ──


@router.get("/designs/{design_id}/price", response_model=PriceEstimateResult)
async def estimate_price(
    design_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    design = await _verify_design_owner(db, design_id, current_user)
    return PriceEstimateResult(**svc.estimate_price(design))


# ── 板材计算 ──


@router.get("/designs/{design_id}/panels", response_model=PanelComputeResult)
async def compute_panels(
    design_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    design = await _verify_design_owner(db, design_id, current_user)
    return PanelComputeResult(**svc.compute_panels(design))


# ── 规格校验 ──


@router.get("/designs/{design_id}/validation", response_model=ValidationResult)
async def validate_spec(
    design_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    design = await _verify_design_owner(db, design_id, current_user)
    return ValidationResult(**svc.validate_furniture_spec(design))

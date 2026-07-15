"""F8-F9 土建模块 API 端点 — 结构属性管理 + 工程量计算"""

from typing import Any

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models.user import User
from app.schemas.structural import (
    LoadBearingWallCreate,
    LoadBearingWallResponse,
    BeamCreate,
    BeamResponse,
    ColumnCreate,
    ColumnResponse,
    FloorSlabCreate,
    FloorSlabResponse,
    FoundationTypeCreate,
    FoundationTypeResponse,
    LoadEstimateCreate,
    LoadEstimateResponse,
    LoadEstimateRequest,
    BayComplianceCreate,
    BayComplianceResponse,
    QuantityCalcCreate,
    QuantityCalcResponse,
    QuantityLineItemCreate,
    QuantityLineItemResponse,
    AutoCalcRequest,
)
from app.auth import get_current_user
from app.rbac import verify_project_access
from app.services import structural_service as svc

router = APIRouter(prefix="/structural", tags=["土建模块"])


# ════════════════════════════════════════════════════════════════
# 承重墙 CRUD
# ════════════════════════════════════════════════════════════════


@router.post("/walls", response_model=LoadBearingWallResponse, status_code=status.HTTP_201_CREATED)
async def create_wall(
    data: LoadBearingWallCreate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """创建承重墙"""
    await verify_project_access(project_id=data.project_id, current_user=current_user, db=db)
    wall = await svc.create_wall(db, data.model_dump())
    return LoadBearingWallResponse.model_validate(wall)


@router.get("/projects/{project_id}/walls", response_model=list[LoadBearingWallResponse])
async def list_walls(
    project_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """列出项目承重墙"""
    await verify_project_access(project_id=project_id, current_user=current_user, db=db)
    walls = await svc.list_walls(db, project_id)
    return [LoadBearingWallResponse.model_validate(w) for w in walls]


@router.get("/walls/{wall_id}", response_model=LoadBearingWallResponse)
async def get_wall(
    wall_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """承重墙详情"""
    wall = await svc.get_wall(db, wall_id)
    if not wall:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="承重墙不存在")
    await verify_project_access(project_id=wall.project_id, current_user=current_user, db=db)
    return LoadBearingWallResponse.model_validate(wall)


@router.put("/walls/{wall_id}", response_model=LoadBearingWallResponse)
async def update_wall(
    wall_id: str,
    data: dict[str, Any],
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """更新承重墙"""
    wall = await svc.get_wall(db, wall_id)
    if not wall:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="承重墙不存在")
    await verify_project_access(project_id=wall.project_id, current_user=current_user, db=db)
    updated = await svc.update_wall(db, wall_id, data)
    return LoadBearingWallResponse.model_validate(updated)


@router.delete("/walls/{wall_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_wall(
    wall_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """删除承重墙"""
    wall = await svc.get_wall(db, wall_id)
    if not wall:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="承重墙不存在")
    await verify_project_access(project_id=wall.project_id, current_user=current_user, db=db)
    await svc.delete_wall(db, wall_id)


# ════════════════════════════════════════════════════════════════
# 梁 CRUD
# ════════════════════════════════════════════════════════════════


@router.post("/beams", response_model=BeamResponse, status_code=status.HTTP_201_CREATED)
async def create_beam(
    data: BeamCreate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """创建梁"""
    await verify_project_access(project_id=data.project_id, current_user=current_user, db=db)
    beam = await svc.create_beam(db, data.model_dump())
    return BeamResponse.model_validate(beam)


@router.get("/projects/{project_id}/beams", response_model=list[BeamResponse])
async def list_beams(
    project_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """列出项目梁"""
    await verify_project_access(project_id=project_id, current_user=current_user, db=db)
    beams = await svc.list_beams(db, project_id)
    return [BeamResponse.model_validate(b) for b in beams]


@router.get("/beams/{beam_id}", response_model=BeamResponse)
async def get_beam(
    beam_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """梁详情"""
    beam = await svc.get_beam(db, beam_id)
    if not beam:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="梁不存在")
    await verify_project_access(project_id=beam.project_id, current_user=current_user, db=db)
    return BeamResponse.model_validate(beam)


@router.put("/beams/{beam_id}", response_model=BeamResponse)
async def update_beam(
    beam_id: str,
    data: dict[str, Any],
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """更新梁"""
    beam = await svc.get_beam(db, beam_id)
    if not beam:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="梁不存在")
    await verify_project_access(project_id=beam.project_id, current_user=current_user, db=db)
    updated = await svc.update_beam(db, beam_id, data)
    return BeamResponse.model_validate(updated)


@router.delete("/beams/{beam_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_beam(
    beam_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """删除梁"""
    beam = await svc.get_beam(db, beam_id)
    if not beam:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="梁不存在")
    await verify_project_access(project_id=beam.project_id, current_user=current_user, db=db)
    await svc.delete_beam(db, beam_id)


# ════════════════════════════════════════════════════════════════
# 柱 CRUD
# ════════════════════════════════════════════════════════════════


@router.post("/columns", response_model=ColumnResponse, status_code=status.HTTP_201_CREATED)
async def create_column(
    data: ColumnCreate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """创建柱"""
    await verify_project_access(project_id=data.project_id, current_user=current_user, db=db)
    col = await svc.create_column(db, data.model_dump())
    return ColumnResponse.model_validate(col)


@router.get("/projects/{project_id}/columns", response_model=list[ColumnResponse])
async def list_columns(
    project_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """列出项目柱"""
    await verify_project_access(project_id=project_id, current_user=current_user, db=db)
    cols = await svc.list_columns(db, project_id)
    return [ColumnResponse.model_validate(c) for c in cols]


@router.get("/columns/{column_id}", response_model=ColumnResponse)
async def get_column(
    column_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """柱详情"""
    col = await svc.get_column(db, column_id)
    if not col:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="柱不存在")
    await verify_project_access(project_id=col.project_id, current_user=current_user, db=db)
    return ColumnResponse.model_validate(col)


@router.put("/columns/{column_id}", response_model=ColumnResponse)
async def update_column(
    column_id: str,
    data: dict[str, Any],
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """更新柱"""
    col = await svc.get_column(db, column_id)
    if not col:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="柱不存在")
    await verify_project_access(project_id=col.project_id, current_user=current_user, db=db)
    updated = await svc.update_column(db, column_id, data)
    return ColumnResponse.model_validate(updated)


@router.delete("/columns/{column_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_column(
    column_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """删除柱"""
    col = await svc.get_column(db, column_id)
    if not col:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="柱不存在")
    await verify_project_access(project_id=col.project_id, current_user=current_user, db=db)
    await svc.delete_column(db, column_id)


# ════════════════════════════════════════════════════════════════
# 楼板 CRUD
# ════════════════════════════════════════════════════════════════


@router.post("/slabs", response_model=FloorSlabResponse, status_code=status.HTTP_201_CREATED)
async def create_slab(
    data: FloorSlabCreate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """创建楼板"""
    await verify_project_access(project_id=data.project_id, current_user=current_user, db=db)
    slab = await svc.create_slab(db, data.model_dump())
    return FloorSlabResponse.model_validate(slab)


@router.get("/projects/{project_id}/slabs", response_model=list[FloorSlabResponse])
async def list_slabs(
    project_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """列出项目楼板"""
    await verify_project_access(project_id=project_id, current_user=current_user, db=db)
    slabs = await svc.list_slabs(db, project_id)
    return [FloorSlabResponse.model_validate(s) for s in slabs]


@router.get("/slabs/{slab_id}", response_model=FloorSlabResponse)
async def get_slab(
    slab_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """楼板详情"""
    slab = await svc.get_slab(db, slab_id)
    if not slab:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="楼板不存在")
    await verify_project_access(project_id=slab.project_id, current_user=current_user, db=db)
    return FloorSlabResponse.model_validate(slab)


@router.put("/slabs/{slab_id}", response_model=FloorSlabResponse)
async def update_slab(
    slab_id: str,
    data: dict[str, Any],
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """更新楼板"""
    slab = await svc.get_slab(db, slab_id)
    if not slab:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="楼板不存在")
    await verify_project_access(project_id=slab.project_id, current_user=current_user, db=db)
    updated = await svc.update_slab(db, slab_id, data)
    return FloorSlabResponse.model_validate(updated)


@router.delete("/slabs/{slab_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_slab(
    slab_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """删除楼板"""
    slab = await svc.get_slab(db, slab_id)
    if not slab:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="楼板不存在")
    await verify_project_access(project_id=slab.project_id, current_user=current_user, db=db)
    await svc.delete_slab(db, slab_id)


# ════════════════════════════════════════════════════════════════
# 基础类型管理
# ════════════════════════════════════════════════════════════════


@router.post("/foundations", response_model=FoundationTypeResponse, status_code=status.HTTP_201_CREATED)
async def create_foundation(
    data: FoundationTypeCreate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """创建基础类型"""
    await verify_project_access(project_id=data.project_id, current_user=current_user, db=db)
    foundation = await svc.create_foundation(db, data.model_dump())
    return FoundationTypeResponse.model_validate(foundation)


@router.get("/projects/{project_id}/foundations", response_model=list[FoundationTypeResponse])
async def list_foundations(
    project_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """列出项目基础类型"""
    await verify_project_access(project_id=project_id, current_user=current_user, db=db)
    foundations = await svc.list_foundations(db, project_id)
    return [FoundationTypeResponse.model_validate(f) for f in foundations]


@router.get("/foundations/{foundation_id}", response_model=FoundationTypeResponse)
async def get_foundation(
    foundation_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """基础类型详情"""
    foundation = await svc.get_foundation(db, foundation_id)
    if not foundation:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="基础类型不存在")
    await verify_project_access(project_id=foundation.project_id, current_user=current_user, db=db)
    return FoundationTypeResponse.model_validate(foundation)


@router.delete("/foundations/{foundation_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_foundation(
    foundation_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """删除基础类型"""
    foundation = await svc.get_foundation(db, foundation_id)
    if not foundation:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="基础类型不存在")
    await verify_project_access(project_id=foundation.project_id, current_user=current_user, db=db)
    await svc.delete_foundation(db, foundation_id)


@router.post("/foundations/{foundation_id}/select", response_model=FoundationTypeResponse)
async def select_foundation(
    foundation_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """选定项目基础方案 (取消其他选定)"""
    foundation = await svc.get_foundation(db, foundation_id)
    if not foundation:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="基础类型不存在")
    await verify_project_access(project_id=foundation.project_id, current_user=current_user, db=db)
    selected = await svc.select_foundation(db, foundation_id)
    return FoundationTypeResponse.model_validate(selected)


@router.post("/foundations/recommend")
async def recommend_foundation(
    soil_type: str = "粘土",
    building_floors: int = 2,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """基础类型推荐 (参考 GB 50007)"""
    result = svc.recommend_foundation(soil_type, building_floors)
    return result


# ════════════════════════════════════════════════════════════════
# 荷载估算
# ════════════════════════════════════════════════════════════════


@router.post("/load-estimates", response_model=LoadEstimateResponse, status_code=status.HTTP_201_CREATED)
async def create_load_estimate(
    data: LoadEstimateCreate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """创建荷载估算"""
    await verify_project_access(project_id=data.project_id, current_user=current_user, db=db)
    estimate = await svc.create_load_estimate(db, data.model_dump())
    return LoadEstimateResponse.model_validate(estimate)


@router.get("/projects/{project_id}/load-estimates", response_model=list[LoadEstimateResponse])
async def list_load_estimates(
    project_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """列出项目荷载估算"""
    await verify_project_access(project_id=project_id, current_user=current_user, db=db)
    estimates = await svc.list_load_estimates(db, project_id)
    return [LoadEstimateResponse.model_validate(e) for e in estimates]


@router.get("/load-estimates/{estimate_id}", response_model=LoadEstimateResponse)
async def get_load_estimate(
    estimate_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """荷载估算详情"""
    estimate = await svc.get_load_estimate(db, estimate_id)
    if not estimate:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="荷载估算不存在")
    await verify_project_access(project_id=estimate.project_id, current_user=current_user, db=db)
    return LoadEstimateResponse.model_validate(estimate)


@router.delete("/load-estimates/{estimate_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_load_estimate(
    estimate_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """删除荷载估算"""
    estimate = await svc.get_load_estimate(db, estimate_id)
    if not estimate:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="荷载估算不存在")
    await verify_project_access(project_id=estimate.project_id, current_user=current_user, db=db)
    await svc.delete_load_estimate(db, estimate_id)


@router.post("/load-estimates/compute")
async def compute_load_estimates(
    data: LoadEstimateRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """自动计算荷载估算 (参考 GB 50009)"""
    result = svc.compute_load_estimates(
        usage=data.usage,
        area_m2=data.area_m2,
        floor_level=data.floor_level,
        include_seismic=data.include_seismic,
    )
    return result


# ════════════════════════════════════════════════════════════════
# 开间/进深/层高合规检查
# ════════════════════════════════════════════════════════════════


@router.post("/compliance", response_model=BayComplianceResponse, status_code=status.HTTP_201_CREATED)
async def create_compliance_check(
    data: BayComplianceCreate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """创建合规检查 (参考 GB 50096-2011)"""
    await verify_project_access(project_id=data.project_id, current_user=current_user, db=db)
    compliance = await svc.create_compliance_check(db, data.model_dump())
    return BayComplianceResponse.model_validate(compliance)


@router.get("/projects/{project_id}/compliance", response_model=list[BayComplianceResponse])
async def list_compliance(
    project_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """列出项目合规检查"""
    await verify_project_access(project_id=project_id, current_user=current_user, db=db)
    checks = await svc.list_compliance(db, project_id)
    return [BayComplianceResponse.model_validate(c) for c in checks]


@router.get("/compliance/{compliance_id}", response_model=BayComplianceResponse)
async def get_compliance(
    compliance_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """合规检查详情"""
    compliance = await svc.get_compliance(db, compliance_id)
    if not compliance:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="合规检查不存在")
    await verify_project_access(project_id=compliance.project_id, current_user=current_user, db=db)
    return BayComplianceResponse.model_validate(compliance)


@router.delete("/compliance/{compliance_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_compliance(
    compliance_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """删除合规检查"""
    compliance = await svc.get_compliance(db, compliance_id)
    if not compliance:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="合规检查不存在")
    await verify_project_access(project_id=compliance.project_id, current_user=current_user, db=db)
    await svc.delete_compliance(db, compliance_id)


# ════════════════════════════════════════════════════════════════
# 工程量自动计算
# ════════════════════════════════════════════════════════════════


@router.post("/quantity-calcs", response_model=QuantityCalcResponse, status_code=status.HTTP_201_CREATED)
async def create_quantity_calc(
    data: QuantityCalcCreate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """创建工程量计算"""
    await verify_project_access(project_id=data.project_id, current_user=current_user, db=db)
    calc = await svc.create_quantity_calc(db, data.model_dump())
    return QuantityCalcResponse.model_validate(calc)


@router.get("/projects/{project_id}/quantity-calcs", response_model=list[QuantityCalcResponse])
async def list_quantity_calcs(
    project_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """列出项目工程量计算"""
    await verify_project_access(project_id=project_id, current_user=current_user, db=db)
    calcs = await svc.list_quantity_calcs(db, project_id)
    return [QuantityCalcResponse.model_validate(c) for c in calcs]


@router.get("/quantity-calcs/{calc_id}", response_model=QuantityCalcResponse)
async def get_quantity_calc(
    calc_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """工程量计算详情 (含明细)"""
    calc = await svc.get_quantity_calc(db, calc_id)
    if not calc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="工程量计算不存在")
    await verify_project_access(project_id=calc.project_id, current_user=current_user, db=db)
    return QuantityCalcResponse.model_validate(calc)


@router.delete("/quantity-calcs/{calc_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_quantity_calc(
    calc_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """删除工程量计算"""
    calc = await svc.get_quantity_calc(db, calc_id)
    if not calc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="工程量计算不存在")
    await verify_project_access(project_id=calc.project_id, current_user=current_user, db=db)
    await svc.delete_quantity_calc(db, calc_id)


@router.post("/quantity-calcs/auto-calc")
async def auto_calc_quantity(
    data: AutoCalcRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """自动工程量计算 — 砖砌体/混凝土/钢筋/模板"""
    if data.calc_type == "brickwork":
        result = svc.calc_brickwork(data.wall_length_m, data.wall_height_m, data.wall_thickness_m)
    elif data.calc_type == "concrete":
        result = svc.calc_concrete_rebar(data.slab_area_m2, data.slab_thickness_m, data.concrete_grade)
    elif data.calc_type == "formwork":
        result = svc.calc_formwork(data.formwork_area_m2)
    else:
        # total: 计算全部
        brick = svc.calc_brickwork(data.wall_length_m, data.wall_height_m, data.wall_thickness_m)
        concrete = svc.calc_concrete_rebar(data.slab_area_m2, data.slab_thickness_m, data.concrete_grade)
        formwork = svc.calc_formwork(data.formwork_area_m2)
        result = {
            "calc_type": "total",
            "brickwork": brick,
            "concrete": concrete,
            "formwork": formwork,
            "total_material_cost": round(
                brick["total_material_cost"]
                + concrete["total_material_cost"]
                + formwork["total_formwork_cost"],
                2,
            ),
        }
    return result


@router.post(
    "/quantity-calcs/{calc_id}/line-items",
    response_model=QuantityLineItemResponse,
    status_code=status.HTTP_201_CREATED,
)
async def add_line_item(
    calc_id: str,
    data: QuantityLineItemCreate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """添加工程量明细"""
    calc = await svc.get_quantity_calc(db, calc_id)
    if not calc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="工程量计算不存在")
    await verify_project_access(project_id=calc.project_id, current_user=current_user, db=db)
    item_data = data.model_dump()
    item_data["calculation_id"] = calc_id
    item = await svc.add_line_item(db, item_data)
    return QuantityLineItemResponse.model_validate(item)


@router.delete("/quantity-calcs/line-items/{item_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_line_item(
    item_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """删除工程量明细"""
    deleted = await svc.delete_line_item(db, item_id)
    if not deleted:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="工程量明细不存在")

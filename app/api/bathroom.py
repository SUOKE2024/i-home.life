"""F17 卫生间设计器 API 端点"""

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models.user import User
from app.schemas.bathroom import (
    BathroomDesignCreate,
    BathroomDesignResponse,
    BathroomFixtureCreate,
    BathroomFixtureResponse,
)
from app.auth import get_current_user
from app.rbac import verify_project_access
from app.services import bathroom_service
from app.ws import ws_manager

router = APIRouter(prefix="/bathroom", tags=["卫生间设计器"])


@router.post("/designs", response_model=BathroomDesignResponse, status_code=status.HTTP_201_CREATED)
async def create_design(
    data: BathroomDesignCreate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """创建卫生间设计"""
    await verify_project_access(project_id=data.project_id, current_user=current_user, db=db)
    design = await bathroom_service.create_design(db, data.model_dump())
    resp = BathroomDesignResponse.model_validate(design)
    await ws_manager.broadcast_to_project(design.project_id, "bathroom.design_created", resp.model_dump())
    return resp


@router.get("/designs/project/{project_id}", response_model=list[BathroomDesignResponse])
async def list_designs(
    project_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """列出项目卫生间设计"""
    await verify_project_access(project_id=project_id, current_user=current_user, db=db)
    designs = await bathroom_service.list_designs(db, project_id)
    return [BathroomDesignResponse.model_validate(d) for d in designs]


@router.get("/designs/{design_id}", response_model=BathroomDesignResponse)
async def get_design(
    design_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """卫生间设计详情"""
    design = await bathroom_service.get_design(db, design_id)
    if not design:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="卫生间设计不存在")
    await verify_project_access(project_id=design.project_id, current_user=current_user, db=db)
    return BathroomDesignResponse.model_validate(design)


@router.post("/designs/{design_id}/auto-layout")
async def auto_layout(
    design_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """自动布局 — 根据布局类型生成卫浴排布"""
    design = await bathroom_service.get_design(db, design_id)
    if not design:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="卫生间设计不存在")
    await verify_project_access(project_id=design.project_id, current_user=current_user, db=db)

    fixtures_data = bathroom_service.generate_bathroom_layout(design)

    created = []
    for fix_data in fixtures_data:
        fix_data["design_id"] = design_id
        fixture = await bathroom_service.add_fixture(db, fix_data)
        created.append(BathroomFixtureResponse.model_validate(fixture))

    await ws_manager.broadcast_to_project(
        design.project_id,
        "bathroom.auto_layout_completed",
        {"design_id": design_id, "fixture_count": len(created)},
    )
    return {
        "design_id": design_id,
        "layout_type": design.layout_type,
        "fixtures": created,
        "total": len(created),
    }


@router.get("/designs/{design_id}/drain")
async def compute_drain(
    design_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """地漏坡度计算"""
    design = await bathroom_service.get_design(db, design_id)
    if not design:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="卫生间设计不存在")
    await verify_project_access(project_id=design.project_id, current_user=current_user, db=db)
    result = bathroom_service.compute_drain_slope(design)
    return {"design_id": design_id, **result}


@router.get("/designs/{design_id}/waterproof")
async def validate_waterproof(
    design_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """防水规范校验"""
    design = await bathroom_service.get_design(db, design_id)
    if not design:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="卫生间设计不存在")
    await verify_project_access(project_id=design.project_id, current_user=current_user, db=db)
    result = bathroom_service.validate_waterproof(design)
    return {"design_id": design_id, **result}


@router.get("/designs/{design_id}/ventilation")
async def analyze_ventilation(
    design_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """通风分析"""
    design = await bathroom_service.get_design(db, design_id)
    if not design:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="卫生间设计不存在")
    await verify_project_access(project_id=design.project_id, current_user=current_user, db=db)
    result = bathroom_service.analyze_ventilation(design)
    return {"design_id": design_id, **result}


@router.post(
    "/designs/{design_id}/fixtures",
    response_model=BathroomFixtureResponse,
    status_code=status.HTTP_201_CREATED,
)
async def add_fixture(
    design_id: str,
    data: BathroomFixtureCreate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """添加卫浴设备"""
    design = await bathroom_service.get_design(db, design_id)
    if not design:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="卫生间设计不存在")
    await verify_project_access(project_id=design.project_id, current_user=current_user, db=db)
    fix_data = data.model_dump()
    fix_data["design_id"] = design_id
    fixture = await bathroom_service.add_fixture(db, fix_data)
    resp = BathroomFixtureResponse.model_validate(fixture)
    await ws_manager.broadcast_to_project(design.project_id, "bathroom.fixture_added", resp.model_dump())
    return resp


@router.get("/designs/{design_id}/fixtures", response_model=list[BathroomFixtureResponse])
async def list_fixtures(
    design_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """列出卫浴设备"""
    design = await bathroom_service.get_design(db, design_id)
    if not design:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="卫生间设计不存在")
    await verify_project_access(project_id=design.project_id, current_user=current_user, db=db)
    fixtures = await bathroom_service.list_fixtures(db, design_id)
    return [BathroomFixtureResponse.model_validate(f) for f in fixtures]


@router.delete("/fixtures/{fixture_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_fixture(
    fixture_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """删除卫浴设备"""
    # 查找 fixture → design → project 校验归属
    from sqlalchemy import select
    from app.models.bathroom import BathroomFixture
    result = await db.execute(select(BathroomFixture).where(BathroomFixture.id == fixture_id))
    fixture = result.scalar_one_or_none()
    if not fixture:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="卫浴设备不存在")
    design = await bathroom_service.get_design(db, fixture.design_id)
    if design:
        await verify_project_access(project_id=design.project_id, current_user=current_user, db=db)
    deleted = await bathroom_service.delete_fixture(db, fixture_id)
    if not deleted:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="卫浴设备不存在")


@router.delete("/designs/{design_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_design(
    design_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """删除卫生间设计"""
    design = await bathroom_service.get_design(db, design_id)
    if not design:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="卫生间设计不存在")
    project_id = design.project_id
    await verify_project_access(project_id=project_id, current_user=current_user, db=db)
    deleted = await bathroom_service.delete_design(db, design_id)
    if not deleted:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="卫生间设计不存在")
    await ws_manager.broadcast_to_project(project_id, "bathroom.design_deleted", {"id": design_id})

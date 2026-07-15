"""F29/F30 灯光设计器 API 端点"""

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models.user import User
from app.schemas.lighting import (
    LightingSchemeCreate,
    LightingSchemeResponse,
    LightingFixtureCreate,
    LightingFixtureResponse,
    AIDesignRequest,
)
from app.auth import get_current_user
from app.rbac import verify_project_access
from app.services import lighting_service
from app.ws import ws_manager

router = APIRouter(prefix="/lighting", tags=["灯光设计器"])


@router.post("/schemes", response_model=LightingSchemeResponse, status_code=status.HTTP_201_CREATED)
async def create_scheme(
    data: LightingSchemeCreate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """创建灯光方案"""
    await verify_project_access(project_id=data.project_id, current_user=current_user, db=db)
    scheme = await lighting_service.create_scheme(db, data.model_dump())
    resp = LightingSchemeResponse.model_validate(scheme)
    await ws_manager.broadcast_to_project(scheme.project_id, "lighting.scheme_created", resp.model_dump())
    return resp


@router.get("/schemes/project/{project_id}", response_model=list[LightingSchemeResponse])
async def list_schemes(
    project_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """列出项目灯光方案"""
    await verify_project_access(project_id=project_id, current_user=current_user, db=db)
    schemes = await lighting_service.list_schemes(db, project_id)
    return [LightingSchemeResponse.model_validate(s) for s in schemes]


@router.get("/schemes/{scheme_id}", response_model=LightingSchemeResponse)
async def get_scheme(
    scheme_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """灯光方案详情"""
    scheme = await lighting_service.get_scheme(db, scheme_id)
    if not scheme:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="灯光方案不存在")
    await verify_project_access(project_id=scheme.project_id, current_user=current_user, db=db)
    return LightingSchemeResponse.model_validate(scheme)


@router.post("/schemes/{scheme_id}/ai-design", response_model=LightingSchemeResponse)
async def ai_design(
    scheme_id: str,
    request: AIDesignRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """AI 自动灯光设计 (调用 generate_ai_scheme 规则引擎)"""
    scheme = await lighting_service.get_scheme(db, scheme_id)
    if not scheme:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="灯光方案不存在")
    await verify_project_access(project_id=scheme.project_id, current_user=current_user, db=db)

    # 调用 AI 方案生成
    ai_result = lighting_service.generate_ai_scheme(
        project_id=scheme.project_id,
        room_name=scheme.room_name,
        room_area=scheme.room_area,
        room_type=request.room_type,
        style=request.style,
    )

    # 更新方案
    update_data = {
        "scheme_type": ai_result["scheme_type"],
        "color_temp_k": ai_result["color_temp_k"],
        "cri": ai_result["cri"],
        "ugpr": ai_result["ugpr"],
        "total_lumens": ai_result["total_lumens"],
        "total_power_w": ai_result["total_power_w"],
        "notes": ai_result["notes"],
    }
    updated = await lighting_service.update_scheme(db, scheme_id, update_data)
    if not updated:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="方案更新失败")

    # 创建 AI 推荐的灯具
    for fixture_data in ai_result["fixtures"]:
        fixture_data["scheme_id"] = scheme_id
        await lighting_service.add_fixture(db, fixture_data)

    # 重新加载方案 (含灯具)
    final_scheme = await lighting_service.get_scheme(db, scheme_id)
    resp = LightingSchemeResponse.model_validate(final_scheme)
    await ws_manager.broadcast_to_project(scheme.project_id, "lighting.ai_design_completed", resp.model_dump())
    return resp


@router.post(
    "/schemes/{scheme_id}/fixtures",
    response_model=LightingFixtureResponse,
    status_code=status.HTTP_201_CREATED,
)
async def add_fixture(
    scheme_id: str,
    data: LightingFixtureCreate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """添加灯具"""
    scheme = await lighting_service.get_scheme(db, scheme_id)
    if not scheme:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="灯光方案不存在")
    await verify_project_access(project_id=scheme.project_id, current_user=current_user, db=db)
    fixture_data = data.model_dump()
    fixture_data["scheme_id"] = scheme_id
    fixture = await lighting_service.add_fixture(db, fixture_data)
    resp = LightingFixtureResponse.model_validate(fixture)
    await ws_manager.broadcast_to_project(scheme.project_id, "lighting.fixture_added", resp.model_dump())
    return resp


@router.get("/schemes/{scheme_id}/fixtures", response_model=list[LightingFixtureResponse])
async def list_fixtures(
    scheme_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """列出灯具"""
    scheme = await lighting_service.get_scheme(db, scheme_id)
    if not scheme:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="灯光方案不存在")
    await verify_project_access(project_id=scheme.project_id, current_user=current_user, db=db)
    fixtures = await lighting_service.list_fixtures(db, scheme_id)
    return [LightingFixtureResponse.model_validate(f) for f in fixtures]


@router.delete("/fixtures/{fixture_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_fixture(
    fixture_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """删除灯具"""
    from sqlalchemy import select
    from app.models.lighting import LightingFixture
    fixture_result = await db.execute(select(LightingFixture).where(LightingFixture.id == fixture_id))
    fixture = fixture_result.scalar_one_or_none()
    if not fixture:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="灯具不存在")
    scheme = await lighting_service.get_scheme(db, fixture.scheme_id)
    if scheme:
        await verify_project_access(project_id=scheme.project_id, current_user=current_user, db=db)
    deleted = await lighting_service.delete_fixture(db, fixture_id)
    if not deleted:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="灯具不存在")


@router.get("/schemes/{scheme_id}/illuminance")
async def compute_illuminance(
    scheme_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """照度计算结果"""
    scheme = await lighting_service.get_scheme(db, scheme_id)
    if not scheme:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="灯光方案不存在")
    await verify_project_access(project_id=scheme.project_id, current_user=current_user, db=db)
    fixtures = await lighting_service.list_fixtures(db, scheme_id)
    result = lighting_service.compute_illuminance(scheme.room_area, scheme.ceiling_height, fixtures)
    return {
        "scheme_id": scheme_id,
        "room_area": scheme.room_area,
        "ceiling_height": scheme.ceiling_height,
        **result,
    }


@router.delete("/schemes/{scheme_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_scheme(
    scheme_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """删除灯光方案"""
    scheme = await lighting_service.get_scheme(db, scheme_id)
    if not scheme:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="灯光方案不存在")
    await verify_project_access(project_id=scheme.project_id, current_user=current_user, db=db)
    project_id = scheme.project_id
    deleted = await lighting_service.delete_scheme(db, scheme_id)
    if not deleted:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="灯光方案不存在")
    await ws_manager.broadcast_to_project(project_id, "lighting.scheme_deleted", {"id": scheme_id})

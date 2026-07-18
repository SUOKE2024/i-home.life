"""F21 硬装模块 API 端点"""

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models.project import Project
from app.models.user import User
from app.schemas.hard_decoration import (
    HardDecorationSchemeCreate,
    HardDecorationSchemeResponse,
    FloorPlanCreate,
    FloorPlanResponse,
    WallFinishCreate,
    WallFinishResponse,
    CeilingDesignCreate,
    CeilingDesignResponse,
    TileLayoutRequest,
    PaintUsageRequest,
    CeilingDesignRequest,
)
from app.auth import get_current_user
from app.rbac import verify_project_access, verify_project_collaborator_access
from app.services import hard_decoration_service as svc
from app.ws import ws_manager

router = APIRouter(prefix="/hard-decoration", tags=["硬装模块"])


@router.post("/schemes", response_model=HardDecorationSchemeResponse, status_code=status.HTTP_201_CREATED)
async def create_scheme(
    data: HardDecorationSchemeCreate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """创建硬装方案"""
    project = await db.get(Project, data.project_id)
    if not project or project.owner_id != current_user.id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="无权访问该项目")
    scheme = await svc.create_scheme(db, data.model_dump())
    resp = HardDecorationSchemeResponse.model_validate(scheme)
    await ws_manager.broadcast_to_project(scheme.project_id, "hard_decoration.scheme_created", resp.model_dump())
    return resp


@router.get("/schemes/project/{project_id}", response_model=list[HardDecorationSchemeResponse])
async def list_schemes(
    project_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """列出项目硬装方案（F40 协作：允许 designer/contractor/supplier 查看）"""
    await verify_project_collaborator_access(project_id=project_id, current_user=current_user, db=db)
    schemes = await svc.list_schemes(db, project_id)
    return [HardDecorationSchemeResponse.model_validate(s) for s in schemes]


@router.get("/schemes/{scheme_id}", response_model=HardDecorationSchemeResponse)
async def get_scheme(
    scheme_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """硬装方案详情（F40 协作：允许 designer/contractor/supplier 查看）"""
    scheme = await svc.get_scheme(db, scheme_id)
    if not scheme:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="硬装方案不存在")
    await verify_project_collaborator_access(project_id=scheme.project_id, current_user=current_user, db=db)
    return HardDecorationSchemeResponse.model_validate(scheme)


@router.post("/schemes/{scheme_id}/tile-layout")
async def tile_layout(
    scheme_id: str,
    data: TileLayoutRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """瓷砖排版"""
    scheme = await svc.get_scheme(db, scheme_id)
    if not scheme:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="硬装方案不存在")
    await verify_project_access(project_id=scheme.project_id, current_user=current_user, db=db)
    result = svc.generate_tile_layout(
        data.room_width, data.room_length, data.tile_width, data.tile_length, data.pattern
    )
    return {"scheme_id": scheme_id, **result}


@router.post("/schemes/{scheme_id}/paint-usage")
async def paint_usage(
    scheme_id: str,
    data: PaintUsageRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """涂料用量计算"""
    scheme = await svc.get_scheme(db, scheme_id)
    if not scheme:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="硬装方案不存在")
    await verify_project_access(project_id=scheme.project_id, current_user=current_user, db=db)
    result = svc.compute_paint_usage(data.wall_area, data.coats, data.coverage_per_l)
    return {"scheme_id": scheme_id, **result}


@router.post("/schemes/{scheme_id}/ceiling-design")
async def ceiling_design(
    scheme_id: str,
    data: CeilingDesignRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """吊顶设计"""
    scheme = await svc.get_scheme(db, scheme_id)
    if not scheme:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="硬装方案不存在")
    await verify_project_access(project_id=scheme.project_id, current_user=current_user, db=db)
    result = svc.design_ceiling(data.room_type, data.height)
    return {"scheme_id": scheme_id, **result}


@router.get("/schemes/{scheme_id}/budget")
async def compute_budget(
    scheme_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """预算汇总"""
    scheme = await svc.get_scheme(db, scheme_id)
    if not scheme:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="硬装方案不存在")
    await verify_project_access(project_id=scheme.project_id, current_user=current_user, db=db)
    result = svc.compute_total_budget(scheme)
    return result


@router.post("/schemes/{scheme_id}/floors", response_model=FloorPlanResponse, status_code=status.HTTP_201_CREATED)
async def add_floor(
    scheme_id: str,
    data: FloorPlanCreate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """添加地面方案"""
    scheme = await svc.get_scheme(db, scheme_id)
    if not scheme:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="硬装方案不存在")
    await verify_project_access(project_id=scheme.project_id, current_user=current_user, db=db)
    floor_data = data.model_dump()
    floor_data["scheme_id"] = scheme_id
    floor = await svc.add_floor(db, floor_data)
    resp = FloorPlanResponse.model_validate(floor)
    await ws_manager.broadcast_to_project(scheme.project_id, "hard_decoration.floor_added", resp.model_dump())
    return resp


@router.get("/schemes/{scheme_id}/floors", response_model=list[FloorPlanResponse])
async def list_floors(
    scheme_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """列出方案的地面方案"""
    scheme = await svc.get_scheme(db, scheme_id)
    if not scheme:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="硬装方案不存在")
    await verify_project_collaborator_access(project_id=scheme.project_id, current_user=current_user, db=db)
    floors = await svc.list_floors(db, scheme_id)
    return [FloorPlanResponse.model_validate(f) for f in floors]


@router.post("/schemes/{scheme_id}/walls", response_model=WallFinishResponse, status_code=status.HTTP_201_CREATED)
async def add_wall(
    scheme_id: str,
    data: WallFinishCreate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """添加墙面方案"""
    scheme = await svc.get_scheme(db, scheme_id)
    if not scheme:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="硬装方案不存在")
    await verify_project_access(project_id=scheme.project_id, current_user=current_user, db=db)
    wall_data = data.model_dump()
    wall_data["scheme_id"] = scheme_id
    wall = await svc.add_wall(db, wall_data)
    resp = WallFinishResponse.model_validate(wall)
    await ws_manager.broadcast_to_project(scheme.project_id, "hard_decoration.wall_added", resp.model_dump())
    return resp


@router.get("/schemes/{scheme_id}/walls", response_model=list[WallFinishResponse])
async def list_walls(
    scheme_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """列出方案的墙面方案"""
    scheme = await svc.get_scheme(db, scheme_id)
    if not scheme:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="硬装方案不存在")
    await verify_project_collaborator_access(project_id=scheme.project_id, current_user=current_user, db=db)
    walls = await svc.list_walls(db, scheme_id)
    return [WallFinishResponse.model_validate(w) for w in walls]


@router.post("/schemes/{scheme_id}/ceilings", response_model=CeilingDesignResponse, status_code=status.HTTP_201_CREATED)
async def add_ceiling(
    scheme_id: str,
    data: CeilingDesignCreate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """添加吊顶方案"""
    scheme = await svc.get_scheme(db, scheme_id)
    if not scheme:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="硬装方案不存在")
    await verify_project_access(project_id=scheme.project_id, current_user=current_user, db=db)
    ceiling_data = data.model_dump()
    ceiling_data["scheme_id"] = scheme_id
    ceiling = await svc.add_ceiling(db, ceiling_data)
    resp = CeilingDesignResponse.model_validate(ceiling)
    await ws_manager.broadcast_to_project(scheme.project_id, "hard_decoration.ceiling_added", resp.model_dump())
    return resp


@router.get("/schemes/{scheme_id}/ceilings", response_model=list[CeilingDesignResponse])
async def list_ceilings(
    scheme_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """列出方案的吊顶方案"""
    scheme = await svc.get_scheme(db, scheme_id)
    if not scheme:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="硬装方案不存在")
    await verify_project_collaborator_access(project_id=scheme.project_id, current_user=current_user, db=db)
    ceilings = await svc.list_ceilings(db, scheme_id)
    return [CeilingDesignResponse.model_validate(c) for c in ceilings]


@router.delete("/schemes/{scheme_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_scheme(
    scheme_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """删除硬装方案"""
    scheme = await svc.get_scheme(db, scheme_id)
    if not scheme:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="硬装方案不存在")
    project = await db.get(Project, scheme.project_id)
    if not project or project.owner_id != current_user.id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="无权访问该项目")
    project_id = scheme.project_id
    deleted = await svc.delete_scheme(db, scheme_id)
    if not deleted:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="硬装方案不存在")
    await ws_manager.broadcast_to_project(project_id, "hard_decoration.scheme_deleted", {"id": scheme_id})

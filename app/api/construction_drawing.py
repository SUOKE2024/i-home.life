"""施工图自动生成路由 — v1.2.0 家装专业性 P4 修复

对标鲁班数字精装（模型即图纸，改模型图纸自动重生成）、酷家乐（模型即是图纸）。
floorplan.data 作 SSOT：几何变 → 图纸自动重生成，无人工干预。
输出 SVG（文本格式，前端可直接渲染或转 PDF，无外部依赖）。

feature flag: settings.construction_drawing_enabled；关闭时返回 503。
越权校验：verify_project_access + verify_project_collaborator_access。
"""

from fastapi import APIRouter, Depends, HTTPException, Query, status
from fastapi.responses import Response
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.user import User
from app.auth import get_current_user
from app.database import get_db
from app.rbac import verify_project_access, verify_project_collaborator_access
from app.services.construction_drawing_service import generate_drawings_for_project
from app.config import get_settings

router = APIRouter(prefix="/construction-drawing", tags=["施工图生成"])


@router.get("/{project_id}/floor-plan")
async def get_floor_plan_drawing(
    project_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
    as_svg: bool = Query(default=False, description="True 返回 image/svg+xml，False 返回 JSON 含 SVG 字符串"),
):
    """生成平面布置图 SVG（模型即图纸）

    含墙体（按厚度双线）、门（弧形开启符号）、窗（双线）、房间标注/面积、比例尺。
    """
    settings = get_settings()
    if not settings.construction_drawing_enabled:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="施工图生成未启用（construction_drawing_enabled=False）",
        )
    # 协作者可查看施工图（designer/contractor/supplier）
    await verify_project_collaborator_access(
        project_id=project_id, current_user=current_user, db=db
    )
    try:
        drawings = await generate_drawings_for_project(db, project_id)
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"无法生成施工图：{e}。请先创建户型方案（floorplan）",
        )
    if as_svg:
        return Response(
            content=drawings.floor_plan_svg,
            media_type="image/svg+xml",
            headers={"Cache-Control": "no-cache, must-revalidate"},
        )
    return {
        "project_id": project_id,
        "floorplan_id": drawings.floorplan_id,
        "floorplan_name": drawings.floorplan_name,
        "drawing_type": "floor_plan",
        "svg": drawings.floor_plan_svg,
        "drawing_version": drawings.drawing_version,
        "element_count": drawings.element_count,
    }


@router.get("/{project_id}/elevation")
async def get_elevation_drawing(
    project_id: str,
    wall_name: str | None = Query(default=None, description="指定墙体名，None 取第一面墙"),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
    as_svg: bool = Query(default=False),
):
    """生成立面图 SVG（按墙面投影：墙体 + 门窗洞口）"""
    settings = get_settings()
    if not settings.construction_drawing_enabled:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="施工图生成未启用（construction_drawing_enabled=False）",
        )
    await verify_project_collaborator_access(
        project_id=project_id, current_user=current_user, db=db
    )
    try:
        drawings = await generate_drawings_for_project(db, project_id, wall_name=wall_name)
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"无法生成立面图：{e}",
        )
    elev = drawings.elevation_svgs[0] if drawings.elevation_svgs else {}
    svg = elev.get("svg", "")
    if as_svg:
        return Response(content=svg, media_type="image/svg+xml")
    return {
        "project_id": project_id,
        "floorplan_id": drawings.floorplan_id,
        "drawing_type": "elevation",
        "wall_name": elev.get("wall_name", ""),
        "svg": svg,
        "drawing_version": drawings.drawing_version,
    }


@router.get("/{project_id}/all")
async def get_all_drawings(
    project_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """生成全套施工图（平面图 + 立面图列表）

    返回 JSON：floor_plan_svg + elevation_svgs[]，前端可一次性加载渲染。
    """
    settings = get_settings()
    if not settings.construction_drawing_enabled:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="施工图生成未启用（construction_drawing_enabled=False）",
        )
    await verify_project_access(project_id=project_id, current_user=current_user, db=db)
    try:
        drawings = await generate_drawings_for_project(db, project_id)
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"无法生成施工图：{e}",
        )
    return {
        "project_id": project_id,
        "floorplan_id": drawings.floorplan_id,
        "floorplan_name": drawings.floorplan_name,
        "floor_plan_svg": drawings.floor_plan_svg,
        "elevation_svgs": drawings.elevation_svgs,
        "drawing_version": drawings.drawing_version,
        "element_count": drawings.element_count,
    }

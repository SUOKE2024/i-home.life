"""施工图自动生成路由 — v1.2.0 家装专业性 P4 修复

对标鲁班数字精装（模型即图纸，改模型图纸自动重生成）、酷家乐（模型即是图纸）。
floorplan.data 作 SSOT：几何变 → 图纸自动重生成，无人工干预。
输出 SVG（文本格式，前端可直接渲染或转 PDF，无外部依赖）。

feature flag: settings.construction_drawing_enabled；关闭时返回 503。
越权校验：verify_project_access + verify_project_collaborator_access。
"""

import json

from fastapi import APIRouter, Depends, HTTPException, Query, status
from fastapi.responses import Response
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.user import User
from app.auth import get_current_user
from app.database import get_db
from app.rbac import verify_project_access, verify_project_collaborator_access
from app.services.construction_drawing_service import (
    generate_drawings_for_project,
    is_pdf_export_available,
    svg_to_dxf,
    svg_to_pdf,
    PDFExportUnavailableError,
)
from app.config import get_settings

router = APIRouter(prefix="/construction-drawing", tags=["施工图生成"])

# 导出支持的图纸类型 → DrawingResult 字段
_EXPORT_DRAWING_TYPES = ("floor-plan", "elevation", "section")
_EXPORT_FORMATS = ("dxf", "pdf")


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


@router.get("/{project_id}/section")
async def get_section_drawing(
    project_id: str,
    section_plane: str | None = Query(
        default=None,
        description="剖切面参数 JSON，如 {\"x\": 2500}（x 坐标 mm）或 {\"line_index\": 0}（取第 N 面墙起点 x）；None 取墙体 bbox 中心",
    ),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
    as_svg: bool = Query(default=False),
):
    """生成剖面图 SVG（沿剖切面竖直切开：墙体剖面填充 + 楼板 + 门窗洞口 + 标高标注）"""
    settings = get_settings()
    if not settings.construction_drawing_enabled:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="施工图生成未启用（construction_drawing_enabled=False）",
        )
    await verify_project_collaborator_access(
        project_id=project_id, current_user=current_user, db=db
    )
    plane: dict | None = None
    if section_plane:
        try:
            plane = json.loads(section_plane)
        except json.JSONDecodeError:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
                detail="section_plane 必须是合法 JSON 对象，如 {\"x\": 2500} 或 {\"line_index\": 0}",
            )
        if not isinstance(plane, dict):
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
                detail="section_plane 必须是 JSON 对象，如 {\"x\": 2500}",
            )
    try:
        drawings = await generate_drawings_for_project(db, project_id, section_plane=plane)
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"无法生成剖面图：{e}",
        )
    if as_svg:
        return Response(content=drawings.section_svg, media_type="image/svg+xml")
    return {
        "project_id": project_id,
        "floorplan_id": drawings.floorplan_id,
        "drawing_type": "section",
        "section_plane": plane,
        "svg": drawings.section_svg,
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
        # v1.3.0 P4: MEP 水电图叠加（construction_drawing_mep_enabled 关闭时为空串）
        "mep_overlay_svg": drawings.mep_overlay_svg,
        # P4: 剖面图（沿剖切面竖直切开；剖切面默认取墙体 bbox 中心）
        "section_svg": drawings.section_svg,
    }


@router.get("/{project_id}/{drawing_type}/export")
async def export_drawing(
    project_id: str,
    drawing_type: str,
    format: str = Query(default="dxf", description="导出格式：dxf（手写 DXF 文本，无依赖）或 pdf（依赖 reportlab/fpdf）"),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """导出施工图为 DXF / PDF（基于现有 SVG 几何转换）

    - DXF：手写 DXF AC1015 文本（LINE/LWPOLYLINE 实体），无外部依赖，engine=svg_to_dxf
    - PDF：依赖 reportlab/fpdf；依赖缺失时 501 诚实标注（禁止伪导出）
    诚实标注：响应头 X-Drawing-Format / X-Drawing-Engine 标明导出格式与转换引擎。
    """
    settings = get_settings()
    if not settings.construction_drawing_enabled:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="施工图生成未启用（construction_drawing_enabled=False）",
        )
    if drawing_type not in _EXPORT_DRAWING_TYPES:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail=f"不支持的图纸类型：{drawing_type}（支持 {'/'.join(_EXPORT_DRAWING_TYPES)}）",
        )
    if format not in _EXPORT_FORMATS:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail=f"不支持的导出格式：{format}（支持 {'/'.join(_EXPORT_FORMATS)}）",
        )
    await verify_project_collaborator_access(
        project_id=project_id, current_user=current_user, db=db
    )
    try:
        drawings = await generate_drawings_for_project(db, project_id)
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"无法导出施工图：{e}",
        )
    if drawing_type == "floor-plan":
        svg = drawings.floor_plan_svg
    elif drawing_type == "elevation":
        svg = drawings.elevation_svgs[0]["svg"] if drawings.elevation_svgs else ""
    else:
        svg = drawings.section_svg
    if not svg or "<svg" not in svg:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="无法导出：图纸生成数据为空（请先创建有效 floorplan）",
        )

    if format == "dxf":
        content = svg_to_dxf(svg, drawing_type)
        return Response(
            content=content,
            media_type="application/dxf",
            headers={
                "X-Drawing-Format": "dxf",
                "X-Drawing-Engine": "svg_to_dxf",
                "Content-Disposition": f'attachment; filename="{drawing_type}.dxf"',
            },
        )
    # PDF：依赖 reportlab/fpdf；缺失 → 501 诚实标注（禁止伪导出）
    if not is_pdf_export_available():
        raise HTTPException(
            status_code=status.HTTP_501_NOT_IMPLEMENTED,
            detail="PDF 导出依赖未安装（reportlab/fpdf 均不可用），当前仅支持 DXF 导出。请安装 reportlab 或 fpdf 后重试。",
        )
    try:
        data = svg_to_pdf(svg, drawing_type)
    except PDFExportUnavailableError as e:
        raise HTTPException(
            status_code=status.HTTP_501_NOT_IMPLEMENTED,
            detail=f"PDF 导出不可用：{e}",
        )
    return Response(
        content=data,
        media_type="application/pdf",
        headers={
            "X-Drawing-Format": "pdf",
            "X-Drawing-Engine": "svg_to_pdf",
            "Content-Disposition": f'attachment; filename="{drawing_type}.pdf"',
        },
    )

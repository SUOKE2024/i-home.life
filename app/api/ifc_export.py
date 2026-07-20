"""BIM IFC 导出 API 端点 — 结构 / 设计方案导出为 IFC 文件下载"""

import asyncio
import os
import logging

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import FileResponse
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models.user import User
from app.models.floorplan import FloorPlan
from app.schemas.ifc_export import IFCExportRequest
from app.auth import get_current_user
from app.rbac import verify_project_access
from app.services.ifc_export_service import (
    export_structural_to_ifc,
    export_design_to_ifc,
    IFCExportError,
    _IFCOPENSHELL_AVAILABLE,
)

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/bim/export", tags=["BIM IFC 导出"])


@router.post(
    "/structural/{project_id}",
    summary="导出结构数据为 IFC",
    description="将项目的承重墙、梁、柱、楼板结构数据导出为 IFC4 格式文件",
)
async def export_structural_ifc(
    project_id: str,
    request: IFCExportRequest = Depends(lambda: IFCExportRequest()),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """从 structural 模型导出 IFC 文件"""
    project = await verify_project_access(
        project_id=project_id, current_user=current_user, db=db
    )

    if not _IFCOPENSHELL_AVAILABLE:
        raise HTTPException(
            status_code=status.HTTP_501_NOT_IMPLEMENTED,
            detail="IFC 导出需要安装 ifcopenshell。请运行: pip install ifcopenshell>=0.7.0",
        )

    try:
        filepath = await asyncio.to_thread(
            export_structural_to_ifc, project_id, db
        )
    except IFCExportError as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e),
        )

    file_size = os.path.getsize(filepath)
    filename = f"{project.name.replace(' ', '_')}_structural.ifc"

    # 清理临时文件（响应后删除）
    async def cleanup():
        try:
            os.unlink(filepath)
        except OSError:
            pass

    return FileResponse(
        path=filepath,
        filename=filename,
        media_type="application/x-ifc",
        background=cleanup,
        headers={
            "Content-Disposition": f'attachment; filename="{filename}"',
            "X-File-Size": str(file_size),
        },
    )


@router.post(
    "/design/{plan_id}",
    summary="导出设计方案为 IFC",
    description="将户型设计方案（墙体、门窗）导出为 IFC4 格式文件",
)
async def export_design_ifc(
    plan_id: str,
    request: IFCExportRequest = Depends(lambda: IFCExportRequest()),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """从 FloorPlan 设计数据导出 IFC 文件"""
    if not _IFCOPENSHELL_AVAILABLE:
        raise HTTPException(
            status_code=status.HTTP_501_NOT_IMPLEMENTED,
            detail="IFC 导出需要安装 ifcopenshell。请运行: pip install ifcopenshell>=0.7.0",
        )

    # 查询 FloorPlan
    result = await db.execute(select(FloorPlan).where(FloorPlan.id == plan_id))
    plan = result.scalar_one_or_none()
    if not plan:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="设计方案不存在",
        )

    # 验证项目权限
    await verify_project_access(
        project_id=plan.project_id, current_user=current_user, db=db
    )

    plan_dict = {
        "id": plan.id,
        "name": plan.name,
        "project_id": plan.project_id,
        "data": plan.data,
        "wall_height": plan.wall_height,
    }

    try:
        filepath = await asyncio.to_thread(export_design_to_ifc, plan_dict)
    except IFCExportError as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e),
        )

    file_size = os.path.getsize(filepath)
    filename = f"{plan.name.replace(' ', '_')}_design.ifc"

    async def cleanup():
        try:
            os.unlink(filepath)
        except OSError:
            pass

    return FileResponse(
        path=filepath,
        filename=filename,
        media_type="application/x-ifc",
        background=cleanup,
        headers={
            "Content-Disposition": f'attachment; filename="{filename}"',
            "X-File-Size": str(file_size),
        },
    )

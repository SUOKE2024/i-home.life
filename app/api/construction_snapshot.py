"""施工进度 3DGS 数字存档 API（评估报告 2026-09-12 P3）

端点:
- POST /api/construction/projects/{project_id}/snapshots  上传施工节点 3DGS 快照（multipart）
- GET  /api/construction/projects/{project_id}/snapshots   施工时间线列表（按拍摄时间倒序）
- GET  /api/construction/snapshots/{snapshot_id}           单条快照详情

用途：施工节点实景存档（竣工验收比对 + 业主远程查看进度 + settlement 存证）。
复用 P0 的 .spz/.ply 资产托管 + validate_splat_file 校验。
"""
from fastapi import APIRouter, Depends, File, Form, HTTPException, Query, UploadFile, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.auth import get_current_user
from app.rbac import verify_project_access, verify_project_collaborator_access
from app.models.user import User
from app.services import file_service
from app.services import construction_snapshot_service as snap_svc
from app.services import vr_panorama_service

router = APIRouter(prefix="/construction", tags=["施工存档"])


def _snapshot_response(s) -> dict:
    return {
        "id": s.id,
        "project_id": s.project_id,
        "task_id": s.task_id,
        "stage": s.stage,
        "room_name": s.room_name,
        "splat_url": s.splat_url,
        "thumbnail_url": s.thumbnail_url,
        "notes": s.notes,
        "captured_at": s.captured_at.isoformat() if s.captured_at else None,
        "created_at": s.created_at.isoformat() if s.created_at else None,
    }


@router.post("/projects/{project_id}/snapshots", status_code=status.HTTP_201_CREATED)
async def upload_snapshot(
    project_id: str,
    stage: str = Form(...),
    task_id: str | None = Form(default=None),
    room_name: str | None = Form(default=None),
    notes: str | None = Form(default=None),
    file: UploadFile = File(...),
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """上传施工节点 3DGS 实景快照（.spz/.ply，multipart）。

    施工方/设计师在关键施工节点对现场实景扫描存档，形成施工时间线。
    stage 取值见 construction_snapshot_service.STAGES（对齐 ConstructionTask.phase）。
    """
    if stage not in snap_svc.STAGES:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"不支持的施工阶段: {stage}，仅支持 {', '.join(snap_svc.STAGES)}",
        )
    contents = await file.read()
    error = vr_panorama_service.validate_splat_file(file.filename or "", contents)
    if error:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=error)
    await verify_project_collaborator_access(project_id=project_id, current_user=user, db=db)

    attachment = await file_service.upload_file(
        db,
        project_id=project_id,
        filename=file.filename or "snapshot.spz",
        file_data=contents,
        content_type="application/octet-stream",
        category="construction_snapshot",
    )
    snapshot = await snap_svc.create_snapshot(
        db,
        project_id=project_id,
        splat_url=f"/api/files/download/{attachment.id}",
        stage=stage,
        task_id=task_id,
        room_name=room_name,
        notes=notes,
    )
    return _snapshot_response(snapshot)


@router.get("/projects/{project_id}/snapshots")
async def list_snapshots(
    project_id: str,
    stage_filter: str | None = Query(default=None),
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """施工时间线列表（按拍摄时间倒序）。"""
    await verify_project_access(project_id=project_id, current_user=user, db=db)
    snapshots = await snap_svc.list_snapshots(db, project_id, stage_filter)
    return [_snapshot_response(s) for s in snapshots]


@router.get("/snapshots/{snapshot_id}")
async def get_snapshot(
    snapshot_id: str,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """单条施工快照详情。"""
    snapshot = await snap_svc.get_snapshot(db, snapshot_id)
    if not snapshot:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="施工快照不存在")
    await verify_project_access(project_id=snapshot.project_id, current_user=user, db=db)
    return _snapshot_response(snapshot)

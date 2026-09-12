"""3DGS 云端重建 API — 采集数据提交云端重建为 .spz/.ply（评估报告 2026-09-12 P1）

端点:
- POST /api/vr/reconstructions                     提交重建任务（照片集/视频/AR 扫描）
- GET  /api/vr/reconstructions/{job_id}            查询重建状态（触发后端轮询）
- GET  /api/vr/reconstructions/project/{project_id} 按项目列重建任务

诚实降级：未配置 gaussian_recon_enabled/backend_url 时 503（ReconUnavailableError）。
"""
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.auth import get_current_user
from app.rbac import verify_project_access, verify_project_collaborator_access
from app.models.user import User
from app.services import gaussian_reconstruction_service as recon_svc
from app.services.gaussian_reconstruction_service import ReconUnavailableError

router = APIRouter(prefix="/vr/reconstructions", tags=["3DGS 云端重建"])


class ReconstructionCreate(BaseModel):
    """提交云端重建任务请求"""

    project_id: str
    room_name: str = Field(..., max_length=100)
    source_type: str = Field(default="photos", description="photos / video / ar_scan")
    source_files: list[str] = Field(default_factory=list, description="源数据 URL 列表")
    floorplan_id: str | None = None
    scan_session_id: str | None = Field(default=None, description="桥接 ar_scan 会话（从 AR 测量数据发起）")


class ReconstructionResponse(BaseModel):
    id: str
    project_id: str
    room_name: str
    floorplan_id: str | None
    scan_session_id: str | None
    source_type: str
    source_files: list[str] = Field(default_factory=list)
    backend_job_id: str | None
    status: str
    splat_url: str | None
    error: str | None
    completed_at: datetime | None
    created_at: datetime

    model_config = {"from_attributes": True}


def _to_response(job) -> ReconstructionResponse:
    return ReconstructionResponse(
        id=job.id,
        project_id=job.project_id,
        room_name=job.room_name,
        floorplan_id=job.floorplan_id,
        scan_session_id=job.scan_session_id,
        source_type=job.source_type,
        source_files=job.source_file_list,
        backend_job_id=job.backend_job_id,
        status=job.status,
        splat_url=job.splat_url,
        error=job.error,
        completed_at=job.completed_at,
        created_at=job.created_at,
    )


@router.post("", response_model=ReconstructionResponse, status_code=status.HTTP_201_CREATED)
async def create_reconstruction(
    body: ReconstructionCreate,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """提交云端重建任务。未配置重建后端时 503（平台不自建 GPU）。"""
    await verify_project_collaborator_access(project_id=body.project_id, current_user=user, db=db)
    if body.source_type not in recon_svc.SOURCE_TYPES:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"不支持的源数据类型: {body.source_type}，仅支持 {', '.join(recon_svc.SOURCE_TYPES)}",
        )
    try:
        job = await recon_svc.submit_reconstruction(
            db,
            project_id=body.project_id,
            room_name=body.room_name,
            source_type=body.source_type,
            source_files=body.source_files,
            floorplan_id=body.floorplan_id,
            scan_session_id=body.scan_session_id,
        )
    except ReconUnavailableError as exc:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=exc.reason)
    return _to_response(job)


@router.get("/project/{project_id}", response_model=list[ReconstructionResponse])
async def list_reconstructions(
    project_id: str,
    status_filter: str | None = None,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """按项目列出重建任务。"""
    await verify_project_access(project_id=project_id, current_user=user, db=db)
    jobs = await recon_svc.list_reconstructions(db, project_id, status_filter)
    return [_to_response(j) for j in jobs]


@router.get("/{job_id}", response_model=ReconstructionResponse)
async def get_reconstruction(
    job_id: str,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """查询重建任务状态（触发一次后端轮询刷新 status/splat_url）。"""
    job = await recon_svc.get_reconstruction(db, job_id)
    if not job:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="重建任务不存在")
    await verify_project_access(project_id=job.project_id, current_user=user, db=db)
    return _to_response(job)

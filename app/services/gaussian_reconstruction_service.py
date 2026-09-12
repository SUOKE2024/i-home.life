"""3DGS 云端重建服务层 — 采集数据提交云端重建为 .spz/.ply（评估报告 2026-09-12 P1）

契约固化（对标 ai_render_service 的接入契约范式）：
- 未配置 gaussian_recon_enabled / gaussian_recon_backend_url 时抛
  ReconUnavailableError（API 层转 503 诚实报错），平台不自建 GPU、不做 2D→3D 重建。
- 配置后走真实云端后端（同步提交 + 查询轮询），后端契约：
    POST {backend_url}/jobs          → {"job_id": str}
    GET  {backend_url}/jobs/{id}     → {"status": str, "splat_url": str|null}
- 源数据类型：photos（照片集）/ video（视频）/ ar_scan（AR 测量原始数据）。
"""
import logging
from datetime import datetime, timezone

try:
    import httpx
except ImportError:  # httpx 可选依赖，缺失时禁用真实后端调用
    httpx = None  # type: ignore

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.models.gaussian_recon import GaussianReconstructionJob

logger = logging.getLogger(__name__)

# 云端重建后端调用超时（提交秒级；重建本身是异步耗时任务，不阻塞）
_RECON_BACKEND_TIMEOUT = 30.0

# 支持的重建源数据类型
SOURCE_TYPES = ("photos", "video", "ar_scan")


class ReconUnavailableError(Exception):
    """云端重建未配置（L3 诚实报错）——API 层捕获后转 HTTP 503。"""

    def __init__(self, reason: str):
        super().__init__(reason)
        self.reason = reason


async def submit_reconstruction(
    db: AsyncSession,
    project_id: str,
    room_name: str,
    source_type: str,
    source_files: list[str],
    floorplan_id: str | None = None,
    scan_session_id: str | None = None,
) -> GaussianReconstructionJob:
    """提交云端重建任务。

    未配置重建后端时抛 ReconUnavailableError（诚实 503）；配置后创建任务记录并
    调用后端提交，成功回填 backend_job_id + processing，失败标 failed + error。
    """
    settings = get_settings()
    if not settings.gaussian_recon_enabled or not settings.gaussian_recon_backend_url:
        raise ReconUnavailableError(
            "云端重建未配置：需设置 gaussian_recon_enabled=True 且 "
            "gaussian_recon_backend_url 指向重建后端（如 XGRIDS LCC Cloud）。"
            "平台不自建 GPU、不做 2D→3D 重建，请改用外部工具采集导出后经 "
            "/api/vr/panoramas/upload-splat 上传。"
        )

    job = GaussianReconstructionJob(
        project_id=project_id,
        room_name=room_name,
        floorplan_id=floorplan_id,
        scan_session_id=scan_session_id,
        source_type=source_type,
    )
    job.source_file_list = source_files
    db.add(job)
    await db.commit()
    await db.refresh(job)

    # 调用云端后端提交（httpx 可选依赖，缺失视同未配置）
    if httpx is None:
        job.status = "failed"
        job.error = "httpx 依赖缺失，无法调用重建后端"
        await db.commit()
        await db.refresh(job)
        return job

    try:
        async with httpx.AsyncClient(timeout=_RECON_BACKEND_TIMEOUT) as client:
            resp = await client.post(
                f"{settings.gaussian_recon_backend_url.rstrip('/')}/jobs",
                json={
                    "project_id": project_id,
                    "room_name": room_name,
                    "source_type": source_type,
                    "source_files": source_files,
                    "floorplan_id": floorplan_id,
                },
            )
            resp.raise_for_status()
            payload = resp.json()
        job.backend_job_id = payload.get("job_id")
        job.status = "processing"
    except Exception as exc:  # noqa: BLE001 — 后端不可达/契约不符时诚实失败
        job.status = "failed"
        job.error = f"重建后端提交失败: {exc}"
        logger.warning("[gaussian_recon] 后端提交失败: %s", exc)

    await db.commit()
    await db.refresh(job)
    return job


async def get_reconstruction(db: AsyncSession, job_id: str) -> GaussianReconstructionJob | None:
    """查询重建任务（触发一次后端状态轮询，刷新 status/splat_url）。"""
    result = await db.execute(
        select(GaussianReconstructionJob).where(GaussianReconstructionJob.id == job_id)
    )
    job = result.scalar_one_or_none()
    if job is None or job.status not in ("processing", "queued") or not job.backend_job_id:
        return job

    settings = get_settings()
    if not settings.gaussian_recon_enabled or not settings.gaussian_recon_backend_url or httpx is None:
        return job

    try:
        async with httpx.AsyncClient(timeout=_RECON_BACKEND_TIMEOUT) as client:
            resp = await client.get(
                f"{settings.gaussian_recon_backend_url.rstrip('/')}/jobs/{job.backend_job_id}"
            )
            resp.raise_for_status()
            payload = resp.json()
        backend_status = payload.get("status")
        if backend_status == "completed":
            job.status = "completed"
            job.splat_url = payload.get("splat_url")
            job.completed_at = datetime.now(timezone.utc)
        elif backend_status == "failed":
            job.status = "failed"
            job.error = payload.get("error") or "云端重建失败"
            job.completed_at = datetime.now(timezone.utc)
        # processing / queued 保持原状态，等待下次轮询
    except Exception as exc:  # noqa: BLE001 — 轮询失败不改变本地状态，诚实保留 processing
        logger.warning("[gaussian_recon] 状态轮询失败: %s", exc)

    await db.commit()
    await db.refresh(job)
    return job


async def list_reconstructions(
    db: AsyncSession, project_id: str, status_filter: str | None = None,
) -> list[GaussianReconstructionJob]:
    """按项目列出重建任务（按创建时间倒序）。"""
    stmt = (
        select(GaussianReconstructionJob)
        .where(GaussianReconstructionJob.project_id == project_id)
        .order_by(GaussianReconstructionJob.created_at.desc())
    )
    if status_filter:
        stmt = stmt.where(GaussianReconstructionJob.status == status_filter)
    result = await db.execute(stmt)
    return list(result.scalars().all())

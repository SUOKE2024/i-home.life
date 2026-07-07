"""视觉表现层 AI 图生图 API — Stable Diffusion / ControlNet 任务管理"""

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.auth import get_current_user
from app.models.user import User
from app.schemas.ai_image import (
    AIImageJobCreate,
    AIImageJobResponse,
    AIImageJobListItem,
    AIImagePresetCreate,
    AIImagePresetResponse,
    ApplyPresetRequest,
    BatchRenderRequest,
)
from app.services import ai_image_service
from app.ws import ws_manager

router = APIRouter(prefix="/ai-image", tags=["AI 图生图"])


# ── 任务 ──


@router.post("/jobs", response_model=AIImageJobResponse, status_code=status.HTTP_201_CREATED)
async def create_job(
    body: AIImageJobCreate,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """创建图生图任务。"""
    # 校验提示词
    if body.prompt:
        is_valid, error = ai_image_service.validate_prompt(body.prompt)
        if not is_valid:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=error)

    data = body.model_dump()
    job = await ai_image_service.create_job(db, data)
    resp = AIImageJobResponse.model_validate(job)
    await ws_manager.broadcast_to_project(
        job.project_id, "ai_image.job.created", resp.model_dump()
    )
    return resp


@router.get("/jobs/project/{project_id}", response_model=list[AIImageJobListItem])
async def list_jobs(
    project_id: str,
    status_filter: str | None = None,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    return await ai_image_service.list_jobs(db, project_id, status_filter)


@router.get("/jobs/{job_id}", response_model=AIImageJobResponse)
async def get_job(
    job_id: str,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    job = await ai_image_service.get_job(db, job_id)
    if not job:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="任务不存在")
    return job


@router.post("/jobs/{job_id}/process", response_model=AIImageJobResponse)
async def process_job(
    job_id: str,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """触发任务处理 (调用 Stable Diffusion / ControlNet API,这里 mock 实现)。"""
    job = await ai_image_service.get_job(db, job_id)
    if not job:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="任务不存在")
    if job.status not in ("queued", "failed"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"当前状态 {job.status} 不允许处理",
        )
    processed = await ai_image_service.process_job(db, job_id)
    if not processed:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="处理失败")
    resp = AIImageJobResponse.model_validate(processed)
    await ws_manager.broadcast_to_project(
        job.project_id, "ai_image.job.completed", resp.model_dump()
    )
    return resp


@router.get("/jobs/{job_id}/status", response_model=dict)
async def get_job_status(
    job_id: str,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """查询任务状态。"""
    job = await ai_image_service.get_job(db, job_id)
    if not job:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="任务不存在")
    return {
        "id": job.id,
        "status": job.status,
        "progress_percent": job.progress_percent,
        "output_image_url": job.output_image_url,
        "error_message": job.error_message,
        "cost_yuan": ai_image_service.compute_cost(job),
    }


@router.delete("/jobs/{job_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_job(
    job_id: str,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    job = await ai_image_service.get_job(db, job_id)
    if not job:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="任务不存在")
    project_id = job.project_id
    deleted = await ai_image_service.delete_job(db, job_id)
    if not deleted:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="任务不存在")
    await ws_manager.broadcast_to_project(
        project_id, "ai_image.job.deleted", {"id": job_id}
    )


# ── 预设模板 ──


@router.get("/presets", response_model=list[AIImagePresetResponse])
async def list_presets(
    category: str | None = None,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """列出预设模板 (按使用次数降序)。"""
    return await ai_image_service.list_presets(db, category)


@router.post("/presets", response_model=AIImagePresetResponse, status_code=status.HTTP_201_CREATED)
async def create_preset(
    body: AIImagePresetCreate,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """创建预设模板。"""
    data = body.model_dump()
    preset = await ai_image_service.create_preset(db, data)
    return preset


@router.get("/presets/{preset_id}", response_model=AIImagePresetResponse)
async def get_preset(
    preset_id: str,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    preset = await ai_image_service.get_preset(db, preset_id)
    if not preset:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="预设模板不存在")
    return preset


# ── 应用预设 / 批量渲染 ──


@router.post("/jobs/apply-preset", response_model=AIImageJobResponse, status_code=status.HTTP_201_CREATED)
async def apply_preset(
    body: ApplyPresetRequest,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """应用预设模板 (body: preset_id, input_image_url, customizations)。"""
    job = await ai_image_service.apply_preset(
        db, body.preset_id, body.input_image_url, body.customizations
    )
    if not job:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="预设模板不存在")
    resp = AIImageJobResponse.model_validate(job)
    await ws_manager.broadcast_to_project(
        job.project_id, "ai_image.job.created", resp.model_dump()
    )
    return resp


@router.post("/jobs/batch", response_model=list[AIImageJobResponse], status_code=status.HTTP_201_CREATED)
async def batch_render(
    body: BatchRenderRequest,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """批量渲染 (body: project_id, floorplan_id, preset_ids)。"""
    jobs = await ai_image_service.batch_render(
        db, body.project_id, body.floorplan_id, body.preset_ids, body.input_image_url
    )
    if not jobs:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="未找到任何有效的预设模板",
        )
    await ws_manager.broadcast_to_project(
        body.project_id,
        "ai_image.batch.queued",
        {"project_id": body.project_id, "job_count": len(jobs)},
    )
    return jobs

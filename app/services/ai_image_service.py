"""视觉表现层 AI 图生图服务层 — Stable Diffusion / ControlNet 任务管理

核心能力:
1. 任务 CRUD 与处理 (mock 实现:生成 placeholder URL,记录 progress)
2. 预设模板应用 (一键应用现代简约/北欧/新中式等风格)
3. 批量渲染 (一个户型应用多个风格预设)
4. 成本计算 (按 steps × 0.01 元 估算)
5. 提示词校验 (过滤敏感词,长度限制)
"""

import json
import uuid
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.ai_image import AIImageJob, AIImagePreset


# ──────────────────────────────────────────────────────────────
# 提示词校验
# ──────────────────────────────────────────────────────────────

# 敏感词黑名单 (生产环境应使用专业敏感词服务)
SENSITIVE_WORDS = {
    "暴力", "色情", "赌博", "毒品", "武器", "政治敏感",
    "violence", "porn", "gamble", "drug", "weapon",
}

# 提示词长度限制
MAX_PROMPT_LENGTH = 2000
MIN_PROMPT_LENGTH = 1


def validate_prompt(prompt: str) -> tuple[bool, str]:
    """提示词校验 (过滤敏感词,长度限制)。

    Returns:
        (is_valid, error_message)
    """
    if not prompt:
        return False, "提示词不能为空"

    if len(prompt) > MAX_PROMPT_LENGTH:
        return False, f"提示词长度超过 {MAX_PROMPT_LENGTH} 字符"

    if len(prompt) < MIN_PROMPT_LENGTH:
        return False, f"提示词长度不足 {MIN_PROMPT_LENGTH} 字符"

    prompt_lower = prompt.lower()
    for word in SENSITIVE_WORDS:
        if word in prompt_lower:
            return False, f"提示词包含敏感词: {word}"

    return True, ""


# ──────────────────────────────────────────────────────────────
# 任务 CRUD
# ──────────────────────────────────────────────────────────────

async def create_job(db: AsyncSession, data: dict) -> AIImageJob:
    """创建图生图任务。"""
    job = AIImageJob(**data)
    db.add(job)
    await db.commit()
    await db.refresh(job)
    return job


async def get_job(db: AsyncSession, job_id: str) -> AIImageJob | None:
    result = await db.execute(select(AIImageJob).where(AIImageJob.id == job_id))
    return result.scalar_one_or_none()


async def list_jobs(
    db: AsyncSession,
    project_id: str,
    status_filter: str | None = None,
) -> list[AIImageJob]:
    stmt = (
        select(AIImageJob)
        .where(AIImageJob.project_id == project_id)
        .order_by(AIImageJob.created_at.desc())
    )
    if status_filter:
        stmt = stmt.where(AIImageJob.status == status_filter)
    result = await db.execute(stmt)
    return list(result.scalars().all())


async def delete_job(db: AsyncSession, job_id: str) -> bool:
    result = await db.execute(select(AIImageJob).where(AIImageJob.id == job_id))
    job = result.scalar_one_or_none()
    if not job:
        return False
    await db.delete(job)
    await db.commit()
    return True


# ──────────────────────────────────────────────────────────────
# 任务处理 (mock 实现)
# ──────────────────────────────────────────────────────────────

def compute_cost(job: AIImageJob) -> float:
    """计算成本 (按 steps × 0.01 元 估算)。

    成本公式: cost = num_inference_steps × 0.01
    例如: 30 steps × 0.01 = 0.30 元

    Args:
        job: AIImageJob 实例
    Returns:
        成本 (元)
    """
    return round(job.num_inference_steps * 0.01, 2)


async def process_job(db: AsyncSession, job_id: str) -> AIImageJob | None:
    """处理图生图任务 (调用 Stable Diffusion / ControlNet API,这里 mock 实现)。

    mock 实现:
    1. 状态流转: queued → processing → completed
    2. 根据 prompt 生成 placeholder URL (cdn.i-home.life/ai/...)
    3. 记录进度和耗时

    实际实现需通过任务队列 (Celery/RQ) 异步调用 SD API,
    并通过 WebSocket 实时推送进度。
    """
    result = await db.execute(select(AIImageJob).where(AIImageJob.id == job_id))
    job = result.scalar_one_or_none()
    if not job:
        return None

    # 1. 进入处理中
    job.status = "processing"
    job.progress_percent = 10.0
    await db.commit()

    # 2. mock 调用 SD/ControlNet API
    # 实际: POST https://api.stability.ai/v2beta/stable-image/generate/sd3
    # mock: 生成 placeholder URL
    render_id = uuid.uuid4().hex[:12]
    output_url = f"https://cdn.i-home.life/ai/{render_id}_output.png"

    # 模拟 progress 流转
    job.progress_percent = 100.0
    job.output_image_url = output_url
    job.status = "completed"
    job.render_duration_sec = int(job.num_inference_steps * 0.5)  # mock: 每 step 0.5s
    job.completed_at = datetime.now(timezone.utc).replace(tzinfo=None)
    await db.commit()
    await db.refresh(job)
    return job


# ──────────────────────────────────────────────────────────────
# 预设模板管理
# ──────────────────────────────────────────────────────────────

async def create_preset(db: AsyncSession, data: dict) -> AIImagePreset:
    """创建预设模板。"""
    default_params = data.pop("default_params", None)
    if isinstance(default_params, dict):
        data["default_params"] = json.dumps(default_params, ensure_ascii=False)

    preset = AIImagePreset(**data)
    db.add(preset)
    await db.commit()
    await db.refresh(preset)
    return preset


async def get_preset(db: AsyncSession, preset_id: str) -> AIImagePreset | None:
    result = await db.execute(select(AIImagePreset).where(AIImagePreset.id == preset_id))
    return result.scalar_one_or_none()


async def list_presets(
    db: AsyncSession,
    category: str | None = None,
    is_public_only: bool = True,
) -> list[AIImagePreset]:
    """列出预设模板 (按使用次数降序)。"""
    stmt = select(AIImagePreset).order_by(AIImagePreset.usage_count.desc())
    if category:
        stmt = stmt.where(AIImagePreset.category == category)
    if is_public_only:
        stmt = stmt.where(AIImagePreset.is_public.is_(True))
    result = await db.execute(stmt)
    return list(result.scalars().all())


async def apply_preset(
    db: AsyncSession,
    preset_id: str,
    project_id: str,
    floorplan_id: str | None = None,
    input_image_url: str = "",
    customizations: dict | None = None,
) -> AIImageJob | None:
    """应用预设模板 — 一键创建图生图任务并触发处理。

    Args:
        preset_id: 预设模板 ID
        project_id: 项目 ID (由调用方校验归属后传入,防止 IDOR)
        floorplan_id: 户型 ID (可选)
        input_image_url: 输入图像 URL
        customizations: 用户自定义参数 (覆盖预设默认参数)
    Returns:
        AIImageJob 实例
    """
    result = await db.execute(select(AIImagePreset).where(AIImagePreset.id == preset_id))
    preset = result.scalar_one_or_none()
    if not preset:
        return None

    # 合并默认参数与自定义参数
    default_params = preset.default_params_dict
    if customizations:
        default_params.update(customizations)

    # 增加预设使用次数
    preset.usage_count = (preset.usage_count or 0) + 1
    await db.commit()

    # 创建任务 — project_id 由调用方显式传入(已校验归属)
    job_data = {
        "project_id": project_id,
        "floorplan_id": floorplan_id or default_params.get("floorplan_id"),
        "job_type": default_params.get("job_type", "style_transfer"),
        "input_image_url": input_image_url,
        "prompt": preset.prompt_template,
        "negative_prompt": preset.negative_prompt_template,
        "model_name": default_params.get("model_name", "stable-diffusion-xl"),
        "controlnet_type": default_params.get("controlnet_type"),
        "controlnet_strength": default_params.get("controlnet_strength", 0.5),
        "guidance_scale": default_params.get("guidance_scale", 7.5),
        "num_inference_steps": default_params.get("num_inference_steps", 30),
        "seed": default_params.get("seed"),
        "status": "queued",
    }
    job = await create_job(db, job_data)
    return job


async def batch_render(
    db: AsyncSession,
    project_id: str,
    floorplan_id: str | None,
    preset_ids: list[str],
    input_image_url: str | None = None,
) -> list[AIImageJob]:
    """批量渲染 — 一个户型应用多个风格预设。

    Args:
        project_id: 项目 ID
        floorplan_id: 户型 ID (可选)
        preset_ids: 预设模板 ID 列表
        input_image_url: 输入图像 URL (若为 None,使用户型缩略图)
    Returns:
        创建的任务列表
    """
    jobs = []
    for preset_id in preset_ids:
        result = await db.execute(select(AIImagePreset).where(AIImagePreset.id == preset_id))
        preset = result.scalar_one_or_none()
        if not preset:
            continue

        # 增加预设使用次数
        preset.usage_count = (preset.usage_count or 0) + 1

        # 创建任务 (不立即处理,留待后续 process_job 触发)
        job_data = {
            "project_id": project_id,
            "floorplan_id": floorplan_id,
            "job_type": "style_transfer",
            "input_image_url": input_image_url,
            "prompt": preset.prompt_template,
            "negative_prompt": preset.negative_prompt_template,
            "model_name": preset.default_params_dict.get("model_name", "stable-diffusion-xl"),
            "controlnet_type": preset.default_params_dict.get("controlnet_type"),
            "controlnet_strength": preset.default_params_dict.get("controlnet_strength", 0.5),
            "guidance_scale": preset.default_params_dict.get("guidance_scale", 7.5),
            "num_inference_steps": preset.default_params_dict.get("num_inference_steps", 30),
            "status": "queued",
        }
        job = AIImageJob(**job_data)
        db.add(job)
        jobs.append(job)

    await db.commit()
    for job in jobs:
        await db.refresh(job)
    return jobs

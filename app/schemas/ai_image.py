"""视觉表现层 AI 图生图 Pydantic 验证模型"""

from datetime import datetime

from pydantic import BaseModel, Field


class AIImageJobCreate(BaseModel):
    """创建图生图任务"""

    project_id: str
    floorplan_id: str | None = None
    job_type: str = Field(default="style_transfer")
    input_image_url: str | None = None
    prompt: str | None = Field(default=None, max_length=2000)
    negative_prompt: str | None = Field(default=None, max_length=1000)
    model_name: str = Field(default="stable-diffusion-xl")
    controlnet_type: str | None = None
    controlnet_strength: float = Field(default=0.5, ge=0.0, le=1.0)
    guidance_scale: float = Field(default=7.5, ge=1.0, le=30.0)
    num_inference_steps: int = Field(default=30, ge=1, le=200)
    seed: int | None = None


class AIImageJobUpdate(BaseModel):
    output_image_url: str | None = None
    status: str | None = None
    progress_percent: float | None = None
    error_message: str | None = None


class AIImageJobResponse(BaseModel):
    id: str
    project_id: str
    floorplan_id: str | None
    job_type: str
    input_image_url: str | None
    output_image_url: str | None
    prompt: str | None
    negative_prompt: str | None
    model_name: str
    controlnet_type: str | None
    controlnet_strength: float
    guidance_scale: float
    num_inference_steps: int
    seed: int | None
    status: str
    progress_percent: float
    error_message: str | None
    render_duration_sec: int
    created_at: datetime
    completed_at: datetime | None

    model_config = {"from_attributes": True}


class AIImageJobListItem(BaseModel):
    id: str
    project_id: str
    job_type: str
    input_image_url: str | None
    output_image_url: str | None
    model_name: str
    status: str
    progress_percent: float
    created_at: datetime

    model_config = {"from_attributes": True}


class AIImagePresetCreate(BaseModel):
    """创建预设模板"""

    name: str = Field(..., max_length=100)
    category: str = Field(default="style")
    prompt_template: str = Field(..., max_length=2000)
    negative_prompt_template: str | None = Field(default=None, max_length=1000)
    default_params: dict = Field(default_factory=dict)
    preview_image_url: str | None = None
    is_public: bool = True


class AIImagePresetResponse(BaseModel):
    id: str
    name: str
    category: str
    prompt_template: str
    negative_prompt_template: str | None
    default_params: str | None
    preview_image_url: str | None
    usage_count: int
    is_public: bool
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class ApplyPresetRequest(BaseModel):
    """应用预设模板"""

    preset_id: str
    project_id: str
    floorplan_id: str | None = None
    input_image_url: str
    customizations: dict = Field(default_factory=dict)


class BatchRenderRequest(BaseModel):
    """批量渲染"""

    project_id: str
    floorplan_id: str | None = None
    preset_ids: list[str] = Field(..., min_length=1)
    input_image_url: str | None = None

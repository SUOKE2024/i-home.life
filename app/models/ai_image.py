"""视觉表现层 AI 图生图模型 — 图生图任务 + 预设模板

支持多种 job_type: style_transfer / render_enhance / furnish_preview / material_replace / perspective_fix
支持多种 model_name: stable-diffusion-xl / controlnet-canny / controlnet-depth / flux-pro
支持 ControlNet (canny/depth/openpose/mlsd/normal) 控制图像生成。
"""

import json
import uuid
from datetime import datetime

from sqlalchemy import String, DateTime, ForeignKey, func, Text, Float, Integer, Boolean
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class AIImageJob(Base):
    """AI 图生图任务 — 基于 Stable Diffusion / ControlNet 的图像生成任务

    通过 prompt + controlnet 控制输入图像的风格迁移/渲染增强/家具预览/材质替换/透视修正。
    """

    __tablename__ = "ai_image_jobs"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    project_id: Mapped[str] = mapped_column(String(36), ForeignKey("projects.id"), nullable=False, index=True)
    floorplan_id: Mapped[str | None] = mapped_column(String(36), ForeignKey("floor_plans.id"), nullable=True, index=True)
    job_type: Mapped[str] = mapped_column(String(30), nullable=False, default="style_transfer")
    # job_type: style_transfer / render_enhance / furnish_preview / material_replace / perspective_fix
    input_image_url: Mapped[str | None] = mapped_column(String(1000), nullable=True)
    output_image_url: Mapped[str | None] = mapped_column(String(1000), nullable=True)
    prompt: Mapped[str | None] = mapped_column(Text, nullable=True)
    negative_prompt: Mapped[str | None] = mapped_column(Text, nullable=True)
    model_name: Mapped[str] = mapped_column(String(50), nullable=False, default="stable-diffusion-xl")
    # model_name: stable-diffusion-xl / controlnet-canny / controlnet-depth / flux-pro
    controlnet_type: Mapped[str | None] = mapped_column(String(20), nullable=True)
    # controlnet_type: canny / depth / openpose / mlsd / normal
    controlnet_strength: Mapped[float] = mapped_column(Float, nullable=False, default=0.5)
    # controlnet_strength: 0-1,默认 0.5
    guidance_scale: Mapped[float] = mapped_column(Float, nullable=False, default=7.5)
    # guidance_scale: CFG,默认 7.5
    num_inference_steps: Mapped[int] = mapped_column(Integer, nullable=False, default=30)
    # num_inference_steps: 默认 30
    seed: Mapped[int | None] = mapped_column(Integer, nullable=True)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="queued")
    # status: queued / processing / completed / failed
    progress_percent: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    render_duration_sec: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    project = relationship("Project")
    floorplan = relationship("FloorPlan")


class AIImagePreset(Base):
    """AI 图生图预设模板 — 风格化模板,可一键应用到任意输入图像

    内置现代简约/北欧/新中式/法式/工业风/日式/美式 等常见风格预设。
    """

    __tablename__ = "ai_image_presets"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    # name: 现代简约 / 北欧 / 新中式 / 法式 / 工业风 / 日式 / 美式
    category: Mapped[str] = mapped_column(String(30), nullable=False, default="style")
    # category: style / room_type / material
    prompt_template: Mapped[str] = mapped_column(Text, nullable=False)
    negative_prompt_template: Mapped[str | None] = mapped_column(Text, nullable=True)
    default_params: Mapped[str | None] = mapped_column(Text, nullable=True)
    # default_params: JSON {model_name, controlnet_type, guidance_scale, num_inference_steps, ...}
    preview_image_url: Mapped[str | None] = mapped_column(String(1000), nullable=True)
    usage_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    is_public: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    @property
    def default_params_dict(self) -> dict:
        try:
            return json.loads(self.default_params or "{}")
        except (json.JSONDecodeError, TypeError):
            return {}

    @default_params_dict.setter
    def default_params_dict(self, value: dict):
        self.default_params = json.dumps(value, ensure_ascii=False)

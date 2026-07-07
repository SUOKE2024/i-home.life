"""视觉表现层 VR 全景 Pydantic 验证模型"""

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


class HotspotSpec(BaseModel):
    """热点定义"""

    type: str = Field(..., description="热点类型: panorama / floorplan / link / info")
    position: dict = Field(..., description="3D 位置 {x, y, z}")
    label: str = Field(..., max_length=100)
    target_panorama_id: str | None = None
    target_floorplan_id: str | None = None
    url: str | None = None


class InitialViewSpec(BaseModel):
    """初始视角定义"""

    heading: float = Field(default=0.0, ge=0.0, le=360.0)
    pitch: float = Field(default=0.0, ge=-90.0, le=90.0)
    fov: float = Field(default=75.0, ge=10.0, le=170.0)


class VRPanoramaCreate(BaseModel):
    """创建全景图"""

    project_id: str
    floorplan_id: str | None = None
    room_name: str = Field(..., max_length=100)
    panorama_type: str = Field(default="equirectangular")
    resolution: str = Field(default="4K")
    fov: float = Field(default=360.0, ge=10.0, le=360.0)
    initial_view: InitialViewSpec | None = None
    render_quality: str = Field(default="standard")


class VRPanoramaUpdate(BaseModel):
    image_url: str | None = None
    thumbnail_url: str | None = None
    status: str | None = None


class VRPanoramaResponse(BaseModel):
    id: str
    project_id: str
    floorplan_id: str | None
    room_name: str
    panorama_type: str
    image_url: str | None
    thumbnail_url: str | None
    resolution: str
    fov: float
    initial_view: str | None
    hotspots: str | None
    render_quality: str
    file_size_mb: float
    render_duration_sec: int
    status: str
    created_at: datetime
    completed_at: datetime | None

    model_config = {"from_attributes": True}


class VRPanoramaListItem(BaseModel):
    id: str
    project_id: str
    room_name: str
    panorama_type: str
    thumbnail_url: str | None
    resolution: str
    status: str
    created_at: datetime

    model_config = {"from_attributes": True}


class HotspotCreate(BaseModel):
    """添加热点"""

    type: str
    position: dict
    label: str = Field(..., max_length=100)
    target_panorama_id: str | None = None
    target_floorplan_id: str | None = None
    url: str | None = None


class RenderPanoramaRequest(BaseModel):
    """触发渲染"""

    floorplan_data: dict | None = None
    quality: str = Field(default="standard")


class VRSceneCreate(BaseModel):
    """创建 VR 场景"""

    project_id: str
    name: str = Field(..., max_length=200)
    panorama_ids: list[str] = Field(default_factory=list)
    default_panorama_id: str | None = None
    transition_type: str = Field(default="fade")
    bgm_url: str | None = None
    voiceover_url: str | None = None
    notes: str | None = None


class VRSceneUpdate(BaseModel):
    name: str | None = None
    panorama_ids: list[str] | None = None
    default_panorama_id: str | None = None
    transition_type: str | None = None
    bgm_url: str | None = None
    voiceover_url: str | None = None
    status: str | None = None
    notes: str | None = None


class VRSceneResponse(BaseModel):
    id: str
    project_id: str
    name: str
    panorama_ids: str | None
    default_panorama_id: str | None
    transition_type: str
    bgm_url: str | None
    voiceover_url: str | None
    status: str
    notes: str | None
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}

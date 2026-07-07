"""视觉表现层 VR 全景模型 — 全景图 + VR 场景

支持 equirectangular / cubemap 两种全景投影,
支持热点 (Hotspot) 跳转 (房间/户型/外链),支持多全景组合 VR 场景漫游。
"""

import json
import uuid
from datetime import datetime

from sqlalchemy import String, DateTime, ForeignKey, func, Text, Float, Integer, JSON
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class VRPanorama(Base):
    """VR 全景图 — 单个房间的 360° 全景渲染结果

    通过 floorplan_id 关联户型,hotspots (JSON) 存储热点列表,
    每个热点可指向其他 panorama / floorplan / 外部链接。
    """

    __tablename__ = "vr_panoramas"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    project_id: Mapped[str] = mapped_column(String(36), ForeignKey("projects.id"), nullable=False)
    floorplan_id: Mapped[str | None] = mapped_column(String(36), ForeignKey("floor_plans.id"), nullable=True)
    room_name: Mapped[str] = mapped_column(String(100), nullable=False)
    panorama_type: Mapped[str] = mapped_column(String(30), nullable=False, default="equirectangular")
    # panorama_type: equirectangular (等距柱状) / cubemap (立方体贴图)
    image_url: Mapped[str | None] = mapped_column(String(1000), nullable=True)
    thumbnail_url: Mapped[str | None] = mapped_column(String(1000), nullable=True)
    resolution: Mapped[str] = mapped_column(String(10), nullable=False, default="4K")
    # resolution: 4K / 8K
    fov: Mapped[float] = mapped_column(Float, nullable=False, default=360.0)
    # fov: 视野角度,默认 360
    initial_view: Mapped[str | None] = mapped_column(Text, nullable=True)
    # initial_view: JSON {heading, pitch, fov} 初始视角
    hotspots: Mapped[str | None] = mapped_column(Text, nullable=True)
    # hotspots: JSON 热点列表 [{type, position, label, target_panorama_id, target_floorplan_id}]
    render_quality: Mapped[str] = mapped_column(String(20), nullable=False, default="standard")
    # render_quality: draft / standard / high
    file_size_mb: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    render_duration_sec: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="queued")
    # status: queued / rendering / completed / failed
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    completed_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)

    project = relationship("Project")
    floorplan = relationship("FloorPlan")

    @property
    def initial_view_dict(self) -> dict:
        try:
            return json.loads(self.initial_view or "{}")
        except (json.JSONDecodeError, TypeError):
            return {}

    @initial_view_dict.setter
    def initial_view_dict(self, value: dict):
        self.initial_view = json.dumps(value, ensure_ascii=False)

    @property
    def hotspot_list(self) -> list[dict]:
        try:
            return json.loads(self.hotspots or "[]")
        except (json.JSONDecodeError, TypeError):
            return []

    @hotspot_list.setter
    def hotspot_list(self, value: list[dict]):
        self.hotspots = json.dumps(value, ensure_ascii=False)


class VRScene(Base):
    """VR 场景 — 多个全景图按浏览顺序组合,支持漫游

    通过 panorama_ids (JSON 有序列表) 关联多个 VRPanorama,
    通过 transition_type 控制切换过渡效果 (fade / warp / none)。
    """

    __tablename__ = "vr_scenes"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    project_id: Mapped[str] = mapped_column(String(36), ForeignKey("projects.id"), nullable=False)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    panorama_ids: Mapped[str | None] = mapped_column(Text, nullable=True)
    # panorama_ids: JSON 有序列表 (按浏览顺序)
    default_panorama_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    transition_type: Mapped[str] = mapped_column(String(20), nullable=False, default="fade")
    # transition_type: fade / warp / none
    bgm_url: Mapped[str | None] = mapped_column(String(1000), nullable=True)
    voiceover_url: Mapped[str | None] = mapped_column(String(1000), nullable=True)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="active")
    # status: active / archived
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), onupdate=func.now())

    project = relationship("Project")

    @property
    def panorama_id_list(self) -> list[str]:
        try:
            return json.loads(self.panorama_ids or "[]")
        except (json.JSONDecodeError, TypeError):
            return []

    @panorama_id_list.setter
    def panorama_id_list(self, value: list[str]):
        self.panorama_ids = json.dumps(value, ensure_ascii=False)

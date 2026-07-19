import uuid
import json
from datetime import datetime

from sqlalchemy import String, DateTime, ForeignKey, func, Text, Float
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class Survey(Base):
    """测量任务 — 覆盖 LiDAR/手动/视觉/拍照/语音引导 五种测量方式"""
    __tablename__ = "surveys"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    project_id: Mapped[str] = mapped_column(String(36), ForeignKey("projects.id"), nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(200), nullable=False, default="现场测量")
    surveyor: Mapped[str | None] = mapped_column(String(100), nullable=True)       # 测量人员
    # method: manual | lidar | visual | photo | voice_guided
    method: Mapped[str] = mapped_column(String(20), nullable=False, default="manual")
    scene_type: Mapped[str] = mapped_column(String(20), nullable=False, default="indoor")  # indoor | outdoor | balcony
    wall_height: Mapped[float] = mapped_column(Float, default=2.8)                  # 层高(米)
    total_area: Mapped[float] = mapped_column(Float, default=0.0)                   # 实测总面积(㎡)
    # JSON: [{name,type,width,length,area,notes}]
    rooms_data: Mapped[str] = mapped_column(Text, nullable=False, default="[]")
    scan_data: Mapped[str | None] = mapped_column(Text, nullable=True)              # LiDAR/摄像头原始数据 JSON
    voice_transcript: Mapped[str | None] = mapped_column(Text, nullable=True)       # 语音引导对话记录
    device_info: Mapped[str | None] = mapped_column(Text, nullable=True)            # 设备信息 JSON {device,os,sensors}
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="draft")  # draft | in_progress | completed
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)                  # 备注
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    project = relationship("Project")

    @property
    def rooms(self) -> list[dict]:
        try:
            return json.loads(self.rooms_data)
        except (json.JSONDecodeError, TypeError):
            return []

    @rooms.setter
    def rooms(self, value: list[dict]):
        self.rooms_data = json.dumps(value, ensure_ascii=False)

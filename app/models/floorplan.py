import uuid
from datetime import datetime

from sqlalchemy import String, DateTime, ForeignKey, func, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class FloorPlan(Base):
    __tablename__ = "floor_plans"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    project_id: Mapped[str] = mapped_column(String(36), ForeignKey("projects.id"), nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(200), nullable=False, default="未命名方案")
    data: Mapped[str] = mapped_column(Text, nullable=False)
    wall_height: Mapped[float] = mapped_column(default=2.8)
    total_area: Mapped[float] = mapped_column(default=0.0)
    room_count: Mapped[int] = mapped_column(default=0)
    # 空间即导航：逐房间状态（JSON 字符串，形如 {"客厅": "in_progress", "主卧": "completed"}）
    # 取值：not_started(未开始) / in_progress(施工中) / completed(已完成) / attention(需关注)
    room_status: Mapped[str] = mapped_column(Text, nullable=False, default="{}")
    is_active: Mapped[bool] = mapped_column(default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    project = relationship("Project")

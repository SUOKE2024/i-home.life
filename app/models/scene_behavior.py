"""A4 预测式智能场景推荐 — 行为日志 + 预测场景模型"""

import uuid
from datetime import datetime

from sqlalchemy import String, DateTime, ForeignKey, func, Integer, JSON, Boolean, Float, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class SceneBehaviorLog(Base):
    """用户场景行为日志"""

    __tablename__ = "scene_behavior_logs"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    project_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("projects.id"), nullable=False, index=True
    )
    user_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("users.id"), nullable=False, index=True
    )
    action_type: Mapped[str] = mapped_column(
        String(30), nullable=False, index=True
    )
    # action_type: scene_activate / scene_deactivate / scene_create / scene_modify /
    #   manual_trigger / time_trigger / sensor_trigger
    scene_id: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("scene_automations.id"), nullable=True, index=True
    )
    room_type: Mapped[str | None] = mapped_column(String(30), nullable=True)
    # room_type: living_room / bedroom / kitchen / bathroom / entrance / study
    time_of_day: Mapped[int | None] = mapped_column(Integer, nullable=True)  # 0-23
    day_of_week: Mapped[int | None] = mapped_column(Integer, nullable=True)  # 0=Mon, 6=Sun
    duration_seconds: Mapped[int | None] = mapped_column(Integer, nullable=True)
    device_states_before: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    device_states_after: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    ambient_data: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    # ambient_data: {"temperature": 25.0, "humidity": 60, "light_lux": 300, "occupancy": true}
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    project = relationship("Project")
    user = relationship("User")


class PredictedScene(Base):
    """预测场景 — 基于行为日志 AI 推断"""

    __tablename__ = "predicted_scenes"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    project_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("projects.id"), nullable=False, index=True
    )
    user_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("users.id"), nullable=False, index=True
    )
    scene_name: Mapped[str] = mapped_column(String(200), nullable=False)
    room_type: Mapped[str | None] = mapped_column(String(30), nullable=True)
    trigger_time_hint: Mapped[str | None] = mapped_column(String(100), nullable=True)
    # 如 "工作日7:00" / "周末9:30" / "每天日落时"
    trigger_condition: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    actions: Mapped[list | None] = mapped_column(JSON, nullable=True)
    confidence: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)  # 0-1
    based_on_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    status: Mapped[str] = mapped_column(
        String(20), nullable=False, default="suggested", index=True
    )
    # status: suggested / accepted / dismissed / created
    explanation: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    project = relationship("Project")
    user = relationship("User")

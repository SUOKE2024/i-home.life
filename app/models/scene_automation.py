"""F32 场景编辑模型 — 场景联动 + 生态对接"""

import uuid
from datetime import datetime

from sqlalchemy import String, DateTime, ForeignKey, func, Integer, Text, JSON, Boolean
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class SceneAutomation(Base):
    """场景联动"""

    __tablename__ = "scene_automations"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    project_id: Mapped[str] = mapped_column(String(36), ForeignKey("projects.id"), nullable=False, index=True)
    scheme_id: Mapped[str | None] = mapped_column(String(36), ForeignKey("smart_home_schemes.id"), nullable=True, index=True)
    # 关联智能家居方案
    scene_name: Mapped[str] = mapped_column(String(200), nullable=False)
    scene_type: Mapped[str] = mapped_column(String(30), nullable=False, default="manual")
    # scene_type: manual(手动) / scheduled(定时) / triggered(触发) / geo(地理围栏)
    trigger_condition: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    # 触发条件 JSON: {"type": "time", "cron": "0 7 * * *"} 或 {"type": "device", "device_id": "xxx", "state": "on"}
    actions: Mapped[list | None] = mapped_column(JSON, nullable=True)
    # 执行动作列表 JSON: [{"device_id": "xxx", "action": "turn_on", "params": {"brightness": 80}}]
    enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    priority: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    # 优先级,数值越大越优先
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    project = relationship("Project")
    scheme = relationship("SmartHomeScheme")


class EcosystemIntegration(Base):
    """生态对接"""

    __tablename__ = "ecosystem_integrations"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    project_id: Mapped[str] = mapped_column(String(36), ForeignKey("projects.id"), nullable=False, index=True)
    ecosystem: Mapped[str] = mapped_column(String(50), nullable=False)
    # ecosystem: homekit / mijia / harmonyos / alexa / google_home / tuya
    auth_status: Mapped[str] = mapped_column(String(20), nullable=False, default="disconnected")
    # auth_status: connected / disconnected / expired
    device_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    last_synced_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    config: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    # 配置 JSON: {"token": "xxx", "hub_id": "xxx"}
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    project = relationship("Project")

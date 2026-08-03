"""F42 局部焕新模式 — 厨卫焕新/墙面刷新/单空间短周期轻量改造

PRD v3.1 F42（2026-08-03 行业调研新增）：
存量时代厨卫焕新、墙面刷新等短周期局部装修被预判为 3-5 年增长主线；
提供轻量项目模板、短周期排期与预算包、局部施工干扰最小化方案。
"""

import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Integer, JSON, String, Float, Text, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class PartialRenovationPlan(Base):
    """局部焕新计划（表 partial_renovation_plans）"""

    __tablename__ = "partial_renovation_plans"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    project_id: Mapped[str] = mapped_column(String(36), ForeignKey("projects.id"), nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    # scope_type: kitchen_refresh(厨卫焕新) / bathroom_refresh / wall_refresh(墙面刷新) /
    #             single_room(单空间改造) / full_renovation(全屋)
    scope_type: Mapped[str] = mapped_column(String(30), nullable=False, index=True)
    # budget_level: economic(经济) / comfort(舒适) / quality(品质)
    budget_level: Mapped[str] = mapped_column(String(20), nullable=False, default="comfort")
    duration_days: Mapped[int] = mapped_column(Integer, nullable=False, default=7)
    budget_lower: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    budget_upper: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    # tasks: JSON [{phase, name, duration_days, detail, needs_owner_confirm}]
    tasks: Mapped[list | None] = mapped_column(JSON, nullable=True)
    # interference_plan: JSON {noise_windows, dust_control, living_zone, material_inventory, relocation}
    interference_plan: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    # status: draft / active / completed
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="draft")
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    project = relationship("Project")

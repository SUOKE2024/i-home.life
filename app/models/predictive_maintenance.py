"""A6 施工预测性维护 — RiskPrediction 模型"""

import uuid
from datetime import datetime

from sqlalchemy import String, DateTime, ForeignKey, func, Float, JSON
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class RiskPrediction(Base):
    __tablename__ = "risk_predictions"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    project_id: Mapped[str] = mapped_column(String(36), ForeignKey("projects.id"), nullable=False, index=True)

    # risk_type: schedule_delay / cost_overrun / material_shortage / quality_risk / labor_shortage / weather_impact
    risk_type: Mapped[str] = mapped_column(String(30), nullable=False)
    risk_score: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    # risk_score: 0-100
    probability: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    # probability: 0-1
    impact_level: Mapped[str] = mapped_column(String(20), nullable=False, default="low")
    # impact_level: low / medium / high / critical

    trigger_factors: Mapped[list | None] = mapped_column(JSON, nullable=True)
    # 触发因素列表，如 ["任务 #T1 已延期 3 天", "预算使用率达 85%"]
    affected_tasks: Mapped[list | None] = mapped_column(JSON, nullable=True)
    # 受影响任务 ID 列表
    mitigation_actions: Mapped[list | None] = mapped_column(JSON, nullable=True)
    # 建议缓解措施列表

    status: Mapped[str] = mapped_column(String(20), nullable=False, default="active")
    # status: active / mitigated / resolved / ignored

    predicted_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    resolved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    project = relationship("Project")

"""评估快照持久化模型（表 eval_snapshots）

v1.13.6 质量评估体系：把每次评估运行生成的完整报告落库为快照，
支持历史趋势对比（多轮迭代闭环）与漂移检测（vs 历史基线）。
"""

import uuid
from datetime import datetime

from sqlalchemy import String, DateTime, Integer, JSON, Index, func
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class EvalSnapshotRecord(Base):
    """评估报告快照（表 eval_snapshots）"""

    __tablename__ = "eval_snapshots"
    __table_args__ = (
        Index("ix_eval_snapshot_created", "created_at"),
    )

    id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=lambda: str(uuid.uuid4()),
    )
    version: Mapped[str] = mapped_column(String(30), nullable=False, default="")
    baseline: Mapped[str] = mapped_column(String(30), nullable=False, default="full_system")
    sample_size: Mapped[int] = mapped_column(Integer, nullable=False, default=0)

    metrics: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    dimension_scores: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    per_agent_scores: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    quality_targets: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    tool_accuracy: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    feedback_metrics: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    ux_metrics: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    notes: Mapped[list] = mapped_column(JSON, nullable=False, default=list)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(),
    )

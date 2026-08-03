"""B2B 装企交付单模型 — 交付包（设计方案+报价+施工计划）的订单化持久化

v1.4.x 借鉴"卖结果不卖功能"的交付式产品：
- 每次 /api/b2b/delivery 生成的整包交付结果落库，可追溯、可流转
- 状态机：draft → quoted → accepted → in_construction → completed / cancelled
- 私有数据 user_id 强隔离，查询必须携带 user_id
"""

import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import String, Float, DateTime, JSON, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base

# 交付单状态机（合法流转见 b2b_delivery.py _ALLOWED_TRANSITIONS）
STATUS_GENERATING = "generating"
STATUS_DRAFT = "draft"
STATUS_QUOTED = "quoted"
STATUS_ACCEPTED = "accepted"
STATUS_IN_CONSTRUCTION = "in_construction"
STATUS_COMPLETED = "completed"
STATUS_CANCELLED = "cancelled"
ALL_STATUSES = (
    STATUS_GENERATING, STATUS_DRAFT, STATUS_QUOTED, STATUS_ACCEPTED,
    STATUS_IN_CONSTRUCTION, STATUS_COMPLETED, STATUS_CANCELLED,
)


class DeliveryOrder(Base):
    """B2B 装企交付单"""

    __tablename__ = "delivery_orders"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)

    # v1.4.x 对接真实项目：project_id 关联 projects 表（可空，独立快照时为空）
    project_id: Mapped[str | None] = mapped_column(String(36), nullable=True, index=True)

    # 交付输入
    name: Mapped[str] = mapped_column(String(200), nullable=False, default="整装交付")
    area: Mapped[float] = mapped_column(Float, nullable=False)
    style: Mapped[str] = mapped_column(String(50), nullable=False, default="modern")
    budget: Mapped[float] = mapped_column(Float, nullable=False, default=0)
    requirements: Mapped[str] = mapped_column(Text, nullable=False, default="")

    # 交付状态（draft/quoted/accepted/in_construction/completed/cancelled）
    status: Mapped[str] = mapped_column(String(20), nullable=False, default=STATUS_DRAFT, index=True)

    # 交付包内容（整包快照，独立于后续订单流转）
    summary: Mapped[str | None] = mapped_column(Text, nullable=True)
    proposals: Mapped[list[dict[str, Any]] | None] = mapped_column(JSON, nullable=True)
    budget_estimate: Mapped[dict[str, Any] | None] = mapped_column(JSON, nullable=True)
    construction_plan: Mapped[dict[str, Any] | None] = mapped_column(JSON, nullable=True)
    sources: Mapped[dict[str, str] | None] = mapped_column(JSON, nullable=True)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(),
    )

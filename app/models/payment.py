"""支付管理模型 — F15 里程碑支付：发起 → 确认 → 退款 / 电子发票 / 分阶段支付节点"""

import uuid
from datetime import datetime

from sqlalchemy import String, DateTime, ForeignKey, func, Float, Text, Integer
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class Payment(Base):
    """支付记录"""
    __tablename__ = "payments"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    project_id: Mapped[str] = mapped_column(String(36), ForeignKey("projects.id"), nullable=False)
    settlement_id: Mapped[str | None] = mapped_column(String(36), ForeignKey("settlements.id"), nullable=True)
    milestone_code: Mapped[str] = mapped_column(String(30), nullable=False, default="completion")
    # handover / plumbing / tiling / completion / warranty

    # F15 分阶段支付节点
    stage_code: Mapped[str | None] = mapped_column(String(30), nullable=True)
    # deposit(首付) / progress(进度款) / final(尾款) / warranty(质保金)
    stage_order: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    due_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)  # 应付日期

    amount: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    payment_method: Mapped[str] = mapped_column(String(30), nullable=False, default="bank_transfer")
    # bank_transfer / alipay / wechat / cash / other

    # 状态机：pending → paid → refunded | pending → disputed → paid/failed
    # disputed: 争议中间态，资金类业务不可逆保护
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="pending")
    # pending / disputed / paid / refunded / failed

    transaction_id: Mapped[str | None] = mapped_column(String(100), nullable=True)  # 第三方流水号
    payer: Mapped[str | None] = mapped_column(String(100), nullable=True)  # 付款方
    payee: Mapped[str | None] = mapped_column(String(100), nullable=True)  # 收款方
    evidence_url: Mapped[str | None] = mapped_column(String(500), nullable=True)  # 凭证 URL
    note: Mapped[str | None] = mapped_column(Text, nullable=True)

    # F15 电子发票
    invoice_no: Mapped[str | None] = mapped_column(String(50), nullable=True)  # 发票号
    invoice_url: Mapped[str | None] = mapped_column(String(500), nullable=True)  # 发票文件 URL
    invoiced_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)  # 开票时间

    paid_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    refunded_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    refund_amount: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    refund_reason: Mapped[str | None] = mapped_column(String(500), nullable=True)

    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), onupdate=func.now())

    project = relationship("Project")
    settlement = relationship("Settlement", back_populates="payments")

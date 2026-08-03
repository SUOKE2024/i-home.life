"""F43 资金托管深化 — 银行存管/第三方监管 + 节点验收双向确认放款

PRD v3.1 F43（2026-08-03 行业调研新增）：
现有 escrow 担保支付（app.models.procurement_enhanced.EscrowPayment）深化为：
- 对接银行存管 / 第三方监管账户
- 节点验收双向确认后放款（业主 + 施工方/供应商）
- 托管资金利息归属业主
依据：资金托管渗透率已达 93.5%，为行业标配。
"""

import uuid
from datetime import datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, String, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class EscrowTrusteeAccount(Base):
    """资金托管存管账户（表 escrow_trustee_accounts）"""

    __tablename__ = "escrow_trustee_accounts"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    escrow_payment_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("escrow_payments.id"), nullable=False, unique=True, index=True
    )
    # trustee_type: bank(银行存管) / third_party(第三方监管账户)
    trustee_type: Mapped[str] = mapped_column(String(20), nullable=False, default="bank")
    # 存管账号（脱敏展示，仅保留后 4 位）
    account_no_masked: Mapped[str] = mapped_column(String(30), nullable=False)
    # 托管资金利息归属业主
    interest_to_owner: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    # 节点验收双向确认（业主 + 承包方/供应商）
    owner_confirmed: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    contractor_confirmed: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    # status: active(存管中) / release_requested(放款请求) / released(已放款) / closed(已关闭)
    status: Mapped[str] = mapped_column(String(30), nullable=False, default="active")
    # release_rule: node_based(节点验收双向确认后放款) / agreed_schedule(合同约定节点)
    release_rule: Mapped[str] = mapped_column(String(30), nullable=False, default="node_based")
    released_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    escrow_payment = relationship("EscrowPayment")

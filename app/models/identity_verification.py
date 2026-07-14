"""实名认证模型 — 支持第三方身份证 OCR / 工商信息核验"""
import uuid
from datetime import datetime

from sqlalchemy import String, DateTime, ForeignKey, func, Text, Boolean, JSON
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class IdentityVerification(Base):
    """实名认证记录"""
    __tablename__ = "identity_verifications"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id: Mapped[str] = mapped_column(String(36), ForeignKey("users.id"), nullable=False, unique=True)

    # 角色
    role: Mapped[str] = mapped_column(String(20), nullable=False)
    # homeowner / designer / supplier / contractor

    # 通用实名信息
    real_name: Mapped[str] = mapped_column(String(100), nullable=False)
    id_card: Mapped[str] = mapped_column(String(18), nullable=False)  # 加密存储
    id_card_front: Mapped[str | None] = mapped_column(String(500), nullable=True)   # 身份证正面 OSS URL
    id_card_back: Mapped[str | None] = mapped_column(String(500), nullable=True)    # 身份证背面 OSS URL
    selfie_with_id: Mapped[str | None] = mapped_column(String(500), nullable=True)  # 手持身份证照 OSS URL

    # 第三方核验结果
    third_party_verified: Mapped[bool] = mapped_column(Boolean, default=False)
    third_party_provider: Mapped[str | None] = mapped_column(String(50), nullable=True)  # aliyun / tencent / wechat
    third_party_result: Mapped[str | None] = mapped_column(Text, nullable=True)          # JSON 核验详情

    # 角色特定属性（JSON）
    # supplier: {"business_license": "url", "company_name": "xx建材", "categories": ["瓷砖","地板"], "license_no": "xxx"}
    # designer: {"qualification_cert": "url", "design_styles": ["现代","北欧"], "school": "清华大学美术学院", "awards": 2}
    # contractor: {"qualification_cert": "url", "safety_cert": "url", "team_size": 10, "specialties": ["水电","泥瓦"]}
    role_attributes: Mapped[str | None] = mapped_column(Text, nullable=True)

    # 审核状态
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="pending")
    # pending / approved / rejected
    reviewer_id: Mapped[str | None] = mapped_column(String(36), ForeignKey("users.id"), nullable=True)
    review_note: Mapped[str | None] = mapped_column(Text, nullable=True)
    verified_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)

    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), onupdate=func.now())

"""工程队匹配模型 — F36 工程队档案 + 评分 + 匹配"""

import uuid
from datetime import datetime

from sqlalchemy import String, DateTime, ForeignKey, func, Float, Integer, Text, Boolean
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class ConstructionCrew(Base):
    """工程队档案"""
    __tablename__ = "construction_crews"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    leader: Mapped[str] = mapped_column(String(100), nullable=False)  # 工长姓名
    phone: Mapped[str | None] = mapped_column(String(50), nullable=True)
    city: Mapped[str | None] = mapped_column(String(100), nullable=True)
    district: Mapped[str | None] = mapped_column(String(100), nullable=True)

    # 资质等级：A/B/C/D
    qualification: Mapped[str] = mapped_column(String(10), nullable=False, default="B")
    # 业务范围（JSON 数组：["mep","masonry","carpentry","painting","installation"]）
    specialties: Mapped[str | None] = mapped_column(Text, nullable=True)

    # F36 入驻审核材料（提交审核时必填）
    license_no: Mapped[str | None] = mapped_column(String(100), nullable=True)  # 营业执照号
    license_type: Mapped[str | None] = mapped_column(String(50), nullable=True)  # 执照类型
    insurance_no: Mapped[str | None] = mapped_column(String(100), nullable=True)  # 保险单号
    # 入驻审核状态：pending（待审核）/ approved（通过）/ rejected（驳回，可重新提交）
    review_status: Mapped[str] = mapped_column(String(20), nullable=False, default="pending")
    review_note: Mapped[str | None] = mapped_column(String(500), nullable=True)  # 审核备注
    reviewed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    # 评分（0-5）
    rating: Mapped[float] = mapped_column(Float, nullable=False, default=4.0)
    completed_projects: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    # 平均工期（天）
    avg_duration: Mapped[int] = mapped_column(Integer, nullable=False, default=60)
    # 日单价（元）
    daily_rate: Mapped[int] = mapped_column(Integer, nullable=False, default=800)

    # 在岗状态：available / busy / offline
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="available")
    introduction: Mapped[str | None] = mapped_column(Text, nullable=True)
    # 作品集代表作全景（设计 4.3 服务商智能展厅）：已交付项目 VRPanorama 实景，关联 vr_panoramas.id
    showcase_panorama_id: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("vr_panoramas.id"), nullable=True, index=True
    )

    # 付费展厅商业闭环（设计 4.3）：权益归属用户（兑换置顶/VR 实拍权益的平台账号）
    owner_id: Mapped[str | None] = mapped_column(String(36), ForeignKey("users.id"), nullable=True, index=True)
    # 作品集置顶标志——平台授予（权益生效驱动），非工程队自报，无权益恒 False
    featured: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())


class CrewBenefit(Base):
    """服务商展厅权益兑换记录（设计 4.3 商业模式：付费展厅/作品集置顶/VR 实拍）"""
    __tablename__ = "crew_benefits"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    crew_id: Mapped[str] = mapped_column(String(36), ForeignKey("construction_crews.id"), nullable=False, index=True)
    user_id: Mapped[str] = mapped_column(String(36), ForeignKey("users.id"), nullable=False, index=True)
    benefit_type: Mapped[str] = mapped_column(String(30), nullable=False)
    # showroom_featured(作品集置顶) / vr_photo(VR 实拍权益)
    points_spent: Mapped[int] = mapped_column(Integer, nullable=False)

    expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="active")
    # active / expired / refunded

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    crew = relationship("ConstructionCrew")


class CrewMatch(Base):
    """工程队-项目匹配记录"""
    __tablename__ = "crew_matches"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    project_id: Mapped[str] = mapped_column(String(36), ForeignKey("projects.id"), nullable=False, index=True)
    crew_id: Mapped[str] = mapped_column(String(36), ForeignKey("construction_crews.id"), nullable=False, index=True)

    # 匹配评分（0-100）
    match_score: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    # 匹配维度明细（JSON）
    score_breakdown: Mapped[str | None] = mapped_column(Text, nullable=True)
    # 推荐理由
    recommendation: Mapped[str | None] = mapped_column(Text, nullable=True)

    # 状态：pending / shortlisted / hired / rejected
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="pending")

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    project = relationship("Project")
    crew = relationship("ConstructionCrew")

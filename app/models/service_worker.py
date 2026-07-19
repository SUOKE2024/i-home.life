"""F35 服务者匹配模型 — 设计师/监理/预算师/木工/水电安装工/窗帘安装工档案 + 评分 + 匹配"""

import uuid
from datetime import datetime

from sqlalchemy import String, DateTime, ForeignKey, func, Float, Integer, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base

# 支持的所有服务者角色
SUPPORTED_ROLES = (
    "designer",             # 设计师
    "supervisor",           # 监理
    "estimator",            # 预算师
    "carpenter",            # 木工
    "plumber_electrician",  # 水电安装工
    "curtain_installer",    # 窗帘安装工
)


class ServiceWorker(Base):
    """服务者档案（设计师 / 监理 / 预算师 / 木工 / 水电安装工 / 窗帘安装工）"""

    __tablename__ = "service_workers"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    phone: Mapped[str | None] = mapped_column(String(50), nullable=True)
    avatar_url: Mapped[str | None] = mapped_column(String(500), nullable=True)
    city: Mapped[str | None] = mapped_column(String(100), nullable=True)
    district: Mapped[str | None] = mapped_column(String(100), nullable=True)

    # 角色：designer / supervisor / estimator / carpenter / plumber_electrician / curtain_installer
    role: Mapped[str] = mapped_column(String(20), nullable=False)
    # 角色专属属性（JSON）
    # designer: {"design_styles": ["modern","minimal"], "software": ["AutoCAD","SketchUp"],
    #   "portfolio_count": 50, "awards": 2}
    # supervisor: {"phases": ["mep","masonry"], "certificate": "监理工程师", "supervised_projects": 80}
    # estimator: {"budget_types": ["main","soft"], "accuracy_rate": 0.92, "estimated_projects": 120}
    # carpenter: {"skills": ["furniture","door_window","cabinet","flooring","ceiling"], "certificate": "木工证",
    #   "tool_level": "专业"}
    # plumber_electrician: {"specialties": ["water_supply","drainage","electrical","gas","heating"],
    #   "license_type": "电工证", "certificate": "水电工上岗证"}
    # curtain_installer: {"curtain_types": ["roller","roman","motorized","fabric","sheer"],
    #   "motorized_install": true, "brand_experience": ["杜亚","somfy"]}
    role_attributes: Mapped[str | None] = mapped_column(Text, nullable=True)

    # 资质等级：A/B/C/D
    qualification: Mapped[str] = mapped_column(String(10), nullable=False, default="B")
    # 评分（0-5）
    rating: Mapped[float] = mapped_column(Float, nullable=False, default=4.0)
    completed_projects: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    years_of_experience: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    # 收费标准
    hourly_rate: Mapped[int] = mapped_column(Integer, nullable=False, default=200)
    daily_rate: Mapped[int] = mapped_column(Integer, nullable=False, default=800)

    # 在岗状态：available / busy / offline
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="available")
    introduction: Mapped[str | None] = mapped_column(Text, nullable=True)
    # 资质证书（JSON 数组）
    certifications: Mapped[str | None] = mapped_column(Text, nullable=True)
    # 作品集 URL（JSON 数组）
    portfolio_urls: Mapped[str | None] = mapped_column(Text, nullable=True)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    # 关联匹配记录
    matches = relationship("ServiceWorkerMatch", back_populates="worker")


class ServiceWorkerMatch(Base):
    """服务者-项目匹配记录"""

    __tablename__ = "service_worker_matches"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    project_id: Mapped[str] = mapped_column(String(36), ForeignKey("projects.id"), nullable=False, index=True)
    worker_id: Mapped[str] = mapped_column(String(36), ForeignKey("service_workers.id"), nullable=False, index=True)
    role: Mapped[str] = mapped_column(String(20), nullable=False)

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
    worker = relationship("ServiceWorker", back_populates="matches")

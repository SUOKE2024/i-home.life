"""总控 Agent 任务模型 — 项目分解、任务推送、申领与分配"""
import uuid
from datetime import datetime

from sqlalchemy import String, DateTime, ForeignKey, func, Text, Integer, Boolean, Float
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class OrchestratorTask(Base):
    """总控 Agent 协调任务"""
    __tablename__ = "orchestrator_tasks"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    project_id: Mapped[str] = mapped_column(String(36), ForeignKey("projects.id"), nullable=False)

    task_type: Mapped[str] = mapped_column(String(30), nullable=False)
    # design / budget / procurement / construction / qa_inspector / settlement / survey / content_publish
    title: Mapped[str] = mapped_column(String(200), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    assigned_agent: Mapped[str] = mapped_column(String(30), nullable=False)
    # designer / budget / procurement / construction / qa_inspector / settlement / orchestrator / content_publisher
    assigned_user_id: Mapped[str | None] = mapped_column(String(36), ForeignKey("users.id"), nullable=True)
    # 指定给哪个设计师/工长/供应商（为空时进入任务池公开申领）

    priority: Mapped[int] = mapped_column(Integer, nullable=False, default=5)  # 1-10

    status: Mapped[str] = mapped_column(String(20), nullable=False, default="pending")
    # pending / claimed / in_progress / completed / failed / cancelled

    # 任务依赖
    parent_task_id: Mapped[str | None] = mapped_column(String(36), ForeignKey("orchestrator_tasks.id"), nullable=True)
    dependencies: Mapped[str | None] = mapped_column(Text, nullable=True)  # JSON 数组，前置任务 ID 列表

    # 申领配置
    claimable: Mapped[bool] = mapped_column(Boolean, default=True)
    claim_deadline: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    claim_role: Mapped[str | None] = mapped_column(String(20), nullable=True)
    # designer / contractor / supplier — 允许申领的角色

    # 结果
    result: Mapped[str | None] = mapped_column(Text, nullable=True)  # 任务执行结果（JSON）

    created_by: Mapped[str] = mapped_column(String(36), nullable=False)  # user_id 或 agent_name
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    started_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)

    # 关联
    assigned_user = relationship("User", foreign_keys=[assigned_user_id])
    parent = relationship("OrchestratorTask", back_populates="children", remote_side=[id])
    children = relationship("OrchestratorTask", back_populates="parent")


class TaskCandidate(Base):
    """任务候选人（申领者）"""
    __tablename__ = "task_candidates"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    task_id: Mapped[str] = mapped_column(String(36), ForeignKey("orchestrator_tasks.id"), nullable=False)
    user_id: Mapped[str] = mapped_column(String(36), ForeignKey("users.id"), nullable=False)

    # 候选人得分
    points_score: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)   # 积分维度得分
    experience_score: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)  # 经验维度得分
    rating_score: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)     # 评分维度得分
    composite_score: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)  # 综合得分
    score_breakdown: Mapped[str | None] = mapped_column(Text, nullable=True)  # JSON 明细

    status: Mapped[str] = mapped_column(String(20), nullable=False, default="pending")
    # pending / confirmed / rejected

    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())

"""A2A (Agent-to-Agent) 任务持久化模型"""
import uuid
from datetime import datetime, timedelta, timezone

from sqlalchemy import String, DateTime, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base

# A2A 任务默认 TTL：24 小时
A2A_TASK_DEFAULT_TTL_HOURS = 24


class A2ATask(Base):
    """A2A 协议任务 — 持久化到数据库，避免进程重启丢失"""
    __tablename__ = "a2a_tasks"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    task_id: Mapped[str] = mapped_column(String(48), nullable=False, unique=True, index=True)
    # a2a_ 前缀 + 12 位 hex，如 "a2a_a1b2c3d4e5f6"

    agent_name: Mapped[str] = mapped_column(String(30), nullable=False)
    message: Mapped[str] = mapped_column(Text, nullable=False)
    project_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    user_id: Mapped[str | None] = mapped_column(String(36), nullable=True, index=True)

    state: Mapped[str] = mapped_column(String(20), nullable=False, default="submitted")
    # submitted / working / completed / failed

    result: Mapped[str | None] = mapped_column(Text, nullable=True)
    error: Mapped[str | None] = mapped_column(Text, nullable=True)

    # v1.15.5 协议信任层（AAIF「可验证证据在协议边界」+ AP2 借鉴）：
    # A2A 任务执行证据链持久化——trace_id 关联 harness 轨迹（可回放溯源），
    # evidence 存 JSON（agent_name/workflow_id/duration_ms/degraded/status），
    # 客户端可核验「任务确实由哪个 Agent 执行、是否降级」而非信任裸文案。
    trace_id: Mapped[str | None] = mapped_column(String(12), nullable=True, index=True)
    evidence: Mapped[str | None] = mapped_column(Text, nullable=True)  # JSON 字符串

    expires_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc) + timedelta(hours=A2A_TASK_DEFAULT_TTL_HOURS),
        index=True,
    )

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
    )

"""Agent 执行轨迹持久化模型（表 agent_traces）

对齐 2026 Agent 可观测性前沿（MELT+P + workflow ID 传播）：
- 每个 Agent 执行（think/think_with_tools/harness run）落一条记录，
  供离线评估（per-agent 成功率/延迟/降级率）、漂移检测与问题回溯。
- workflow_id：跨 Agent 协作时从编排入口传播，同一用户请求的所有
  Agent 执行共享同一 workflow_id（对齐 DZone 2026「workflow ID 在
  每条 agent span 上传播」范式）。
- prompt 上下文采样：按采样率截断记录 system prompt + 用户消息
  （防 PII 扩散：最长 500/300 字符截断，不存完整对话）。
- 采集路径受 settings.agent_trace_persist_enabled 门控，关闭时零落库。
"""

import uuid
from datetime import datetime, timezone

from sqlalchemy import String, Text, DateTime, Float, Integer, Boolean, Index, func
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class AgentTraceRecord(Base):
    """Agent 执行轨迹（表 agent_traces）"""

    __tablename__ = "agent_traces"
    __table_args__ = (
        Index("ix_agent_trace_agent_time", "agent_name", "created_at"),
        Index("ix_agent_trace_workflow_time", "workflow_id", "created_at"),
    )

    id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=lambda: str(uuid.uuid4()),
    )  # trace_id
    workflow_id: Mapped[str | None] = mapped_column(String(36), nullable=True, index=True)
    agent_name: Mapped[str] = mapped_column(String(60), nullable=False, index=True)
    agent_version: Mapped[str | None] = mapped_column(String(30), nullable=True)
    provider: Mapped[str | None] = mapped_column(String(30), nullable=True)
    model: Mapped[str | None] = mapped_column(String(100), nullable=True)

    status: Mapped[str] = mapped_column(String(20), nullable=False, default="pending")
    # pending / running / success / failed / fallback / degraded
    user_id: Mapped[str | None] = mapped_column(String(36), nullable=True, index=True)
    project_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    scope: Mapped[str | None] = mapped_column(String(20), nullable=True)
    context_source: Mapped[str | None] = mapped_column(String(20), nullable=True)

    latency_ms: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    first_token_latency_ms: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)

    prompt_tokens: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    completion_tokens: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    total_tokens: Mapped[int] = mapped_column(Integer, nullable=False, default=0)

    tool_call_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    tool_call_rounds: Mapped[int] = mapped_column(Integer, nullable=False, default=0)

    fallback_used: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    fallback_reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    retry_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)

    error_type: Mapped[str | None] = mapped_column(String(60), nullable=True)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)

    # prompt 上下文采样（截断防 PII 扩散，仅采样到的轨迹有值）
    prompt_preview: Mapped[str | None] = mapped_column(Text, nullable=True)
    response_preview: Mapped[str | None] = mapped_column(Text, nullable=True)

    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=_utcnow)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(),
    )

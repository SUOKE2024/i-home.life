"""Agent Case 模型 — 任务执行轨迹的结构化沉淀

借鉴 EverMind EverOS Agent Memory（2026-04 公测）+ SkillCorpus 论文：
- Agent 完成任务后，轨迹（trace）被压缩、去噪、提取为结构化 Case
- Case = task_intent（自包含意图，检索键）+ approach（分步压缩记录）+ quality_score（0-1 自评）
- 同主题 Case 积累后聚类蒸馏为 Skill（见 agent_skill_evolution_service）
- Case 按 scope 隔离（复用 agent_memory / agent_skill 的 personal/project/team/org 体系）

与 AgentTrace（harness.py 运行时 dataclass）的区别：
  AgentTrace = 一次执行的瞬时可观测数据（token/延迟/工具链），生命周期=单次请求
  AgentCase  = Trace 提炼后的持久化经验资产，生命周期=跨会话复用

隐私约束（对齐 CLAUDE.md 会话加密 + 缓存隔离红线）：
- user_id 强隔离，查询必须携带 user_id（scope=personal）或授权校验
- approach 仅存压缩后步骤摘要，不存原始 PII 明文
- 软删除（deleted_at），不物理删除
"""

import uuid
from datetime import datetime

from sqlalchemy import (
    String, Text, DateTime, Float, Integer, ForeignKey, Index, func,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class AgentCase(Base):
    """Agent 任务执行 Case（表 agent_cases）

    一条 Case = 一次目标导向任务的结构化执行记录。
    非目标导向对话（闲聊/简单 Q&A）不入 Case（提取时过滤）。
    """

    __tablename__ = "agent_cases"
    __table_args__ = (
        Index("ix_agent_cases_scope_owner", "scope", "owner_id"),
        Index("ix_agent_cases_quality", "quality_score"),
    )

    id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=lambda: str(uuid.uuid4()),
    )

    # ── 归属（对齐 agent_skill scope 体系）──
    scope: Mapped[str] = mapped_column(String(20), nullable=False, default="personal", index=True)
    owner_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    # personal→user_id / project→project_id / team→team_id / org→固定 "org"

    # ── 执行溯源 ──
    agent_name: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    session_id: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("agent_sessions.id"), nullable=True, index=True,
    )
    trace_id: Mapped[str | None] = mapped_column(String(12), nullable=True)
    # 关联 harness.AgentTrace.trace_id（运行时轨迹），便于回溯原始可观测数据

    # ── Case 核心（借鉴 EverOS Agent Case 结构）──
    task_intent: Mapped[str] = mapped_column(Text, nullable=False)
    # 自包含的任务意图陈述（检索键：未来 Agent 面对相似任务时用它匹配）

    approach: Mapped[str] = mapped_column(Text, nullable=False, default="")
    # 压缩后的分步执行记录（JSON 数组）：
    # [{"step": 1, "attempted": "...", "tool": "...", "result": "...", "revised": false}]
    # 失败重试也记录，供未来 Agent 避免重复错误

    outcome: Mapped[str] = mapped_column(String(20), nullable=False, default="unknown")
    # success / partial / failed / unknown

    quality_score: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    # 0.0-1.0 自评（用户反馈 agent_feedbacks 可校准此值）

    # ── 进化统计（Skill 蒸馏 + 诊断归因用）──
    cluster_id: Mapped[str | None] = mapped_column(String(36), nullable=True, index=True)
    # 聚类后归属的簇 id（同簇 Case 蒸馏为一个 Skill）
    distilled_to_skill_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    # 已被蒸馏进哪个 Skill（避免重复蒸馏）

    retrieval_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    last_retrieved_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True,
    )

    # ── 审计 ──
    created_by: Mapped[str] = mapped_column(
        String(36), ForeignKey("users.id"), nullable=False,
    )
    deleted_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True, default=None,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(),
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(),
    )

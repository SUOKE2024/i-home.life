"""v1.10.1 Agent Case 自进化管线: agent_cases 表 + agent_skills 进化列

Revision ID: a9b0c1d2e3f4
Revises: y1a2b3c4d5e6
Create Date: 2026-08-08

借鉴 EverMind EverOS Agent Memory + SkillCorpus + HarnessBank：
- agent_cases: 从 AgentTrace 提取的结构化任务执行 Case（task_intent + approach + quality_score）
- agent_skills 进化列: success/fail 计数 + 三维质控评分（Utility/Robustness/Safety）

特性：
  - 幂等：建表用 has_table 检查，加列用 has_column 检查（生产可安全重复执行）
  - NOT NULL 列带 server_default（存量行获得默认值，避免 ALTER 失败）
  - SQLite batch mode 兼容
  - 回滚：DROP TABLE / DROP COLUMN（幂等）
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "a9b0c1d2e3f4"
down_revision: Union[str, None] = "y1a2b3c4d5e6"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

_CASE_TABLE = "agent_cases"
_SKILL_TABLE = "agent_skills"

_SKILL_NEW_COLUMNS: list[tuple[str, sa.Column]] = [
    ("success_count", sa.Column("success_count", sa.Integer(), nullable=False, server_default="0")),
    ("fail_count", sa.Column("fail_count", sa.Integer(), nullable=False, server_default="0")),
    ("utility_score", sa.Column("utility_score", sa.Float(), nullable=False, server_default="0.0")),
    ("robustness_score", sa.Column("robustness_score", sa.Float(), nullable=False, server_default="0.0")),
    ("safety_score", sa.Column("safety_score", sa.Float(), nullable=False, server_default="0.0")),
    ("last_evaluated_at", sa.Column("last_evaluated_at", sa.DateTime(timezone=True), nullable=True)),
]


def _has_table(table_name: str) -> bool:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    try:
        return table_name in inspector.get_table_names()
    except Exception:
        return True


def _has_column(table_name: str, column_name: str) -> bool:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    try:
        cols = [c["name"] for c in inspector.get_columns(table_name)]
    except Exception:
        return True
    return column_name in cols


def upgrade() -> None:
    # 1. 创建 agent_cases 表
    if not _has_table(_CASE_TABLE):
        op.create_table(
            _CASE_TABLE,
            sa.Column("id", sa.String(36), primary_key=True),
            sa.Column("scope", sa.String(20), nullable=False, server_default="personal"),
            sa.Column("owner_id", sa.String(36), nullable=False),
            sa.Column("agent_name", sa.String(50), nullable=False),
            sa.Column("session_id", sa.String(36), nullable=True),
            sa.Column("trace_id", sa.String(12), nullable=True),
            sa.Column("task_intent", sa.Text(), nullable=False),
            sa.Column("approach", sa.Text(), nullable=False, server_default=""),
            sa.Column("outcome", sa.String(20), nullable=False, server_default="unknown"),
            sa.Column("quality_score", sa.Float(), nullable=False, server_default="0.0"),
            sa.Column("cluster_id", sa.String(36), nullable=True),
            sa.Column("distilled_to_skill_id", sa.String(36), nullable=True),
            sa.Column("retrieval_count", sa.Integer(), nullable=False, server_default="0"),
            sa.Column("last_retrieved_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column("created_by", sa.String(36), nullable=False),
            sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
            sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
            sa.ForeignKeyConstraint(["session_id"], ["agent_sessions.id"]),
            sa.ForeignKeyConstraint(["created_by"], ["users.id"]),
        )
        op.create_index("ix_agent_cases_scope_owner", _CASE_TABLE, ["scope", "owner_id"])
        op.create_index("ix_agent_cases_agent_name", _CASE_TABLE, ["agent_name"])
        op.create_index("ix_agent_cases_quality", _CASE_TABLE, ["quality_score"])
        op.create_index("ix_agent_cases_scope", _CASE_TABLE, ["scope"])
        print(f"  created: {_CASE_TABLE}")
    else:
        print(f"  skip: {_CASE_TABLE} already exists")

    # 2. agent_skills 加进化列
    bind = op.get_bind()
    is_sqlite = bind.dialect.name == "sqlite"
    for col_name, col in _SKILL_NEW_COLUMNS:
        if _has_column(_SKILL_TABLE, col_name):
            print(f"  skip: {_SKILL_TABLE}.{col_name} already exists")
            continue
        if is_sqlite:
            with op.batch_alter_table(_SKILL_TABLE) as batch_op:
                batch_op.add_column(col)
        else:
            op.add_column(_SKILL_TABLE, col)
        print(f"  added: {_SKILL_TABLE}.{col_name}")


def downgrade() -> None:
    # 2. agent_skills 删进化列
    bind = op.get_bind()
    is_sqlite = bind.dialect.name == "sqlite"
    for col_name, _ in reversed(_SKILL_NEW_COLUMNS):
        if not _has_column(_SKILL_TABLE, col_name):
            continue
        if is_sqlite:
            with op.batch_alter_table(_SKILL_TABLE) as batch_op:
                batch_op.drop_column(col_name)
        else:
            op.drop_column(_SKILL_TABLE, col_name)

    # 1. 删 agent_cases 表
    if _has_table(_CASE_TABLE):
        op.drop_table(_CASE_TABLE)

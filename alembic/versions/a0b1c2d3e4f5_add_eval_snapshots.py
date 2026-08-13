"""add eval_snapshots table

Revision ID: a0b1c2d3e4f5
Revises: z8a9b0c1d2e3
Create Date: 2026-08-13

v1.13.6 质量评估体系（快照层）：
  - 新增 eval_snapshots 表，持久化每次评估运行生成的完整报告快照
  - 支持历史趋势对比（多轮迭代闭环）与漂移检测（vs 历史基线）

特性：
  - 幂等：_has_table 检查（生产可安全重复执行）
  - JSON 列由 model Python 默认值填充（新建表无存量行，无需 server_default）
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "a0b1c2d3e4f5"
down_revision: Union[str, None] = "f6a7b8c9d0e2"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

_TABLE = "eval_snapshots"


def _has_table(table_name: str) -> bool:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    try:
        return table_name in inspector.get_table_names()
    except Exception:
        return False


def upgrade() -> None:
    if _has_table(_TABLE):
        print(f"  skip: {_TABLE} already exists")
        return
    op.create_table(
        _TABLE,
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("version", sa.String(30), nullable=False, server_default=""),
        sa.Column("baseline", sa.String(30), nullable=False, server_default="full_system"),
        sa.Column("sample_size", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("metrics", sa.JSON(), nullable=False),
        sa.Column("dimension_scores", sa.JSON(), nullable=False),
        sa.Column("per_agent_scores", sa.JSON(), nullable=False),
        sa.Column("quality_targets", sa.JSON(), nullable=False),
        sa.Column("tool_accuracy", sa.JSON(), nullable=False),
        sa.Column("feedback_metrics", sa.JSON(), nullable=False),
        sa.Column("ux_metrics", sa.JSON(), nullable=False),
        sa.Column("notes", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index("ix_eval_snapshot_created", _TABLE, ["created_at"])
    print(f"  created: {_TABLE}")


def downgrade() -> None:
    if not _has_table(_TABLE):
        print(f"  skip: {_TABLE} not exists")
        return
    op.drop_index("ix_eval_snapshot_created", table_name=_TABLE)
    op.drop_table(_TABLE)
    print(f"  dropped: {_TABLE}")

"""v1.8.0: Agent 工具批准 — 新建 agent_approvals 表

Revision ID: u6b7c8d9e0f1
Revises: t5a6b7c8d9e0
Create Date: 2026-08-03 14:30:00.000000

借鉴 YC QM strict posture，FC 无状态环境调整为"拒绝-重新触发"模式。
对齐 a2a_task.py 异步状态机范式。幂等设计。
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = 'u6b7c8d9e0f1'
down_revision: Union[str, None] = 't5a6b7c8d9e0'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

_TABLE_NAME = 'agent_approvals'


def upgrade() -> None:
    conn = op.get_bind()
    inspector = sa.inspect(conn)

    if inspector.has_table(_TABLE_NAME):
        print(f"  skip: table {_TABLE_NAME} already exists")
        return

    op.create_table(
        _TABLE_NAME,
        sa.Column('id', sa.String(36), nullable=False),
        sa.Column('approval_id', sa.String(48), nullable=False),
        sa.Column('user_id', sa.String(36), nullable=False),
        sa.Column('agent_name', sa.String(50), nullable=False),
        sa.Column('tool_name', sa.String(100), nullable=False),
        sa.Column('arguments', sa.Text(), nullable=False, server_default='{}'),
        sa.Column('project_id', sa.String(36), nullable=True),
        sa.Column('scope', sa.String(20), nullable=False, server_default='personal'),
        sa.Column('trace_id', sa.String(36), nullable=True),
        sa.Column('state', sa.String(20), nullable=False, server_default='pending'),
        sa.Column('decided_by', sa.String(36), nullable=True),
        sa.Column('decided_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('decision_reason', sa.Text(), nullable=True),
        sa.Column('expires_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column(
            'created_at', sa.DateTime(timezone=True),
            server_default=sa.func.now(), nullable=False,
        ),
        sa.Column(
            'updated_at', sa.DateTime(timezone=True),
            server_default=sa.func.now(), nullable=False,
        ),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('approval_id', name='uq_approval_id'),
        sa.CheckConstraint(
            "state IN ('pending', 'approved', 'rejected', 'expired')",
            name='chk_approval_state',
        ),
    )
    op.create_index('ix_agent_approvals_approval_id', _TABLE_NAME, ['approval_id'])
    op.create_index('ix_agent_approvals_user_id', _TABLE_NAME, ['user_id'])
    op.create_index('ix_agent_approvals_state', _TABLE_NAME, ['state'])
    op.create_index('ix_agent_approvals_expires_at', _TABLE_NAME, ['expires_at'])
    print(f"  created: table {_TABLE_NAME}")


def downgrade() -> None:
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    if not inspector.has_table(_TABLE_NAME):
        return
    op.drop_table(_TABLE_NAME)
    print(f"  dropped: table {_TABLE_NAME}")

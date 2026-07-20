"""v1.1.19: Agent 会话持久化 — 新增 agent_sessions 和 agent_messages 表

Revision ID: h8c9d0e1f2a3
Revises: g7b8c9d0e1f2
Create Date: 2026-07-20 12:00:00.000000

新增两张表支持 Agent 对话会话持久化：
- agent_sessions: 会话元数据（标题、agent 类型、消息计数、软删除）
- agent_messages: 对话消息（role/content/序号/哈希）
- agent_feedbacks: 新增 session_id 外键字段

隐私保护设计：
- 会话标题自动从首条用户消息截取，最多 100 字符
- 消息内容散列化存储（content_hash）
- 软删除机制（is_deleted）
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'h8c9d0e1f2a3'
down_revision: Union[str, None] = 'g7b8c9d0e1f2'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # agent_sessions 表
    op.create_table(
        'agent_sessions',
        sa.Column('id', sa.String(36), nullable=False),
        sa.Column('user_id', sa.String(36), sa.ForeignKey('users.id'), nullable=False),
        sa.Column('project_id', sa.String(36), sa.ForeignKey('projects.id'), nullable=True),
        sa.Column('title', sa.String(100), nullable=False, server_default='新的对话'),
        sa.Column('primary_agent_type', sa.String(50), nullable=True),
        sa.Column('message_count', sa.Integer, nullable=False, server_default='0'),
        sa.Column('is_deleted', sa.Boolean, nullable=False, server_default='0'),
        sa.Column('deleted_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index('ix_agent_sessions_user_id', 'agent_sessions', ['user_id'])
    op.create_index('ix_agent_sessions_project_id', 'agent_sessions', ['project_id'])

    # agent_messages 表
    op.create_table(
        'agent_messages',
        sa.Column('id', sa.String(36), nullable=False),
        sa.Column('session_id', sa.String(36), sa.ForeignKey('agent_sessions.id'), nullable=False),
        sa.Column('role', sa.String(20), nullable=False),
        sa.Column('content', sa.Text, nullable=False),
        sa.Column('agent_type', sa.String(50), nullable=True),
        sa.Column('sequence', sa.Integer, nullable=False, server_default='0'),
        sa.Column('content_hash', sa.String(64), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index('ix_agent_messages_session_id', 'agent_messages', ['session_id'])

    # agent_feedbacks: 新增 session_id 外键字段
    op.execute(
        "ALTER TABLE agent_feedbacks ADD COLUMN session_id VARCHAR(36) REFERENCES agent_sessions(id)"
    )
    op.create_index('ix_agent_feedbacks_session_id', 'agent_feedbacks', ['session_id'])


def downgrade() -> None:
    op.drop_index('ix_agent_feedbacks_session_id', table_name='agent_feedbacks')
    op.execute("ALTER TABLE agent_feedbacks DROP COLUMN session_id")
    op.drop_index('ix_agent_messages_session_id', table_name='agent_messages')
    op.drop_table('agent_messages')
    op.drop_index('ix_agent_sessions_project_id', table_name='agent_sessions')
    op.drop_index('ix_agent_sessions_user_id', table_name='agent_sessions')
    op.drop_table('agent_sessions')

"""add a2a_tasks table

Revision ID: l3c4d5e6f7a8
Revises: k2b3c4d5e6f7
Create Date: 2026-07-25

v1.2.4 A2A 协议任务持久化：
  - 新增 a2a_tasks 表，存储 A2A Agent 间任务记录
  - 含 TTL 过期机制（expires_at 列 + 索引）
  - 替代原内存 dict 存储，进程重启不丢失
"""
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = "l3c4d5e6f7a8"
down_revision = "k2b3c4d5e6f7"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "a2a_tasks",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("task_id", sa.String(48), nullable=False, unique=True),
        sa.Column("agent_name", sa.String(30), nullable=False),
        sa.Column("message", sa.Text, nullable=False),
        sa.Column("project_id", sa.String(36), nullable=True),
        sa.Column("user_id", sa.String(36), nullable=True),
        sa.Column("state", sa.String(20), nullable=False, server_default="submitted"),
        sa.Column("result", sa.Text, nullable=True),
        sa.Column("error", sa.Text, nullable=True),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index("ix_a2a_tasks_task_id", "a2a_tasks", ["task_id"])
    op.create_index("ix_a2a_tasks_user_id", "a2a_tasks", ["user_id"])
    op.create_index("ix_a2a_tasks_expires_at", "a2a_tasks", ["expires_at"])


def downgrade():
    op.drop_index("ix_a2a_tasks_expires_at", table_name="a2a_tasks")
    op.drop_index("ix_a2a_tasks_user_id", table_name="a2a_tasks")
    op.drop_index("ix_a2a_tasks_task_id", table_name="a2a_tasks")
    op.drop_table("a2a_tasks")

"""add v1.1.27 perf indexes

Revision ID: j1a2b3c4d5e6
Revises: i9d0e1f2a3b4
Create Date: 2026-07-22

复合索引（3 个）：
  - construction_tasks (project_id, status) — timeline 端点高频查询
  - agent_messages (session_id, created_at) — chat 历史查询排序
  - audit_logs (user_id, created_at) — admin 审计查询

PG 用 CREATE INDEX CONCURRENTLY（不锁表），SQLite 用普通 CREATE INDEX。
回滚用 DROP INDEX CONCURRENTLY。
"""
from alembic import op

# revision identifiers, used by Alembic.
revision = "j1a2b3c4d5e6"
down_revision = "i9d0e1f2a3b4"
branch_labels = None
depends_on = None

# 复合索引定义：(索引名, 表名, [列名])
_INDEXES = [
    ("ix_construction_tasks_project_id_status", "construction_tasks",
     ["project_id", "status"]),
    ("ix_agent_messages_session_id_created_at", "agent_messages",
     ["session_id", "created_at"]),
    ("ix_audit_logs_user_id_created_at", "audit_logs",
     ["user_id", "created_at"]),
]


def upgrade():
    """添加性能复合索引。

    PG 用 CONCURRENTLY（不锁表），SQLite 用普通 CREATE INDEX。
    """
    bind = op.get_bind()
    is_pg = bind.dialect.name == "postgresql"

    for idx_name, table, columns in _INDEXES:
        cols_str = ", ".join(columns)
        if is_pg:
            # CONCURRENTLY 不能在事务中执行，需要 autocommit_block
            with op.get_context().autocommit_block():
                op.execute(
                    f"CREATE INDEX CONCURRENTLY IF NOT EXISTS "
                    f"{idx_name} ON {table} ({cols_str})"
                )
        else:
            op.create_index(
                idx_name, table, columns, if_not_exists=True
            )


def downgrade():
    """删除性能复合索引。"""
    bind = op.get_bind()
    is_pg = bind.dialect.name == "postgresql"

    for idx_name, _table, _columns in _INDEXES:
        if is_pg:
            with op.get_context().autocommit_block():
                op.execute(
                    f"DROP INDEX CONCURRENTLY IF EXISTS {idx_name}"
                )
        else:
            op.drop_index(idx_name, if_exists=True)

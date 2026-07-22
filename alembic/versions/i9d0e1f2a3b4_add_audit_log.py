"""v1.2.0: 审计日志 — 新增 audit_logs 表

Revision ID: i9d0e1f2a3b4
Revises: h8c9d0e1f2a3
Create Date: 2026-07-21 10:00:00.000000

新增 audit_logs 表用于记录敏感操作审计日志：
- 字段：id (UUID), user_id, action, resource_type, resource_id (nullable),
        details (JSON), request_ip, user_agent (nullable), created_at
- 索引：user_id, action, resource_type, created_at
- 不建立外键约束（审计日志独立于业务表，避免级联影响）

迁移采用幂等设计：使用 inspect 检查表/索引存在性后再决定是否创建，
可在生产环境安全重复执行（与 h8c9d0e1f2a3_add_agent_sessions.py 风格一致）。
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'i9d0e1f2a3b4'
down_revision: Union[str, None] = 'h8c9d0e1f2a3'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


# 表名与索引规范
_TABLE_NAME = 'audit_logs'
_INDEXES: list[tuple[str, str]] = [
    # (index_name, column_name)
    ('ix_audit_logs_user_id', 'user_id'),
    ('ix_audit_logs_action', 'action'),
    ('ix_audit_logs_resource_type', 'resource_type'),
    ('ix_audit_logs_created_at', 'created_at'),
]


def upgrade() -> None:
    conn = op.get_bind()
    inspector = sa.inspect(conn)

    # 幂等检查：表已存在则跳过创建
    if inspector.has_table(_TABLE_NAME):
        print(f"  skip: table {_TABLE_NAME} already exists")
    else:
        op.create_table(
            _TABLE_NAME,
            sa.Column('id', sa.String(36), nullable=False),
            sa.Column('user_id', sa.String(36), nullable=False),
            sa.Column('action', sa.String(32), nullable=False),
            sa.Column('resource_type', sa.String(64), nullable=False),
            sa.Column('resource_id', sa.String(64), nullable=True),
            sa.Column('details', sa.JSON, nullable=True),
            sa.Column('request_ip', sa.String(64), nullable=False),
            sa.Column('user_agent', sa.String(500), nullable=True),
            sa.Column(
                'created_at',
                sa.DateTime(timezone=True),
                server_default=sa.func.now(),
                nullable=False,
            ),
            sa.PrimaryKeyConstraint('id'),
        )
        print(f"  created: table {_TABLE_NAME}")

    # 幂等检查：索引已存在则跳过创建
    existing_indexes: set[str] = set()
    if inspector.has_table(_TABLE_NAME):
        for idx in inspector.get_indexes(_TABLE_NAME):
            if idx.get('name'):
                existing_indexes.add(idx['name'])

    created_indexes = 0
    skipped_indexes = 0
    for index_name, column_name in _INDEXES:
        if index_name in existing_indexes:
            skipped_indexes += 1
            continue
        try:
            op.create_index(index_name, _TABLE_NAME, [column_name])
            created_indexes += 1
        except Exception as e:
            print(f"  skip index {index_name}: {e}")
            skipped_indexes += 1

    print(
        f"\n  audit_logs: indexes created={created_indexes}, skipped={skipped_indexes}, "
        f"total={len(_INDEXES)}"
    )


def downgrade() -> None:
    conn = op.get_bind()
    inspector = sa.inspect(conn)

    # 幂等删除索引
    existing_indexes: set[str] = set()
    if inspector.has_table(_TABLE_NAME):
        for idx in inspector.get_indexes(_TABLE_NAME):
            if idx.get('name'):
                existing_indexes.add(idx['name'])

    for index_name, _column_name in _INDEXES:
        if index_name in existing_indexes:
            try:
                op.drop_index(index_name, table_name=_TABLE_NAME)
            except Exception as e:
                print(f"  skip drop {index_name}: {e}")

    # 幂等删除表
    if inspector.has_table(_TABLE_NAME):
        op.drop_table(_TABLE_NAME)

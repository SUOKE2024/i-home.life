"""v1.4.x: Agent 记忆作用域 — agent_memories 表新增 scope / project_id 列

Revision ID: j0f5a9c2d4e6
Revises: o6f7a8b9c0d1
Create Date: 2026-08-02 12:00:00.000000

借鉴 YC QM 的 Scope 设计：给长期记忆增加归属维度
（personal/project/team/org），避免项目/团队间记忆与上下文污染。
新增列：
- scope: 记忆作用域（personal=默认 / project / team / org），NOT NULL DEFAULT 'personal'
- project_id: scope=project 时记录所属项目（可空），用于项目维度隔离查询

迁移采用幂等设计（与 i9d0e1f2a3b4_add_audit_log.py 风格一致）：
用 inspect 检查列存在性后再决定是否添加，可在生产环境安全重复执行。
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'j0f5a9c2d4e6'
down_revision: Union[str, None] = 'o6f7a8b9c0d1'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

_TABLE_NAME = 'agent_memories'
_COLUMNS = [
    ('scope', 'varchar(20)'),
    ('project_id', 'varchar(36)'),
]
_INDEXES: list[tuple[str, str]] = [
    ('ix_agent_memories_user_id', 'user_id'),
    ('ix_agent_memories_scope', 'scope'),
    ('ix_agent_memories_project_id', 'project_id'),
]


def _create_full_table() -> None:
    """agent_memories 此前无独立 migration，此处完整建表（含 scope/project_id）。"""
    op.create_table(
        _TABLE_NAME,
        sa.Column('id', sa.String(36), nullable=False),
        sa.Column('user_id', sa.String(36), nullable=False),
        sa.Column('category', sa.String(30), nullable=False, server_default='fact'),
        sa.Column('memory_key', sa.String(100), nullable=False),
        sa.Column('memory_value', sa.Text(), nullable=False),
        sa.Column('scope', sa.String(20), nullable=False, server_default='personal'),
        sa.Column('project_id', sa.String(36), nullable=True),
        sa.Column('source', sa.String(50), nullable=True),
        sa.Column('importance', sa.Integer(), nullable=False, server_default='1'),
        sa.Column('access_count', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('last_accessed_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            'created_at', sa.DateTime(timezone=True),
            server_default=sa.func.now(), nullable=False,
        ),
        sa.Column(
            'updated_at', sa.DateTime(timezone=True),
            server_default=sa.func.now(), nullable=False,
        ),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint(
            'user_id', 'category', 'scope', 'project_id', 'memory_key',
            name='uq_agent_memory_user_cat_scope_key',
        ),
    )
    for index_name, column_name in _INDEXES:
        op.create_index(index_name, _TABLE_NAME, [column_name])
    print(f"  created: table {_TABLE_NAME} (完整建表，含 scope/project_id)")


def _ensure_columns(inspector) -> None:
    """已有表补列（幂等）。"""
    existing_columns = {c['name'] for c in inspector.get_columns(_TABLE_NAME)}
    for col_name, _col_type in _COLUMNS:
        if col_name in existing_columns:
            print(f"  skip: column {_TABLE_NAME}.{col_name} already exists")
            continue
        if col_name == 'scope':
            op.add_column(
                _TABLE_NAME,
                sa.Column('scope', sa.String(20), nullable=False, server_default='personal'),
            )
        else:
            op.add_column(
                _TABLE_NAME,
                sa.Column('project_id', sa.String(36), nullable=True),
            )
        print(f"  added: column {_TABLE_NAME}.{col_name}")


def _ensure_indexes(inspector) -> int:
    """幂等创建索引，返回新建数量。"""
    existing_indexes: set[str] = set()
    for idx in inspector.get_indexes(_TABLE_NAME):
        if idx.get('name'):
            existing_indexes.add(idx['name'])
    created = 0
    for index_name, column_name in _INDEXES:
        if index_name in existing_indexes:
            continue
        try:
            op.create_index(index_name, _TABLE_NAME, [column_name])
            created += 1
        except Exception as e:
            print(f"  skip index {index_name}: {e}")
    return created


def _ensure_unique_constraint(inspector) -> None:
    """幂等更新唯一约束：旧 3 列 → 新 5 列（含 scope/project_id）。"""
    existing_unique = {uc.get('name') for uc in inspector.get_unique_constraints(_TABLE_NAME)}
    if 'uq_agent_memory_user_cat_scope_key' not in existing_unique:
        try:
            if 'uq_agent_memory_user_cat_key' in existing_unique:
                op.drop_constraint('uq_agent_memory_user_cat_key', _TABLE_NAME, type_='unique')
            op.create_unique_constraint(
                'uq_agent_memory_user_cat_scope_key', _TABLE_NAME,
                ['user_id', 'category', 'scope', 'project_id', 'memory_key'],
            )
            print("  updated: unique constraint -> uq_agent_memory_user_cat_scope_key")
        except Exception as e:
            print(f"  skip unique constraint update: {e}")


def upgrade() -> None:
    conn = op.get_bind()
    inspector = sa.inspect(conn)

    if not inspector.has_table(_TABLE_NAME):
        _create_full_table()
        return
    _ensure_columns(inspector)
    created = _ensure_indexes(inspector)
    _ensure_unique_constraint(inspector)
    print(f"\n  {_TABLE_NAME}: indexes created={created}")


def downgrade() -> None:
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    if not inspector.has_table(_TABLE_NAME):
        return

    existing_columns = {c['name'] for c in inspector.get_columns(_TABLE_NAME)}
    for col_name, _col_type in _COLUMNS:
        if col_name in existing_columns:
            try:
                op.drop_column(_TABLE_NAME, col_name)
            except Exception as e:
                print(f"  skip drop {_TABLE_NAME}.{col_name}: {e}")

    existing_indexes: set[str] = set()
    for idx in inspector.get_indexes(_TABLE_NAME):
        if idx.get('name'):
            existing_indexes.add(idx['name'])
    for index_name, _column_name in _INDEXES:
        if index_name in existing_indexes:
            try:
                op.drop_index(index_name, table_name=_TABLE_NAME)
            except Exception as e:
                print(f"  skip drop {index_name}: {e}")

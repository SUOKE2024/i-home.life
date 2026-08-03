"""v1.4.x: B2B 交付单对接真实项目 — delivery_orders 表新增 project_id 列

Revision ID: q1f2e3d4c5b6
Revises: p0e1d2c3b4a5
Create Date: 2026-08-02 16:00:00.000000

交付单可关联真实装修项目（project_id）：
- 报价档基于项目真实 Budget/BudgetLine（source=db），无项目数据时诚实降级估算
- 归属校验：仅项目 owner / admin 可关联

迁移采用幂等设计，生产环境可安全重复执行。
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'q1f2e3d4c5b6'
down_revision: Union[str, None] = 'p0e1d2c3b4a5'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

_TABLE_NAME = 'delivery_orders'
_COLUMN = 'project_id'
_INDEX = ('ix_delivery_orders_project_id', 'project_id')


def upgrade() -> None:
    conn = op.get_bind()
    inspector = sa.inspect(conn)

    if not inspector.has_table(_TABLE_NAME):
        print(f"  skip: table {_TABLE_NAME} does not exist")
        return

    existing_columns = {c['name'] for c in inspector.get_columns(_TABLE_NAME)}
    if _COLUMN not in existing_columns:
        op.add_column(_TABLE_NAME, sa.Column(_COLUMN, sa.String(36), nullable=True))
        print(f"  added: column {_TABLE_NAME}.{_COLUMN}")

    existing_indexes: set[str] = set()
    for idx in inspector.get_indexes(_TABLE_NAME):
        if idx.get('name'):
            existing_indexes.add(idx['name'])
    if _INDEX[0] not in existing_indexes:
        try:
            op.create_index(_INDEX[0], _TABLE_NAME, [_INDEX[1]])
            print(f"  created: index {_INDEX[0]}")
        except Exception as e:
            print(f"  skip index {_INDEX[0]}: {e}")


def downgrade() -> None:
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    if not inspector.has_table(_TABLE_NAME):
        return
    existing_indexes: set[str] = set()
    for idx in inspector.get_indexes(_TABLE_NAME):
        if idx.get('name'):
            existing_indexes.add(idx['name'])
    if _INDEX[0] in existing_indexes:
        try:
            op.drop_index(_INDEX[0], table_name=_TABLE_NAME)
        except Exception as e:
            print(f"  skip drop {_INDEX[0]}: {e}")
    existing_columns = {c['name'] for c in inspector.get_columns(_TABLE_NAME)}
    if _COLUMN in existing_columns:
        try:
            op.drop_column(_TABLE_NAME, _COLUMN)
        except Exception as e:
            print(f"  skip drop {_TABLE_NAME}.{_COLUMN}: {e}")

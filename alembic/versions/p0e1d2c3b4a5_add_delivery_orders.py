"""v1.4.x: B2B 交付单 — 新增 delivery_orders 表

Revision ID: p0e1d2c3b4a5
Revises: j0f5a9c2d4e6
Create Date: 2026-08-02 14:00:00.000000

借鉴"卖结果不卖功能"的交付式产品：将 /api/b2b/delivery 生成的整包
（设计方案+报价+施工计划）订单化持久化，支持状态流转与追溯。
- 字段：id, user_id, name, area, style, budget, requirements,
        status, summary, proposals(JSON), budget_estimate(JSON),
        construction_plan(JSON), sources(JSON), created_at, updated_at
- 索引：user_id, status
- 状态机在 app/models/delivery_order.py 定义（draft/quoted/accepted/
  in_construction/completed/cancelled）

迁移采用幂等设计（与既有迁移风格一致），生产环境可安全重复执行。
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'p0e1d2c3b4a5'
down_revision: Union[str, None] = 'j0f5a9c2d4e6'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

_TABLE_NAME = 'delivery_orders'
_INDEXES: list[tuple[str, str]] = [
    ('ix_delivery_orders_user_id', 'user_id'),
    ('ix_delivery_orders_status', 'status'),
]


def upgrade() -> None:
    conn = op.get_bind()
    inspector = sa.inspect(conn)

    if inspector.has_table(_TABLE_NAME):
        print(f"  skip: table {_TABLE_NAME} already exists")
        return

    op.create_table(
        _TABLE_NAME,
        sa.Column('id', sa.String(36), nullable=False),
        sa.Column('user_id', sa.String(36), nullable=False),
        sa.Column('name', sa.String(200), nullable=False, server_default='整装交付'),
        sa.Column('area', sa.Float(), nullable=False),
        sa.Column('style', sa.String(50), nullable=False, server_default='modern'),
        sa.Column('budget', sa.Float(), nullable=False, server_default='0'),
        sa.Column('requirements', sa.Text(), nullable=False, server_default=''),
        sa.Column('status', sa.String(20), nullable=False, server_default='draft'),
        sa.Column('summary', sa.Text(), nullable=True),
        sa.Column('proposals', sa.JSON, nullable=True),
        sa.Column('budget_estimate', sa.JSON, nullable=True),
        sa.Column('construction_plan', sa.JSON, nullable=True),
        sa.Column('sources', sa.JSON, nullable=True),
        sa.Column(
            'created_at', sa.DateTime(timezone=True),
            server_default=sa.func.now(), nullable=False,
        ),
        sa.Column(
            'updated_at', sa.DateTime(timezone=True),
            server_default=sa.func.now(), nullable=False,
        ),
        sa.PrimaryKeyConstraint('id'),
    )
    print(f"  created: table {_TABLE_NAME}")

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
    print(f"  {_TABLE_NAME}: indexes created={created}")


def downgrade() -> None:
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    if not inspector.has_table(_TABLE_NAME):
        return
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
    op.drop_table(_TABLE_NAME)

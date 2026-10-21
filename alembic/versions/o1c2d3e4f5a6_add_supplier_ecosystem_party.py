"""suppliers 增 ecosystem_party_id — 跨品牌供应商主数据映射

Revision ID: o1c2d3e4f5a6
Revises: n8b9c0d1e2f3
Create Date: 2026-10-21

canonical party 由索克生活 product-service 的 ecosystem_supplier_parties 签发；
本表只保存映射键，不复制资质/结算数据。

幂等：列已存在则跳过。
回滚：drop index + drop column（SQLite 走 batch）。
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "o1c2d3e4f5a6"
down_revision: Union[str, None] = "n8b9c0d1e2f3"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

_TABLE = "suppliers"
_COLUMN = "ecosystem_party_id"
_INDEX = f"ix_{_TABLE}_{_COLUMN}"


def _has_column() -> bool:
    inspector = sa.inspect(op.get_bind())
    try:
        return _COLUMN in {c["name"] for c in inspector.get_columns(_TABLE)}
    except Exception:
        return False


def upgrade() -> None:
    if _has_column():
        print(f"  skip: {_TABLE}.{_COLUMN} already exists")
        return
    op.add_column(_TABLE, sa.Column(_COLUMN, sa.String(36), nullable=True))
    op.create_index(_INDEX, _TABLE, [_COLUMN])
    print(f"  added: {_TABLE}.{_COLUMN}")


def downgrade() -> None:
    if not _has_column():
        print(f"  skip: {_TABLE}.{_COLUMN} not exists")
        return
    op.drop_index(_INDEX, table_name=_TABLE)
    with op.batch_alter_table(_TABLE) as batch_op:
        batch_op.drop_column(_COLUMN)
    print(f"  dropped: {_TABLE}.{_COLUMN}")

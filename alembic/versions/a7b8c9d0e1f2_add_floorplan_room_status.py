"""空间即导航: floor_plans 补 room_status 逐房间状态列

Revision ID: a7b8c9d0e1f2
Revises: c0d1e2f3a4b5
Create Date: 2026-08-11

「空间即导航」——户型图逐房间状态打通：
- floor_plans 新增 room_status TEXT 列（JSON 字符串，形如 {"客厅": "in_progress"}）
  取值：not_started(未开始) / in_progress(施工中) / completed(已完成) / attention(需关注)

特性：
  - 幂等：has_column 检查，生产可安全重复执行
  - NOT NULL 列带 server_default，存量行获得默认值 '{}'
  - SQLite batch mode 兼容
"""
from typing import Sequence, Union

import logging

from alembic import op
import sqlalchemy as sa

logger = logging.getLogger("alembic.runtime.migration")


# revision identifiers, used by Alembic.
revision: str = "a7b8c9d0e1f2"
down_revision: Union[str, None] = "c0d1e2f3a4b5"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

_TABLE = "floor_plans"
_COLUMN = "room_status"


def _has_column(table: str, column_name: str) -> bool:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    try:
        cols = [c["name"] for c in inspector.get_columns(table)]
    except Exception:
        return True  # 表不存在视为已处理，避免报错
    return column_name in cols


def upgrade() -> None:
    bind = op.get_bind()
    logger.info("[%s] upgrade start: dialect=%s", revision, bind.dialect.name)

    if _has_column(_TABLE, _COLUMN):
        logger.info("[%s] skip: %s.%s already exists", revision, _TABLE, _COLUMN)
        logger.info("[%s] upgrade done", revision)
        return

    col = sa.Column(
        _COLUMN, sa.Text(), nullable=False, server_default=sa.text("'{}'")
    )
    if bind.dialect.name == "sqlite":
        with op.batch_alter_table(_TABLE) as batch_op:
            batch_op.add_column(col)
    else:
        op.add_column(_TABLE, col)
    logger.info("[%s] added: %s.%s", revision, _TABLE, _COLUMN)
    logger.info("[%s] upgrade done", revision)


def downgrade() -> None:
    bind = op.get_bind()
    is_sqlite = bind.dialect.name == "sqlite"
    logger.info("[%s] downgrade start: dialect=%s", revision, bind.dialect.name)

    if not _has_column(_TABLE, _COLUMN):
        logger.info("[%s] skip: %s.%s not exists", revision, _TABLE, _COLUMN)
        logger.info("[%s] downgrade done", revision)
        return

    if is_sqlite:
        with op.batch_alter_table(_TABLE) as batch_op:
            batch_op.drop_column(_COLUMN)
    else:
        op.drop_column(_TABLE, _COLUMN)
    logger.info("[%s] dropped: %s.%s", revision, _TABLE, _COLUMN)
    logger.info("[%s] downgrade done", revision)

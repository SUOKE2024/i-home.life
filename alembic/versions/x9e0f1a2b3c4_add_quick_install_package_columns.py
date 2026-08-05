"""F49 局改快装产品化: partial_renovation_plans 补标准套餐字段

Revision ID: x9e0f1a2b3c4
Revises: w8d9e0f1a2b3
Create Date: 2026-08-04

F49 局改快装产品化（PRD v3.1，2026-08-03 行业调研新增）：
- 48h 厨卫换新 / 7 天墙面焕新标准化套餐 + 干法施工 + 0 搬家
- partial_renovation_plans 补 package_code / fixed_price / dry_construction / zero_relocation

特性：
  - 幂等：has_column 检查，生产可安全重复执行
  - NOT NULL 布尔列带 server_default，存量行获得默认值
  - SQLite batch mode 兼容
"""
from typing import Sequence, Union

import logging

from alembic import op
import sqlalchemy as sa

# 复用 alembic 内置 logger 命名空间：随 alembic 命令输出，无需额外配置
logger = logging.getLogger("alembic.runtime.migration")


# revision identifiers, used by Alembic.
revision: str = "x9e0f1a2b3c4"
down_revision: Union[str, None] = "w8d9e0f1a2b3"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

_TABLE = "partial_renovation_plans"


def _has_column(table: str, column_name: str) -> bool:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    try:
        cols = [c["name"] for c in inspector.get_columns(table)]
    except Exception:
        return True  # 表不存在视为已处理，避免报错
    return column_name in cols


def _has_index(table: str, index_name: str) -> bool:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    try:
        return any(ix["name"] == index_name for ix in inspector.get_indexes(table))
    except Exception:
        return False


def _has_table(table: str) -> bool:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    try:
        return table in inspector.get_table_names()
    except Exception:
        return False


def _add_column(table: str, col: sa.Column) -> None:
    bind = op.get_bind()
    if bind.dialect.name == "sqlite":
        with op.batch_alter_table(table) as batch_op:
            batch_op.add_column(col)
    else:
        op.add_column(table, col)


def upgrade() -> None:
    bind = op.get_bind()
    logger.info("[%s] upgrade start: dialect=%s", revision, bind.dialect.name)

    if not _has_column(_TABLE, "package_code"):
        _add_column(_TABLE, sa.Column("package_code", sa.String(32), nullable=True))
        op.create_index("ix_partial_renovation_plans_package_code", _TABLE, ["package_code"])
        logger.info("[%s] added: %s.package_code (+index)", revision, _TABLE)
    else:
        logger.info("[%s] skip: %s.package_code already exists", revision, _TABLE)
    if not _has_column(_TABLE, "fixed_price"):
        _add_column(_TABLE, sa.Column("fixed_price", sa.Float(), nullable=True))
        logger.info("[%s] added: %s.fixed_price", revision, _TABLE)
    else:
        logger.info("[%s] skip: %s.fixed_price already exists", revision, _TABLE)
    if not _has_column(_TABLE, "dry_construction"):
        _add_column(
            _TABLE,
            sa.Column("dry_construction", sa.Boolean(), nullable=False, server_default=sa.false()),
        )
        logger.info("[%s] added: %s.dry_construction", revision, _TABLE)
    else:
        logger.info("[%s] skip: %s.dry_construction already exists", revision, _TABLE)
    if not _has_column(_TABLE, "zero_relocation"):
        _add_column(
            _TABLE,
            sa.Column("zero_relocation", sa.Boolean(), nullable=False, server_default=sa.false()),
        )
        logger.info("[%s] added: %s.zero_relocation", revision, _TABLE)
    else:
        logger.info("[%s] skip: %s.zero_relocation already exists", revision, _TABLE)
    logger.info("[%s] upgrade done", revision)


def downgrade() -> None:
    bind = op.get_bind()
    is_sqlite = bind.dialect.name == "sqlite"
    logger.info("[%s] downgrade start: dialect=%s", revision, bind.dialect.name)
    # 表可能不存在（partial_renovation_plans 由 model/create_all 建，空库 migration 链
    # 从未建表——2026-08-06 空库 downgrade base 实测 NoSuchTableError），先跳过
    if not _has_table(_TABLE):
        logger.info("[%s] skip: table %s not exists", revision, _TABLE)
        logger.info("[%s] downgrade done", revision)
        return
    # package_code 带索引 ix_partial_renovation_plans_package_code：SQLite batch 重建表时
    # 必须先删索引，否则报 no such column: package_code（2026-08-06 本地实测复现）
    if _has_index(_TABLE, "ix_partial_renovation_plans_package_code"):
        op.drop_index("ix_partial_renovation_plans_package_code", table_name=_TABLE)
        logger.info("[%s] dropped index: ix_partial_renovation_plans_package_code", revision)
    for column in ("zero_relocation", "dry_construction", "fixed_price", "package_code"):
        if not _has_column(_TABLE, column):
            logger.info("[%s] skip: %s.%s not exists", revision, _TABLE, column)
            continue
        if is_sqlite:
            with op.batch_alter_table(_TABLE) as batch_op:
                batch_op.drop_column(column)
        else:
            op.drop_column(_TABLE, column)
        logger.info("[%s] dropped: %s.%s", revision, _TABLE, column)
    logger.info("[%s] downgrade done", revision)

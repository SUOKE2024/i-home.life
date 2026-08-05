"""F50 一板一码溯源: material_eco_certs 补 henf_grade + 新增 material_board_traces 表

Revision ID: w8d9e0f1a2b3
Revises: v7c8d9e0f1a2
Create Date: 2026-08-04

F50 板材全链路溯源（PRD v3.1，2026-08-03 行业调研新增）：
- material_eco_certs 补 henf_grade（HENF 无醛最高级预埋，GB18580-2025 强制 + HENF 新标准）
- 新增 material_board_traces 表（一板一码：产地/批次/物流/环保等级）

特性：
  - 幂等：has_column / 表存在性检查，生产可安全重复执行
  - NOT NULL 列带 server_default，存量行获得默认值
  - SQLite batch mode 兼容
"""
from typing import Sequence, Union

import logging

from alembic import op
import sqlalchemy as sa

# 复用 alembic 内置 logger 命名空间：随 alembic 命令输出，无需额外配置
logger = logging.getLogger("alembic.runtime.migration")


# revision identifiers, used by Alembic.
revision: str = "w8d9e0f1a2b3"
down_revision: Union[str, None] = "v7c8d9e0f1a2"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

_CERT_TABLE = "material_eco_certs"
_BOARD_TABLE = "material_board_traces"


def _has_column(table: str, column_name: str) -> bool:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    try:
        cols = [c["name"] for c in inspector.get_columns(table)]
    except Exception:
        return True  # 表不存在视为已处理，避免报错
    return column_name in cols


def _has_table(table: str) -> bool:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    try:
        return table in inspector.get_table_names()
    except Exception:
        return True


def _has_index(table: str, index_name: str) -> bool:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    try:
        return any(ix["name"] == index_name for ix in inspector.get_indexes(table))
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

    # 1) material_eco_certs 补 henf_grade（幂等）
    if not _has_column(_CERT_TABLE, "henf_grade"):
        _add_column(
            _CERT_TABLE,
            sa.Column("henf_grade", sa.String(10), nullable=True, index=True),
        )
        logger.info("[%s] added: %s.henf_grade", revision, _CERT_TABLE)
    else:
        logger.info("[%s] skip: %s.henf_grade already exists", revision, _CERT_TABLE)

    # 2) 新增 material_board_traces 表（幂等）
    if _has_table(_BOARD_TABLE):
        logger.info("[%s] skip: %s already exists", revision, _BOARD_TABLE)
        logger.info("[%s] upgrade done", revision)
        return
    op.create_table(
        _BOARD_TABLE,
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("board_code", sa.String(64), nullable=False),
        sa.Column("material_id", sa.String(36), nullable=False),
        sa.Column("batch_no", sa.String(64), nullable=False, server_default=""),
        sa.Column("origin", sa.String(100), nullable=False, server_default=""),
        sa.Column("vendor", sa.String(100), nullable=False, server_default=""),
        sa.Column("produced_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("logistics", sa.JSON(), nullable=True),
        sa.Column("henf_grade", sa.String(10), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False,
                  server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.ForeignKeyConstraint(["material_id"], ["materials.id"]),
        sa.UniqueConstraint("board_code", name="uq_material_board_traces_board_code"),
    )
    op.create_index("ix_material_board_traces_board_code", _BOARD_TABLE, ["board_code"])
    op.create_index("ix_material_board_traces_material_id", _BOARD_TABLE, ["material_id"])
    op.create_index("ix_material_board_traces_henf_grade", _BOARD_TABLE, ["henf_grade"])
    logger.info("[%s] created: %s (+3 indexes)", revision, _BOARD_TABLE)
    logger.info("[%s] upgrade done", revision)


def downgrade() -> None:
    bind = op.get_bind()
    is_sqlite = bind.dialect.name == "sqlite"
    logger.info("[%s] downgrade start: dialect=%s", revision, bind.dialect.name)

    if _has_table(_BOARD_TABLE):
        # 整表删除直接 DROP TABLE：BatchOperations 无 drop_table（SQLite 下 batch 仅用于列级操作）
        op.drop_table(_BOARD_TABLE)
        logger.info("[%s] dropped: %s", revision, _BOARD_TABLE)
    else:
        logger.info("[%s] skip: %s not exists", revision, _BOARD_TABLE)

    if _has_column(_CERT_TABLE, "henf_grade"):
        # henf_grade 在 upgrade 中由 sa.Column(index=True) 隐式建索引，先删索引防 SQLite 重建表报错
        if _has_index(_CERT_TABLE, "ix_material_eco_certs_henf_grade"):
            op.drop_index("ix_material_eco_certs_henf_grade", table_name=_CERT_TABLE)
            logger.info("[%s] dropped index: ix_material_eco_certs_henf_grade", revision)
        if is_sqlite:
            with op.batch_alter_table(_CERT_TABLE) as batch_op:
                batch_op.drop_column("henf_grade")
        else:
            op.drop_column(_CERT_TABLE, "henf_grade")
        logger.info("[%s] dropped: %s.henf_grade", revision, _CERT_TABLE)
    else:
        logger.info("[%s] skip: %s.henf_grade not exists", revision, _CERT_TABLE)
    logger.info("[%s] downgrade done", revision)

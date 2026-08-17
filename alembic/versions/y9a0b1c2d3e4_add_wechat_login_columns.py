"""微信开放平台登录：users 表 wechat_openid/wechat_unionid + phone 可空

Revision ID: y9a0b1c2d3e4
Revises: z8a9b0c1d2e3
Create Date: 2026-08-17

背景：微信扫码登录用户无手机号（openid 为唯一身份标识），需 users.phone 放开
NOT NULL；wechat_openid 唯一防并发重复建号。

设计：
  - 幂等：_has_column 守卫，已存在 skip；唯一索引 _has_index 守卫
  - phone DROP NOT NULL：PG 直接 alter_column；SQLite 用 batch 重建表
    （与 y0f1a2b3c4d5 projects.phase 同模式，保证空库基线 nullability 与生产
    一致——scripts/compare_db_schema.py 的列对比含 nullable，不一致会触发
    每日 schema-compare 失败）
  - downgrade 非破坏性：仅删本迁移新增的索引与列；phone NOT NULL 不回滚
    （微信用户 phone=NULL，恢复约束会导致存量数据违反）
"""
from typing import Sequence, Union

import logging

from alembic import op
import sqlalchemy as sa

logger = logging.getLogger("alembic.runtime.migration")


# revision identifiers, used by Alembic.
revision: str = "y9a0b1c2d3e4"
down_revision: Union[str, None] = "d2e3f4a5b6c7"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

_TABLE = "users"
_OPENID_INDEX = "ix_users_wechat_openid"


def _has_column(table: str, column_name: str) -> bool:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    try:
        cols = [c["name"] for c in inspector.get_columns(table)]
    except Exception:
        return True
    return column_name in cols


def _has_index(table: str, index_name: str) -> bool:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    try:
        indexes = [i["name"] for i in inspector.get_indexes(table)]
    except Exception:
        return True
    return index_name in indexes


def upgrade() -> None:
    bind = op.get_bind()
    dialect = bind.dialect.name
    logger.info("[%s] upgrade start: dialect=%s", revision, dialect)

    # 1) 补列（幂等）
    if not _has_column(_TABLE, "wechat_openid"):
        op.add_column(_TABLE, sa.Column("wechat_openid", sa.String(64), nullable=True))
        logger.info("[%s] added: %s.wechat_openid", revision, _TABLE)
    if not _has_column(_TABLE, "wechat_unionid"):
        op.add_column(_TABLE, sa.Column("wechat_unionid", sa.String(64), nullable=True))
        logger.info("[%s] added: %s.wechat_unionid", revision, _TABLE)

    # 2) openid 唯一索引（防并发重复建号；NULL 不参与唯一冲突）
    if not _has_index(_TABLE, _OPENID_INDEX):
        op.create_index(_OPENID_INDEX, _TABLE, ["wechat_openid"], unique=True)
        logger.info("[%s] created unique index: %s", revision, _OPENID_INDEX)

    # 3) phone 放开 NOT NULL（PG 直接 alter；SQLite 用 batch 重建表——
    #    与 y0f1a2b3c4d5 projects.phase 同模式，保证空库基线 nullability
    #    与生产一致，否则每日 schema-compare 会报差异）
    if dialect == "sqlite":
        with op.batch_alter_table(_TABLE) as batch_op:
            batch_op.alter_column("phone", existing_type=sa.String(20), nullable=True)
    else:
        op.alter_column(_TABLE, "phone", existing_type=sa.String(20), nullable=True)
    logger.info("[%s] altered: %s.phone nullable=True (dialect=%s)", revision, _TABLE, dialect)


def downgrade() -> None:
    bind = op.get_bind()
    dialect = bind.dialect.name
    logger.info("[%s] downgrade start: dialect=%s", revision, dialect)

    # 删索引 + 列；phone NOT NULL 不回滚（见 docstring）
    if _has_index(_TABLE, _OPENID_INDEX):
        op.drop_index(_OPENID_INDEX, table_name=_TABLE)
    if _has_column(_TABLE, "wechat_openid"):
        if dialect == "sqlite":
            with op.batch_alter_table(_TABLE) as batch_op:
                batch_op.drop_column("wechat_openid")
        else:
            op.drop_column(_TABLE, "wechat_openid")
    if _has_column(_TABLE, "wechat_unionid"):
        if dialect == "sqlite":
            with op.batch_alter_table(_TABLE) as batch_op:
                batch_op.drop_column("wechat_unionid")
        else:
            op.drop_column(_TABLE, "wechat_unionid")
    logger.info("[%s] downgrade done (phone constraint intentionally kept)", revision)

"""补齐 v1.6.0 F40 业务列（alembic 迁移链遗漏，运行时轻量迁移已覆盖）

Revision ID: z8a9b0c1d2e3
Revises: z7a8b9c0d1e2
Create Date: 2026-08-06

背景（2026-08-06 全景验证三方交叉核验：Base.metadata vs 空库迁移链 vs 真实库）：
- chat_rooms.agent_members / chat_messages.auto_reply_meta / bom_items.quantity_source /
  bom_items.fallback_note 为 v1.6.0 F40 真实业务字段（Agent 群成员 / Agent 自动回复标注 /
  几何算量诚实标注），model 声明、真实库由 app/database.py 运行时轻量迁移
  （_SCHEMA_MIGRATION_VERSION=7, _schema_migrations 表）ALTER TABLE 补列。
- 但 alembic 迁移链从未收录这 4 列（init 建表无此列，后续迁移未 add_column；
  z7a8b9c0d1e2 仅补了同批的 bom_items.version）→ 空库（CI/新环境）upgrade head
  后缺列，check_schema_drift exit=1。

设计（与 z7a8b9c0d1e2 同策略）：
  - upgrade 幂等：_has_column 守卫，已存在 skip
  - DDL 与运行时迁移一致（quantity_source VARCHAR(30) NOT NULL DEFAULT 'empirical' /
    fallback_note VARCHAR(500) / auto_reply_meta TEXT / agent_members TEXT NOT NULL DEFAULT '[]'）
  - downgrade 不删列：与 bom_items.version 处理一致（业务活跃字段，删列破坏性大，
    upgrade 时 _has_column 幂等 skip）
"""
from typing import Sequence, Union

import logging

from alembic import op
import sqlalchemy as sa

# 复用 alembic 内置 logger 命名空间：随 alembic 命令输出，无需额外配置
logger = logging.getLogger("alembic.runtime.migration")


# revision identifiers, used by Alembic.
revision: str = "z8a9b0c1d2e3"
down_revision: Union[str, None] = "z7a8b9c0d1e2"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

# ── 补列（model 有、空库无；幂等 _has_column；DDL 对齐运行时轻量迁移）──
# (表, 列, 类型, nullable, server_default)
_ADD_COLUMNS = [
    ("bom_items", "quantity_source", sa.String(30), False, "empirical"),
    ("bom_items", "fallback_note", sa.String(500), True, None),
    ("chat_messages", "auto_reply_meta", sa.Text(), True, None),
    ("chat_rooms", "agent_members", sa.Text(), False, "[]"),
]


def _has_column(table: str, column: str) -> bool:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    try:
        return column in [c["name"] for c in inspector.get_columns(table)]
    except Exception:
        return False


def upgrade() -> None:
    bind = op.get_bind()
    logger.info("[%s] upgrade start: dialect=%s", revision, bind.dialect.name)

    for table, column, col_type, nullable, server_default in _ADD_COLUMNS:
        if _has_column(table, column):
            logger.info("[%s] skip add column: %s.%s already exists", revision, table, column)
            continue
        op.add_column(
            table,
            sa.Column(column, col_type, nullable=nullable, server_default=server_default),
        )
        logger.info("[%s] added column: %s.%s", revision, table, column)

    logger.info("[%s] upgrade done", revision)


def downgrade() -> None:
    bind = op.get_bind()
    logger.info("[%s] downgrade start: dialect=%s", revision, bind.dialect.name)

    # 与 bom_items.version 一致：业务活跃列不删，upgrade 幂等 skip
    logger.info("[%s] keep columns (non-destructive): %s", revision,
                ", ".join(f"{t}.{c}" for t, c, _, _, _ in _ADD_COLUMNS))

    logger.info("[%s] downgrade done", revision)

"""全链路编排: projects 表新增 phase 列（7 阶段状态机持久化）

Revision ID: y0f1a2b3c4d5
Revises: x9e0f1a2b3c4
Create Date: 2026-08-04

阶段码（PHASE_ORDER）：
  initiation / design / budget / procurement / construction / quality / settlement / completed
外加 cancelled 作为任意阶段可进入的终态。

特性：
  - 幂等：has_column 检查，生产可安全重复执行
  - NOT NULL 列带 server_default，存量行按 status 反推 backfill：
      status=completed → phase=completed
      status=active     → phase=construction
      status=draft      → phase=initiation
      其他               → phase=initiation
  - SQLite batch mode 兼容
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "y0f1a2b3c4d5"
down_revision: Union[str, None] = "x9e0f1a2b3c4"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

_TABLE = "projects"


def _has_column(table: str, column_name: str) -> bool:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    try:
        cols = [c["name"] for c in inspector.get_columns(table)]
    except Exception:
        return True
    return column_name in cols


def _add_column(table: str, col: sa.Column) -> None:
    bind = op.get_bind()
    if bind.dialect.name == "sqlite":
        with op.batch_alter_table(table) as batch_op:
            batch_op.add_column(col)
    else:
        op.add_column(table, col)


def upgrade() -> None:
    if not _has_column(_TABLE, "phase"):
        # 先加为 nullable，backfill 后改 NOT NULL
        _add_column(_TABLE, sa.Column("phase", sa.String(30), nullable=True))
        print(f"  added: {_TABLE}.phase (nullable)")

        # 按 status 反推 backfill（与 project_service PHASE_ORDER 对齐）
        bind = op.get_bind()
        bind.execute(sa.text(
            "UPDATE projects SET phase='completed' WHERE phase IS NULL AND status='completed'"
        ))
        bind.execute(sa.text(
            "UPDATE projects SET phase='construction' WHERE phase IS NULL AND status='active'"
        ))
        bind.execute(sa.text(
            "UPDATE projects SET phase='initiation' WHERE phase IS NULL"
        ))
        print(f"  backfilled: {_TABLE}.phase by status")

        # 改为 NOT NULL with server_default（SQLite batch 需重建表，PostgreSQL 直接 alter）
        if bind.dialect.name == "sqlite":
            with op.batch_alter_table(_TABLE) as batch_op:
                batch_op.alter_column(
                    "phase",
                    existing_type=sa.String(30),
                    nullable=False,
                    existing_server_default=sa.text("'initiation'"),
                )
        else:
            op.alter_column(
                _TABLE, "phase",
                existing_type=sa.String(30),
                nullable=False,
                server_default=sa.text("'initiation'"),
            )
        print(f"  set: {_TABLE}.phase NOT NULL default 'initiation'")


def downgrade() -> None:
    bind = op.get_bind()
    if not _has_column(_TABLE, "phase"):
        return
    if bind.dialect.name == "sqlite":
        with op.batch_alter_table(_TABLE) as batch_op:
            batch_op.drop_column("phase")
    else:
        op.drop_column(_TABLE, "phase")

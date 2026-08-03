"""F36 入驻审核: construction_crews 补 6 列（license/review）

Revision ID: v7c8d9e0f1a2
Revises: u6b7c8d9e0f1
Create Date: 2026-08-03

F36 工程队入驻审核在 ORM model（app/models/construction_crew.py）新增 6 列，
但 alembic 迁移链未同步（check_schema_drift.py 检出 production 缺列，/api/crews 500）。
本迁移按既有 drift-fix 惯例（n5e6f7a8b9c0 / s4a5b6c7d8e9）幂等补列：

  license_no / license_type / insurance_no   — 入驻审核材料（可空）
  review_status                              — 审核状态（NOT NULL，server_default 'pending'）
  review_note / reviewed_at                  — 审核备注 / 审核时间（可空）

特性：
  - 幂等：has_column 检查已存在则跳过（生产可安全重复执行）
  - NOT NULL 列带 server_default（存量行获得默认值，避免 ALTER 失败）
  - SQLite batch mode 兼容
  - 回滚：DROP COLUMN（幂等）
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "v7c8d9e0f1a2"
down_revision: Union[str, None] = "u6b7c8d9e0f1"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

_TABLE = "construction_crews"

# (列名, Column 构造)
_COLUMNS: list[tuple[str, sa.Column]] = [
    ("license_no", sa.Column("license_no", sa.String(100), nullable=True)),
    ("license_type", sa.Column("license_type", sa.String(50), nullable=True)),
    ("insurance_no", sa.Column("insurance_no", sa.String(100), nullable=True)),
    (
        "review_status",
        sa.Column(
            "review_status",
            sa.String(20),
            nullable=False,
            server_default=sa.text("'pending'"),
        ),
    ),
    ("review_note", sa.Column("review_note", sa.String(500), nullable=True)),
    (
        "reviewed_at",
        sa.Column("reviewed_at", sa.DateTime(timezone=True), nullable=True),
    ),
]


def _has_column(column_name: str) -> bool:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    try:
        cols = [c["name"] for c in inspector.get_columns(_TABLE)]
    except Exception:
        return True  # 表不存在视为已处理，避免报错
    return column_name in cols


def _add_column(col: sa.Column) -> None:
    bind = op.get_bind()
    if bind.dialect.name == "sqlite":
        with op.batch_alter_table(_TABLE) as batch_op:
            batch_op.add_column(col)
    else:
        op.add_column(_TABLE, col)


def upgrade() -> None:
    for col_name, col in _COLUMNS:
        if _has_column(col_name):
            print(f"  skip: {_TABLE}.{col_name} already exists")
            continue
        _add_column(col)
        print(f"  added: {_TABLE}.{col_name}")


def downgrade() -> None:
    bind = op.get_bind()
    is_sqlite = bind.dialect.name == "sqlite"
    for col_name, _ in reversed(_COLUMNS):
        if not _has_column(col_name):
            continue
        if is_sqlite:
            with op.batch_alter_table(_TABLE) as batch_op:
                batch_op.drop_column(col_name)
        else:
            op.drop_column(_TABLE, col_name)

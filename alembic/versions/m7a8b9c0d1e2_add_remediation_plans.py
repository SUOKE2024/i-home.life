"""新增 remediation_plans 表 — 站点修复清单（v1.18.0）

Revision ID: m7a8b9c0d1e2
Revises: c6d7e8f9a0b1
Create Date: 2026-09-25

借鉴来源：数智前线《万小智，让AI从网站生成走向企业经营》（2026-09-24）——
AI 让网站生成变得容易，但「诊断完成不代表问题解决」，缺失的是
「清单 → 确认 → 执行 → 复检 → 回滚」的留痕。本表承载该处置链路。

幂等：表已存在（create_all 建表场景）则跳过。
回滚：downgrade 直接 drop_table（清单为本版本新增数据，无既有依赖）。
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "m7a8b9c0d1e2"
down_revision: Union[str, None] = "c6d7e8f9a0b1"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

_TABLE = "remediation_plans"
_STATUSES = "'proposed', 'applied', 'verified', 'partially_verified', 'rolled_back'"


def _has_table(table_name: str) -> bool:
    inspector = sa.inspect(op.get_bind())
    try:
        return table_name in inspector.get_table_names()
    except Exception:
        return False


def upgrade() -> None:
    if _has_table(_TABLE):
        print(f"  skip: {_TABLE} already exists")
        return

    op.create_table(
        _TABLE,
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("plan_type", sa.String(40), nullable=False, server_default="site_ai_visibility"),
        sa.Column("status", sa.String(20), nullable=False, server_default="proposed"),
        sa.Column("static_root", sa.String(200), nullable=True),
        sa.Column("score_before", sa.Integer, nullable=True),
        sa.Column("score_after", sa.Integer, nullable=True),
        sa.Column("items", sa.JSON, nullable=True),
        sa.Column("summary", sa.JSON, nullable=True),
        sa.Column("backups", sa.JSON, nullable=True),
        sa.Column("created_by", sa.String(36), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("applied_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("verified_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("rolled_back_at", sa.DateTime(timezone=True), nullable=True),
        sa.CheckConstraint(f"status IN ({_STATUSES})", name="chk_remediation_plan_status"),
    )
    op.create_index(f"ix_{_TABLE}_created_by", _TABLE, ["created_by"])
    print(f"  created: {_TABLE} (站点修复清单)")


def downgrade() -> None:
    if not _has_table(_TABLE):
        print(f"  skip: {_TABLE} not exists")
        return
    # 索引随表一并删除（SQLite/PostgreSQL 均无需显式 drop_index）
    op.drop_table(_TABLE)
    print(f"  dropped: {_TABLE}")

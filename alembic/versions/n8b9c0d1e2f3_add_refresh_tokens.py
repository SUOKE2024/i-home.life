"""新增 refresh_tokens 表 — 刷新令牌会话（认证改造 v4.public）

Revision ID: n8b9c0d1e2f3
Revises: m7a8b9c0d1e2
Create Date: 2026-10-14

认证改造：把 PASETO 从 v4.local（对称）切到 v4.public（Ed25519），并引入
OAuth 2.1 风格的刷新令牌轮换（同族滚动 + 复用检测 + 族撤销），与 suoke_club 对齐。
本表作为 refresh 会话的 SSOT：jti 主键、族、令牌原文、used_at/rotated_to/revoked。

幂等：表已存在（create_all 建表场景）则跳过。
回滚：downgrade 直接 drop_table（会话为本版本新增数据，无既有依赖）。
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "n8b9c0d1e2f3"
down_revision: Union[str, None] = "m7a8b9c0d1e2"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

_TABLE = "refresh_tokens"


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
        sa.Column("jti", sa.String(64), primary_key=True),
        sa.Column("user_id", sa.String(36), nullable=False),
        sa.Column("family_id", sa.String(32), nullable=False),
        sa.Column("token_text", sa.Text, nullable=False),
        sa.Column("issued_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("used_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("rotated_to", sa.String(64), nullable=True),
        sa.Column("revoked", sa.Boolean, nullable=False, server_default=sa.false()),
    )
    op.create_index(f"ix_{_TABLE}_user_id", _TABLE, ["user_id"])
    op.create_index(f"ix_{_TABLE}_family_id", _TABLE, ["family_id"])
    print(f"  created: {_TABLE} (刷新令牌会话)")


def downgrade() -> None:
    if not _has_table(_TABLE):
        print(f"  skip: {_TABLE} not exists")
        return
    op.drop_table(_TABLE)
    print(f"  dropped: {_TABLE}")

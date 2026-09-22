"""scene_automations 补 ecosystem 列 + 生态凭据加密存量回填（2026-09-22 P0/P1 修复）

Revision ID: k3c4d5e6f7a9
Revises: a3b4c5d6e7f8
Create Date: 2026-09-22

两部分：

1. `scene_automations.ecosystem`（可空 String(50)）—— 此前该列不存在，
   `_run_scene_action` 用 `getattr(scene, "ecosystem", None) or "matter"` 兜底，
   导致所有场景动作恒走 Matter stub 桥 → 永远 pending。补列后可显式指定生态。

2. `ecosystem_integrations.config` 存量加密回填 —— 此前生态凭据（米家账号密码、
   涂鸦 AccessSecret 等）明文落库且经 API 原样回露。改为 AES-256-GCM 密文
   `{"encrypted": "<b64>"}`（密钥 SHA-256(paseto_secret_key)，见 device_credentials）。

幂等：已加密行（含 "encrypted" 键）跳过；表/列不存在（create_all 建表场景）跳过。
加密失败（PASETO 密钥不可用）不阻断迁移，逐行跳过并打印告警计数——
读取路径 `_decrypt_ecosystem_config` 对明文行兼容，故不会造成功能中断。
回滚：downgrade 将密文解回明文（恢复变更前行为；注意回滚会把凭据重新置为明文）+
DROP COLUMN。若需保留加密，勿 downgrade 本迁移。
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "k3c4d5e6f7a9"
down_revision: Union[str, None] = "a3b4c5d6e7f8"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

_TABLE = "scene_automations"
_COLUMN = "ecosystem"
_ECO_TABLE = "ecosystem_integrations"
_ECO_COLUMN = "config"


def _has_table(table_name: str) -> bool:
    inspector = sa.inspect(op.get_bind())
    try:
        return table_name in inspector.get_table_names()
    except Exception:
        return False


def _has_column(table_name: str, column_name: str) -> bool:
    if not _has_table(table_name):
        return False
    inspector = sa.inspect(op.get_bind())
    try:
        return column_name in [c["name"] for c in inspector.get_columns(table_name)]
    except Exception:
        return True


def _eco_table() -> sa.Table:
    meta = sa.MetaData()
    return sa.Table(
        _ECO_TABLE,
        meta,
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column(_ECO_COLUMN, sa.JSON),
    )


def _encrypt_existing_configs() -> None:
    """存量明文凭据 → 密文（幂等；失败逐行跳过并打印告警，不阻断迁移）。"""
    from app.services.device_credentials import encrypt_device_credentials

    bind = op.get_bind()
    tbl = _eco_table()
    rows = bind.execute(sa.select(tbl.c.id, tbl.c.config)).fetchall()
    migrated = 0
    skipped_failed = 0
    for row_id, cfg in rows:
        if not isinstance(cfg, dict) or not cfg or "encrypted" in cfg:
            continue
        encrypted = encrypt_device_credentials(cfg)
        if encrypted is None:
            skipped_failed += 1
            continue
        bind.execute(tbl.update().where(tbl.c.id == row_id).values(**{_ECO_COLUMN: encrypted}))
        migrated += 1
    print(f"  encrypted: {_ECO_TABLE}.{_ECO_COLUMN} rows={migrated}")
    if skipped_failed:
        print(
            f"  WARN: {skipped_failed} 行因 PASETO 密钥不可用未加密（仍为明文，"
            "读取路径兼容；配置密钥后重跑本迁移或手工加密）"
        )


def _decrypt_configs_on_rollback() -> None:
    """回滚：密文解回明文（恢复变更前行为）；解不开的行原样保留。"""
    from app.services.device_credentials import decrypt_device_credentials

    bind = op.get_bind()
    tbl = _eco_table()
    rows = bind.execute(sa.select(tbl.c.id, tbl.c.config)).fetchall()
    restored = 0
    for row_id, cfg in rows:
        if not isinstance(cfg, dict) or "encrypted" not in cfg:
            continue
        plain = decrypt_device_credentials(cfg)
        if plain is None:
            continue
        bind.execute(tbl.update().where(tbl.c.id == row_id).values(**{_ECO_COLUMN: plain}))
        restored += 1
    if restored:
        print(f"  WARN: {restored} 行生态凭据已回滚为明文存储（恢复变更前行为）")


def upgrade() -> None:
    if not _has_table(_TABLE):
        print(f"  skip: {_TABLE} not exists (create_all 建表)")
    elif not _has_column(_TABLE, _COLUMN):
        col = sa.Column(_COLUMN, sa.String(50), nullable=True)
        bind = op.get_bind()
        if bind.dialect.name == "sqlite":
            with op.batch_alter_table(_TABLE) as batch_op:
                batch_op.add_column(col)
        else:
            op.add_column(_TABLE, col)
        print(f"  added: {_TABLE}.{_COLUMN} (场景执行生态桥显式指定列)")
    else:
        print(f"  skip: {_TABLE}.{_COLUMN} already exists")

    if _has_table(_ECO_TABLE) and _has_column(_ECO_TABLE, _ECO_COLUMN):
        _encrypt_existing_configs()
    else:
        print(f"  skip: {_ECO_TABLE}.{_ECO_COLUMN} not exists (create_all 建表，新写入即密文)")


def downgrade() -> None:
    if _has_table(_ECO_TABLE) and _has_column(_ECO_TABLE, _ECO_COLUMN):
        _decrypt_configs_on_rollback()

    if not _has_table(_TABLE):
        print(f"  skip: {_TABLE} not exists")
        return
    if not _has_column(_TABLE, _COLUMN):
        print(f"  skip: {_TABLE}.{_COLUMN} not exists")
        return
    bind = op.get_bind()
    if bind.dialect.name == "sqlite":
        with op.batch_alter_table(_TABLE) as batch_op:
            batch_op.drop_column(_COLUMN)
    else:
        op.drop_column(_TABLE, _COLUMN)
    print(f"  dropped: {_TABLE}.{_COLUMN}")

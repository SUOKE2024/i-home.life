"""health_monitors.device_id 放开外键 + 拆分内部设备关联列

Revision ID: c6d7e8f9a0b1
Revises: b5c6d7e8f9a0
Create Date: 2026-09-24

背景（2026-09-24 生产环境多角色交叉验证 A-2，High）：
  ``health_monitors.device_id`` 原为 ``ForeignKey("smart_devices.id")``，而穿戴 BLE
  上报链路传的是 **BLE MAC**（``flutter_app/lib/pages/wearable_devices_page.dart``
  直接传 ``_ble.device?.remoteId.str``；CLAUDE.md 亦明确「device_id=BLE MAC」）。
  三处口径互斥 → 生产实测 ``device_id="AA:BB:CC:DD:EE:FF"`` 恒 422
  （``health_monitors_device_id_fkey``），**适老/穿戴康养链路的真实心率上报不可用**。

本迁移按「后端放开外键」方案拆分两列，各司其职：
  - ``device_id``            外部设备标识（BLE MAC / 第三方设备号），**去外键**，仅索引
  - ``smart_device_id``      平台内 ``smart_devices`` 的可选关联（保留外键约束）

  这样既保住 CLAUDE.md 已公开的「device_id=BLE MAC」口径，又保留「记录可关联平台设备」
  的能力；两者互不强制，缺失不报错（诚实降级：无关联即如实为空，不伪造）。

方言差异（关键）：
  - PostgreSQL：原生 ``op.drop_constraint`` / ``op.add_column`` + ``create_foreign_key``。
    旧外键名用 PG 默认命名 ``health_monitors_device_id_fkey``，存在才 drop（幂等）。
  - SQLite：**不对旧外键做 drop**。原因：SQLite 的 FK 是建表内联且**匿名**，无法按名删除；
    且 SQLite 默认 ``PRAGMA foreign_keys=OFF``（全仓库未开启），该外键本就不生效，
    而测试库由 ``tests/conftest.py`` 的 ``Base.metadata.create_all`` 从模型直接建表
    （模型已无该外键）。保留旧内联外键对功能无影响，强行 batch 重建反而有丢列风险。
    新列与**具名**外键经 ``batch_alter_table`` 添加（具名方可反射/回滚）。
"""
from typing import Sequence, Union

import logging

from alembic import op
import sqlalchemy as sa

logger = logging.getLogger("alembic.runtime.migration")


# revision identifiers, used by Alembic.
revision: str = "c6d7e8f9a0b1"
down_revision: Union[str, None] = "b5c6d7e8f9a0"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

_TABLE = "health_monitors"
_OLD_FK = "health_monitors_device_id_fkey"   # PG 默认命名
_NEW_COL = "smart_device_id"
_NEW_FK = "fk_health_monitors_smart_device_id"
_NEW_IX = "ix_health_monitors_smart_device_id"


def _columns(table: str) -> set[str]:
    try:
        return {c["name"] for c in sa.inspect(op.get_bind()).get_columns(table)}
    except Exception:
        return set()


def _table_exists(table: str) -> bool:
    return table in set(sa.inspect(op.get_bind()).get_table_names())


def _fk_exists(table: str, name: str) -> bool:
    try:
        return name in {f["name"] for f in sa.inspect(op.get_bind()).get_foreign_keys(table)}
    except NotImplementedError:
        return False


def upgrade() -> None:
    bind = op.get_bind()
    dialect = bind.dialect.name
    logger.info("[%s] upgrade start: dialect=%s", revision, dialect)

    if not _table_exists(_TABLE):
        logger.warning("[%s] table %s missing, skip", revision, _TABLE)
        return

    # 1) 放开 device_id 外键（仅 PG；SQLite 见模块 docstring 说明）
    if dialect == "sqlite":
        logger.info("[%s] SQLite: keep unenforced anonymous device_id FK (PRAGMA foreign_keys=OFF)",
                    revision)
    elif _fk_exists(_TABLE, _OLD_FK):
        op.drop_constraint(_OLD_FK, _TABLE, type_="foreignkey")
        logger.info("[%s] dropped old FK %s", revision, _OLD_FK)
    else:
        logger.info("[%s] skip: old FK %s absent", revision, _OLD_FK)

    # 2) 新增 smart_device_id（平台内设备可选关联）
    if _NEW_COL in _columns(_TABLE):
        logger.info("[%s] skip add column: %s.%s exists", revision, _TABLE, _NEW_COL)
    elif dialect == "sqlite":
        with op.batch_alter_table(_TABLE) as batch_op:
            batch_op.add_column(sa.Column(_NEW_COL, sa.String(36), nullable=True))
            batch_op.create_foreign_key(_NEW_FK, "smart_devices", [_NEW_COL], ["id"])
    else:
        op.add_column(_TABLE, sa.Column(_NEW_COL, sa.String(36), nullable=True))
        op.create_foreign_key(_NEW_FK, _TABLE, "smart_devices", [_NEW_COL], ["id"])
        logger.info("[%s] added column + FK %s", revision, _NEW_COL)

    # 3) 索引（两方言通用，幂等由 inspector 判定）
    existing_ix = {i["name"] for i in sa.inspect(bind).get_indexes(_TABLE)}
    if _NEW_IX not in existing_ix:
        op.create_index(_NEW_IX, _TABLE, [_NEW_COL])
        logger.info("[%s] created index %s", revision, _NEW_IX)
    else:
        logger.info("[%s] skip index: %s exists", revision, _NEW_IX)

    logger.info("[%s] upgrade done", revision)


def downgrade() -> None:
    bind = op.get_bind()
    dialect = bind.dialect.name
    logger.info("[%s] downgrade start: dialect=%s", revision, dialect)

    if not _table_exists(_TABLE):
        logger.info("[%s] skip: table absent", revision)
        return

    # 索引 → 外键/列 → 恢复 device_id 外键（逆序）
    existing_ix = {i["name"] for i in sa.inspect(bind).get_indexes(_TABLE)}
    if _NEW_IX in existing_ix:
        op.drop_index(_NEW_IX, table_name=_TABLE)
        logger.info("[%s] dropped index %s", revision, _NEW_IX)

    if _NEW_COL in _columns(_TABLE):
        if dialect == "sqlite":
            with op.batch_alter_table(_TABLE) as batch_op:
                batch_op.drop_constraint(_NEW_FK, type_="foreignkey")
                batch_op.drop_column(_NEW_COL)
        else:
            if _fk_exists(_TABLE, _NEW_FK):
                op.drop_constraint(_NEW_FK, _TABLE, type_="foreignkey")
            op.drop_column(_TABLE, _NEW_COL)
        logger.info("[%s] dropped column %s", revision, _NEW_COL)

    if dialect != "sqlite" and not _fk_exists(_TABLE, _OLD_FK):
        op.create_foreign_key(_OLD_FK, _TABLE, "smart_devices", ["device_id"], ["id"])
        logger.info("[%s] restored FK %s", revision, _OLD_FK)

    logger.info("[%s] downgrade done", revision)

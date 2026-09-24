"""回填 scene_automations.scene_type CHECK 约束（受限枚举三层兜底补漏）

Revision ID: b5c6d7e8f9a0
Revises: a4b5c6d7e8f9
Create Date: 2026-09-24

背景（2026-09-24 生产环境多角色交叉验证 A-1 / B-3，High）：
  ``scene_type`` 的受限枚举在三层均无兜底，非法值可 201 落库并持久化（生产实测
  ``wakeup`` / ``sleep`` / ``QA_GARBAGE_XYZ`` 全部 201，PATCH 亦 200）：
    1. schema：``app/schemas/scene_automation.py`` 原为裸 ``str``，合法值只写在注释里
       （同文件 ``EcosystemName`` 已用 Literal，属遗漏非设计）
    2. model：``SceneAutomation`` 完全没有 ``__table_args__``（无任何 CheckConstraint）
    3. 迁移：``b8c8d9e0f1a2`` 的 166 条回填清单**未收录本表**，``scene_automations``
       仅出现在该文件 docstring 注释中

  与 CLAUDE.md「scene_type 合法值为 manual/scheduled/triggered/geo」及 v1.17.4
  「生产实测 32 → 198 条约束，越界枚举被拒」直接冲突——本表是 CHECK 回填的漏网表。

前置条件：执行前须确认库内无非法值残留（``SELECT count(*) FROM scene_automations
WHERE scene_type NOT IN ('manual','scheduled','triggered','geo')`` 应为 0）。
生产已于 2026-09-24 清理完毕（验证期产生的 4 条探测记录已删除），实测残留 0。

幂等：约束已存在则 skip（照 ``b8c8d9e0f1a2`` 的 ``_plan`` 范式）。
SQLite 走 ``batch_alter_table``（不支持原生 ADD/DROP CONSTRAINT），PG 走原生。
"""
from typing import Sequence, Union

import logging

from alembic import op
import sqlalchemy as sa

logger = logging.getLogger("alembic.runtime.migration")


# revision identifiers, used by Alembic.
revision: str = "b5c6d7e8f9a0"
down_revision: Union[str, None] = "a4b5c6d7e8f9"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

_TABLE = "scene_automations"
_CONSTRAINT = "chk_scene_automation_scene_type"
_SQLTEXT = "scene_type IN ('manual', 'scheduled', 'triggered', 'geo')"


def _table_exists(table: str) -> bool:
    return table in set(sa.inspect(op.get_bind()).get_table_names())


def _constraint_exists(table: str, name: str) -> bool:
    try:
        return name in {c["name"] for c in sa.inspect(op.get_bind()).get_check_constraints(table)}
    except NotImplementedError:  # 方言不支持反射 → 视为不存在
        return False


def upgrade() -> None:
    bind = op.get_bind()
    dialect = bind.dialect.name
    logger.info("[%s] upgrade start: dialect=%s", revision, dialect)

    if not _table_exists(_TABLE):
        logger.warning("[%s] table %s missing, skip", revision, _TABLE)
        return
    if _constraint_exists(_TABLE, _CONSTRAINT):
        logger.info("[%s] skip: %s already exists", revision, _CONSTRAINT)
        return

    if dialect == "sqlite":
        with op.batch_alter_table(_TABLE) as batch_op:
            batch_op.create_check_constraint(_CONSTRAINT, _SQLTEXT)
    else:
        op.create_check_constraint(_CONSTRAINT, _TABLE, _SQLTEXT)
    logger.info("[%s] added %s ON %s", revision, _CONSTRAINT, _TABLE)
    logger.info("[%s] upgrade done", revision)


def downgrade() -> None:
    bind = op.get_bind()
    dialect = bind.dialect.name
    logger.info("[%s] downgrade start: dialect=%s", revision, dialect)

    if not _table_exists(_TABLE) or not _constraint_exists(_TABLE, _CONSTRAINT):
        logger.info("[%s] skip drop: %s absent", revision, _CONSTRAINT)
        return

    if dialect == "sqlite":
        with op.batch_alter_table(_TABLE) as batch_op:
            batch_op.drop_constraint(_CONSTRAINT, type_="check")
    else:
        op.drop_constraint(_CONSTRAINT, _TABLE, type_="check")
    logger.info("[%s] dropped %s", revision, _CONSTRAINT)
    logger.info("[%s] downgrade done", revision)

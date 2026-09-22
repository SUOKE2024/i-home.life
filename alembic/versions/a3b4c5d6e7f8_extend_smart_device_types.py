"""smart_devices.device_type 允许集扩展：适老/康养设备类型（v1.17.0）

Revision ID: a3b4c5d6e7f8
Revises: f1a2b3c4d5e6
Create Date: 2026-09-15

背景（2026-09-15 八部门《促进智能家居消费行动方案》适老化供给落地）：
政策明确「推广家庭服务机器人、健康监测、智能照护等适老化产品」。原允许集
（light/switch/socket/sensor/camera/lock/curtain/speaker/thermostat/
air_purifier/robot_vacuum）无法承载适老设备选型与台账，真实写入会抛
IntegrityError（500）。

新增 5 类：
  - fall_radar      毫米波跌倒监测雷达（防跌倒，地方高阶补贴品类）
  - emergency_call  紧急呼叫按钮（床头/卫生间）
  - care_bed        智能护理床 / 防压疮护理床垫
  - health_monitor  健康监测终端（心率/血氧/睡眠等）
  - service_robot   家庭服务机器人（陪伴/照护/移位辅助）

设计：
  - 仅扩允许集（不缩），存量数据安全；幂等：_has_constraint 守卫，缺失即 skip
    （纯 alembic 从零建的库里 smart_devices 未带 CHECK 约束——约束由
    `database.init_db` 的 create_all 依模型建立；两条路径下本迁移均安全：无约束即 skip）
  - SQLite 用 batch_alter_table（不支持原生 DROP CONSTRAINT）；PG 直接 drop/create
  - downgrade 恢复原 11 类允许集（若期间写入过新增类型，downgrade 由约束拒绝）
  - 本地已实测 up/down 全周期：约束替换生效、`ix_smart_devices_scheme_id` 索引保留、
    无 `_alembic_tmp_*` 残留
"""
from typing import Sequence, Union

import logging

from alembic import op
import sqlalchemy as sa

logger = logging.getLogger("alembic.runtime.migration")


# revision identifiers, used by Alembic.
revision: str = "a3b4c5d6e7f8"
down_revision: Union[str, None] = "f1a2b3c4d5e6"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

_TABLE = "smart_devices"
_CONSTRAINT = "chk_smart_device_type"

_NEW_ALLOWED_SQL = (
    "device_type IN ('light', 'switch', 'socket', 'sensor', 'camera', 'lock', "
    "'curtain', 'speaker', 'thermostat', 'air_purifier', 'robot_vacuum', "
    "'fall_radar', 'care_bed', 'service_robot', 'health_monitor', 'emergency_call')"
)

_OLD_ALLOWED_SQL = (
    "device_type IN ('light', 'switch', 'socket', 'sensor', 'camera', 'lock', "
    "'curtain', 'speaker', 'thermostat', 'air_purifier', 'robot_vacuum')"
)


def _has_constraint(table: str, constraint_name: str) -> bool:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    try:
        constraints = [c["name"] for c in inspector.get_check_constraints(table)]
    except Exception:
        return True
    return constraint_name in constraints


def _replace_check_constraint(new_sql: str) -> None:
    if not _has_constraint(_TABLE, _CONSTRAINT):
        logger.info("[%s] constraint %s.%s missing, skip", revision, _TABLE, _CONSTRAINT)
        return
    bind = op.get_bind()
    if bind.dialect.name == "sqlite":
        with op.batch_alter_table(_TABLE) as batch_op:
            batch_op.drop_constraint(_CONSTRAINT, type_="check")
            batch_op.create_check_constraint(_CONSTRAINT, new_sql)
    else:
        op.drop_constraint(_CONSTRAINT, _TABLE, type_="check")
        op.create_check_constraint(_CONSTRAINT, _TABLE, new_sql)
    logger.info("[%s] replaced constraint: %s.%s", revision, _TABLE, _CONSTRAINT)


def upgrade() -> None:
    bind = op.get_bind()
    logger.info("[%s] upgrade start: dialect=%s", revision, bind.dialect.name)
    _replace_check_constraint(_NEW_ALLOWED_SQL)
    logger.info("[%s] upgrade done", revision)


def downgrade() -> None:
    bind = op.get_bind()
    logger.info("[%s] downgrade start: dialect=%s", revision, bind.dialect.name)
    _replace_check_constraint(_OLD_ALLOWED_SQL)
    logger.info("[%s] downgrade done", revision)

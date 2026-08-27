"""scene_automations 补 trigger_type 派生列 + 索引（2026-08-27 设备链路加固）

Revision ID: c2d3e4f5a6b7
Revises: v1c2d3e4f5a6
Create Date: 2026-08-27

背景：check_sensor_triggers 每次传感器快照上传全量扫描用户所有 enabled 场景，
再在 Python 侧过滤 trigger_condition.type == "sensor"。补冗余列 trigger_type
（由 trigger_condition.type 派生，值域 time/device/geo/sensor），
使 SQL 层可走索引预过滤，避免场景数×设备数增长时性能劣化。

数据纪律：只派生真实类型，未知/缺失 type 保持 NULL（诚实，不猜测）。
写路径统一派生（scene_automation_service.create_scene/update_scene、
predictive_scene_service.accept_prediction），本迁移仅回填存量数据。
列定义与 app/models/scene_automation.py::SceneAutomation.trigger_type 一致
（可空 String(30) + index）。
回滚：DROP INDEX + DROP COLUMN（幂等）。
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "c2d3e4f5a6b7"
down_revision: Union[str, None] = "v1c2d3e4f5a6"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

_TABLE = "scene_automations"
_COLUMN = "trigger_type"
_INDEX = "ix_scene_automations_trigger_type"


def _has_table(table_name: str) -> bool:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    try:
        return table_name in inspector.get_table_names()
    except Exception:
        return False


def _has_column(table_name: str, column_name: str) -> bool:
    if not _has_table(table_name):
        return False
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    try:
        cols = [c["name"] for c in inspector.get_columns(table_name)]
    except Exception:
        return True
    return column_name in cols


def _has_index(table_name: str, index_name: str) -> bool:
    if not _has_table(table_name):
        return False
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    try:
        idx = [i["name"] for i in inspector.get_indexes(table_name)]
    except Exception:
        return True
    return index_name in idx


def _backfill_trigger_type() -> None:
    """存量回填：仅派生已知类型（time/device/geo/sensor），未知保持 NULL。"""
    bind = op.get_bind()
    if bind.dialect.name == "sqlite":
        op.execute(
            "UPDATE scene_automations SET trigger_type = "
            "json_extract(trigger_condition, '$.type') "
            "WHERE trigger_condition IS NOT NULL "
            "AND json_extract(trigger_condition, '$.type') IN "
            "('time','device','geo','sensor')"
        )
    else:
        op.execute(
            "UPDATE scene_automations SET trigger_type = "
            "trigger_condition->>'type' "
            "WHERE trigger_condition IS NOT NULL "
            "AND trigger_condition->>'type' IN "
            "('time','device','geo','sensor')"
        )


def upgrade() -> None:
    if not _has_table(_TABLE):
        # 表不存在（create_all 建表场景）：新模型已含列，跳过
        print(f"  skip: {_TABLE} not exists (create_all 建表)")
        return
    if not _has_column(_TABLE, _COLUMN):
        col = sa.Column(_COLUMN, sa.String(30), nullable=True)
        bind = op.get_bind()
        if bind.dialect.name == "sqlite":
            with op.batch_alter_table(_TABLE) as batch_op:
                batch_op.add_column(col)
        else:
            op.add_column(_TABLE, col)
        print(f"  added: {_TABLE}.{_COLUMN} (触发类型派生列)")
        _backfill_trigger_type()
        print(f"  backfilled: {_TABLE}.{_COLUMN} (存量派生)")
    else:
        print(f"  skip: {_TABLE}.{_COLUMN} already exists")
    if not _has_index(_TABLE, _INDEX):
        op.create_index(_INDEX, _TABLE, [_COLUMN])
        print(f"  created: {_INDEX}")
    else:
        print(f"  skip: {_INDEX} already exists")


def downgrade() -> None:
    if not _has_table(_TABLE):
        print(f"  skip: {_TABLE} not exists")
        return
    if _has_index(_TABLE, _INDEX):
        op.drop_index(_INDEX, table_name=_TABLE)
        print(f"  dropped: {_INDEX}")
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

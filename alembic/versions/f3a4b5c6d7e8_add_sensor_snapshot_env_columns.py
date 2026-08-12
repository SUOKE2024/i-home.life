"""设备链路验证增强: sensor_snapshots 补环境量列（temperature/humidity/light_lux）

Revision ID: f3a4b5c6d7e8
Revises: e2f3a4b5c6d7
Create Date: 2026-08-12

背景：sensor_snapshot API 需支持环境传感器真实上报的环境量参与场景触发
（temperature/humidity/light_lux）。e2f3a4b5c6d7 建表时无此三列，
对已建表补列（幂等 has_column 检查，SQLite batch mode 兼容）。

列定义与 app/models/sensor_snapshot.py::SensorSnapshot 完全一致（可空 Float）。
回滚：DROP COLUMN（幂等）。
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "f3a4b5c6d7e8"
down_revision: Union[str, None] = "e2f3a4b5c6d7"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

_TABLE = "sensor_snapshots"
_COLUMNS = [
    ("temperature", sa.Float(), "温度 °C"),
    ("humidity", sa.Float(), "湿度 %"),
    ("light_lux", sa.Float(), "光照度 lux"),
]


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


def upgrade() -> None:
    if not _has_table(_TABLE):
        # 表不存在（create_all 建表场景）：新模型已含列，跳过
        print(f"  skip: {_TABLE} not exists (create_all 建表)")
        return
    bind = op.get_bind()
    for name, coltype, desc in _COLUMNS:
        if _has_column(_TABLE, name):
            print(f"  skip: {_TABLE}.{name} already exists")
            continue
        col = sa.Column(name, coltype, nullable=True)
        if bind.dialect.name == "sqlite":
            with op.batch_alter_table(_TABLE) as batch_op:
                batch_op.add_column(col)
        else:
            op.add_column(_TABLE, col)
        print(f"  added: {_TABLE}.{name} ({desc})")


def downgrade() -> None:
    if not _has_table(_TABLE):
        print(f"  skip: {_TABLE} not exists")
        return
    bind = op.get_bind()
    for name, _, _ in _COLUMNS:
        if not _has_column(_TABLE, name):
            print(f"  skip: {_TABLE}.{name} not exists")
            continue
        if bind.dialect.name == "sqlite":
            with op.batch_alter_table(_TABLE) as batch_op:
                batch_op.drop_column(name)
        else:
            op.drop_column(_TABLE, name)
        print(f"  dropped: {_TABLE}.{name}")

"""设备链路全量诊断修复: sensor_snapshots 建表迁移（Flutter 传感器快照真实落库）

Revision ID: e2f3a4b5c6d7
Revises: a7b8c9d0e1f2
Create Date: 2026-08-12

背景：/api/sensors/snapshot 此前仅返回 received 确认、不落库，且用加速度计数据
硬编码伪装温度/湿度/占用率触发场景（违反诚实降级红线）。本次新增 sensor_snapshots
表，仅存储客户端真实采集读数（加速度计/陀螺仪/磁力计/GPS）。

列定义与 app/models/sensor_snapshot.py::SensorSnapshot 完全一致。
回滚：DROP TABLE（幂等）。
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "e2f3a4b5c6d7"
down_revision: Union[str, None] = "a7b8c9d0e1f2"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

_TABLE = "sensor_snapshots"


def _has_table(table_name: str) -> bool:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
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
        sa.Column("user_id", sa.String(36), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("device_id", sa.String(200), nullable=True),
        sa.Column("platform", sa.String(30), nullable=False),
        sa.Column("accelerometer_available", sa.Boolean(), nullable=False),
        sa.Column("accelerometer_x", sa.Float(), nullable=True),
        sa.Column("accelerometer_y", sa.Float(), nullable=True),
        sa.Column("accelerometer_z", sa.Float(), nullable=True),
        sa.Column("gyroscope_available", sa.Boolean(), nullable=False),
        sa.Column("gyroscope_x", sa.Float(), nullable=True),
        sa.Column("gyroscope_y", sa.Float(), nullable=True),
        sa.Column("gyroscope_z", sa.Float(), nullable=True),
        sa.Column("magnetometer_available", sa.Boolean(), nullable=False),
        sa.Column("magnetometer_x", sa.Float(), nullable=True),
        sa.Column("magnetometer_y", sa.Float(), nullable=True),
        sa.Column("magnetometer_z", sa.Float(), nullable=True),
        sa.Column("magnetometer_heading_deg", sa.Float(), nullable=True),
        sa.Column("gps_available", sa.Boolean(), nullable=False),
        sa.Column("gps_latitude", sa.Float(), nullable=True),
        sa.Column("gps_longitude", sa.Float(), nullable=True),
        sa.Column("gps_accuracy", sa.Float(), nullable=True),
        sa.Column("gps_altitude", sa.Float(), nullable=True),
        sa.Column("sampled_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.Index("ix_sensor_snapshots_user_id", "user_id"),
        sa.Index("ix_sensor_snapshots_device_id", "device_id"),
    )
    print(f"  created: {_TABLE}")


def downgrade() -> None:
    if not _has_table(_TABLE):
        print(f"  skip: {_TABLE} not exists")
        return
    op.drop_table(_TABLE)
    print(f"  dropped: {_TABLE}")

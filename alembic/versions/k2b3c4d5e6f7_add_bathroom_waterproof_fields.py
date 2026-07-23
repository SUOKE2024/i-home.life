"""add bathroom waterproof fields

Revision ID: k2b3c4d5e6f7
Revises: j1a2b3c4d5e6
Create Date: 2026-07-23

v1.1.31 FP-2 修复：BathroomDesign 补 7 个防水/通风真校验字段。
原 validate_waterproof 后 4 项硬编码 passed=True（伪专业），现补字段做真校验。

新增字段（均 nullable=True，含 server_default 以便存量行获得默认值）：
  - other_wall_waterproof_height_mm  Integer  默认 300   其他墙面防水高度（≥300mm）
  - floor_waterproof_done            Integer  默认 1     地面是否满做防水（0/1）
  - waterproof_thickness_mm          Float    默认 1.5   防水层厚度（≥1.5mm）
  - water_test_hours                 Float    默认 48.0  闭水试验时长（≥48h，对齐 HC-005）
  - has_natural_window               Integer  默认 0     是否有自然通风窗（0/1）
  - window_area_m2                   Float    默认 NULL  窗户面积（m²）
  - mechanical_vent_airflow          Float    默认 80.0  机械通风风量（m³/h，≥80）

回滚：DROP COLUMN（SQLite 需 batch mode）。
"""
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = "k2b3c4d5e6f7"
down_revision = "j1a2b3c4d5e6"
branch_labels = None
depends_on = None


# (列名, 类型, server_default)
_COLUMNS = [
    ("other_wall_waterproof_height_mm", sa.Integer(), "300"),
    ("floor_waterproof_done", sa.Integer(), "1"),
    ("waterproof_thickness_mm", sa.Float(), "1.5"),
    ("water_test_hours", sa.Float(), "48.0"),
    ("has_natural_window", sa.Integer(), "0"),
    ("window_area_m2", sa.Float(), None),
    ("mechanical_vent_airflow", sa.Float(), "80.0"),
]


def upgrade():
    """为 bathroom_designs 表添加 7 个防水/通风真校验字段。

    所有字段 nullable=True + server_default，存量行自动获得默认值，
    新行由 ORM default 填充。SQLite/PG 均用标准 add_column。
    """
    bind = op.get_bind()
    is_sqlite = bind.dialect.name == "sqlite"

    for col_name, col_type, default in _COLUMNS:
        col = sa.Column(col_name, col_type, nullable=True)
        if default is not None:
            # server_default 用文本表达式，兼容 SQLite/PG
            col = sa.Column(
                col_name, col_type, nullable=True,
                server_default=sa.text(default),
            )
        if is_sqlite:
            # SQLite ALTER TABLE ADD COLUMN 不支持 IF NOT EXISTS，
            # 用 batch_alter_table 以兼容（并支持未来表结构重构）
            with op.batch_alter_table("bathroom_designs") as batch_op:
                batch_op.add_column(col)
        else:
            op.add_column("bathroom_designs", col)


def downgrade():
    """回滚：移除 7 个防水/通风字段。"""
    bind = op.get_bind()
    is_sqlite = bind.dialect.name == "sqlite"

    for col_name, _, _ in reversed(_COLUMNS):
        if is_sqlite:
            with op.batch_alter_table("bathroom_designs") as batch_op:
                batch_op.drop_column(col_name)
        else:
            op.drop_column("bathroom_designs", col_name)

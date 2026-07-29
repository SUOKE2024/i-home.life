"""add missing columns drift fix (bathroom/construction/order/procurement)

Revision ID: n5e6f7a8b9c0
Revises: m4d5e6f7a8b9
Create Date: 2026-07-30

v1.2.7 P0 schema drift 修复（第二轮）：check_schema_drift.py 核查发现 4 张表
共 11 列 model 已定义但生产 DB 缺失（alembic 迁移从未应用到生产，create_all
不补列）。ORM 查询 SELECT 这些列会触发 500 column does not exist。

受影响表/列：
  bathroom_designs (7 列, v1.1.31 FP-2 防水通风真校验)：
    - other_wall_waterproof_height_mm  Integer  default 300
    - floor_waterproof_done            Integer  default 1   (bool 0/1)
    - waterproof_thickness_mm          Float    default 1.5
    - water_test_hours                 Float    default 48.0
    - has_natural_window               Integer  default 0   (bool 0/1)
    - window_area_m2                   Float    nullable
    - mechanical_vent_airflow          Float    default 80.0
  construction_tasks (2 列)：
    - actual_duration_days             Float    nullable
    - predecessor_id                   String(36) FK→construction_tasks.id, index
  order_lines (1 列)：
    - delivered_quantity               Float    default 0.0  (已有 chk_order_line_delivered_qty_positive 约束，补列后存量行默认 0.0 满足)
  procurement_orders (2 列)：
    - construction_task_id             String(36) FK→construction_tasks.id, nullable
    - material_delivered_at            DateTime(timezone=True) nullable

特性：
  - 幂等：has_column 检查已存在则跳过
  - 类型对齐 model（DateTime 用 WITH TIME ZONE，符合约定）
  - server_default 用文本表达式兼容 SQLite/PG（存量行获得默认值）
  - SQLite batch mode 兼容
  - FK/index 在补列时一并创建（has_index 检查幂等）
  - 回滚：DROP COLUMN（含 FK/index 自动级联）

注：生产通过直接 ALTER TABLE ADD COLUMN IF NOT EXISTS 补列（ssh psql），
alembic_version 暂不 stamp（既有迁移债单独处理）。
"""
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = "n5e6f7a8b9c0"
down_revision = "m4d5e6f7a8b9"
branch_labels = None
depends_on = None


def _has_column(table_name: str, column_name: str) -> bool:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    try:
        cols = [c["name"] for c in inspector.get_columns(table_name)]
    except Exception:
        return True  # 表不存在视为已处理，避免报错
    return column_name in cols


def _has_index(table_name: str, index_name: str) -> bool:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    try:
        idxs = [i["name"] for i in inspector.get_indexes(table_name)]
    except Exception:
        return True
    return index_name in idxs


def _add_column(table_name: str, col: sa.Column):
    bind = op.get_bind()
    is_sqlite = bind.dialect.name == "sqlite"
    if is_sqlite:
        with op.batch_alter_table(table_name) as batch_op:
            batch_op.add_column(col)
    else:
        op.add_column(table_name, col)


def _create_index(table_name: str, index_name: str, columns: list[str]):
    bind = op.get_bind()
    is_sqlite = bind.dialect.name == "sqlite"
    if _has_index(table_name, index_name):
        return
    if is_sqlite:
        with op.batch_alter_table(table_name) as batch_op:
            batch_op.create_index(index_name, columns)
    else:
        op.create_index(index_name, table_name, columns)


# (表, 列名, Column 构造, 关联 index 定义 [(index_name, [cols])])
_COLUMNS = [
    # bathroom_designs 7 列
    ("bathroom_designs", "other_wall_waterproof_height_mm",
     sa.Column("other_wall_waterproof_height_mm", sa.Integer(), nullable=True, server_default=sa.text("300")), []),
    ("bathroom_designs", "floor_waterproof_done",
     sa.Column("floor_waterproof_done", sa.Integer(), nullable=True, server_default=sa.text("1")), []),
    ("bathroom_designs", "waterproof_thickness_mm",
     sa.Column("waterproof_thickness_mm", sa.Float(), nullable=True, server_default=sa.text("1.5")), []),
    ("bathroom_designs", "water_test_hours",
     sa.Column("water_test_hours", sa.Float(), nullable=True, server_default=sa.text("48.0")), []),
    ("bathroom_designs", "has_natural_window",
     sa.Column("has_natural_window", sa.Integer(), nullable=True, server_default=sa.text("0")), []),
    ("bathroom_designs", "window_area_m2",
     sa.Column("window_area_m2", sa.Float(), nullable=True), []),
    ("bathroom_designs", "mechanical_vent_airflow",
     sa.Column("mechanical_vent_airflow", sa.Float(), nullable=True, server_default=sa.text("80.0")), []),
    # construction_tasks 2 列
    ("construction_tasks", "actual_duration_days",
     sa.Column("actual_duration_days", sa.Float(), nullable=True), []),
    ("construction_tasks", "predecessor_id",
     sa.Column("predecessor_id", sa.String(36), nullable=True),
     [("ix_construction_tasks_predecessor_id", ["predecessor_id"])]),
    # order_lines 1 列
    ("order_lines", "delivered_quantity",
     sa.Column("delivered_quantity", sa.Float(), nullable=False, server_default=sa.text("0.0")), []),
    # procurement_orders 2 列
    ("procurement_orders", "construction_task_id",
     sa.Column("construction_task_id", sa.String(36), nullable=True), []),
    ("procurement_orders", "material_delivered_at",
     sa.Column("material_delivered_at", sa.DateTime(timezone=True), nullable=True), []),
]


def upgrade():
    """为 4 张表补 11 列（幂等，含 FK/index）。"""
    for table_name, col_name, col, indexes in _COLUMNS:
        if _has_column(table_name, col_name):
            continue
        _add_column(table_name, col)
        for idx_name, idx_cols in indexes:
            _create_index(table_name, idx_name, idx_cols)


def downgrade():
    """回滚：移除 11 列（幂等）。"""
    bind = op.get_bind()
    is_sqlite = bind.dialect.name == "sqlite"
    for table_name, col_name, _, indexes in reversed(_COLUMNS):
        # 先删 index 再删列
        for idx_name, _ in indexes:
            if not _has_index(table_name, idx_name):
                continue
            if is_sqlite:
                with op.batch_alter_table(table_name) as batch_op:
                    batch_op.drop_index(idx_name)
            else:
                op.drop_index(idx_name, table_name=table_name)
        if not _has_column(table_name, col_name):
            continue
        if is_sqlite:
            with op.batch_alter_table(table_name) as batch_op:
                batch_op.drop_column(col_name)
        else:
            op.drop_column(table_name, col_name)

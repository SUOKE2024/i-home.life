"""add deleted_at drift fix

Revision ID: m4d5e6f7a8b9
Revises: l3c4d5e6f7a8
Create Date: 2026-07-30

v1.2.7 P0 schema drift 修复：30 张表 model 已有 deleted_at（软删）列，
但 alembic 迁移从未定义该列。本地开发（Base.metadata.create_all）会自动建列，
生产靠 alembic 维护则缺列 → ORM 查询 SELECT * 触发 "column deleted_at does not exist" 500。

根因：deleted_at 是后加到各 model 的，未配套 alembic 迁移（memory 教训：
"create_all 不补列是隐性陷阱"）。本次统一补齐。

受影响表（30）：bathroom_designs / bathroom_fixtures / bom_items / budget_lines /
budgets / ceiling_designs / construction_logs / construction_tasks /
custom_furniture_designs / door_window_specs / furniture_boms / furniture_modules /
hard_decoration_floor_plans / hard_decoration_schemes / inspections /
kitchen_components / kitchen_designs / lighting_fixtures / lighting_schemes /
order_lines / procurement_orders / quotations / smart_devices / smart_home_schemes /
soft_furnishing_items / soft_furnishing_schemes / storage_systems / suppliers /
wall_finishes / waterproof_plans

特性：
  - 幂等：upgrade 用 inspector.get_columns() 检查列已存在则跳过（避免重复执行报错）
  - 类型：DateTime(timezone=True)（符合"生产 PG TIMESTAMP 必须 WITH TIME ZONE"约定）
  - nullable=True，default=None（软删标记，未删行为 NULL）
  - SQLite 兼容：batch_alter_table（SQLite ALTER TABLE 限制）
  - 回滚：DROP COLUMN（SQLite batch mode）

注：生产 alembic_version 当前卡在 4356fec95e3e（init），落后 13 迁移。
本迁移在生产通过直接执行 SQL（ALTER TABLE ADD COLUMN IF NOT EXISTS）补列，
alembic_version 暂不 stamp（既有 13 迁移债单独处理）。
"""
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = "m4d5e6f7a8b9"
down_revision = "l3c4d5e6f7a8"
branch_labels = None
depends_on = None


# 30 张需要补 deleted_at 的表（model 已定义，迁移缺失）
_TABLES = [
    "bathroom_designs",
    "bathroom_fixtures",
    "bom_items",
    "budget_lines",
    "budgets",
    "ceiling_designs",
    "construction_logs",
    "construction_tasks",
    "custom_furniture_designs",
    "door_window_specs",
    "furniture_boms",
    "furniture_modules",
    "hard_decoration_floor_plans",
    "hard_decoration_schemes",
    "inspections",
    "kitchen_components",
    "kitchen_designs",
    "lighting_fixtures",
    "lighting_schemes",
    "order_lines",
    "procurement_orders",
    "quotations",
    "smart_devices",
    "smart_home_schemes",
    "soft_furnishing_items",
    "soft_furnishing_schemes",
    "storage_systems",
    "suppliers",
    "wall_finishes",
    "waterproof_plans",
]


def _has_column(table_name: str, column_name: str = "deleted_at") -> bool:
    """幂等检查：列是否已存在。PG/SQLite 通用。"""
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    try:
        cols = [c["name"] for c in inspector.get_columns(table_name)]
    except Exception:
        # 表不存在时返回 False（不阻断，由 create_all 负责建表）
        return True  # 视为"已处理"跳过，避免对不存在的表报错
    return column_name in cols


def upgrade():
    """为 30 张表补 deleted_at 列（幂等，已存在则跳过）。"""
    bind = op.get_bind()
    is_sqlite = bind.dialect.name == "sqlite"

    for table_name in _TABLES:
        if _has_column(table_name):
            # 列已存在（如本地 create_all 已建，或迁移重复执行），跳过
            continue
        col = sa.Column(
            "deleted_at",
            sa.DateTime(timezone=True),
            nullable=True,
            default=None,
        )
        if is_sqlite:
            # SQLite ALTER TABLE ADD COLUMN 限制，用 batch mode
            with op.batch_alter_table(table_name) as batch_op:
                batch_op.add_column(col)
        else:
            op.add_column(table_name, col)


def downgrade():
    """回滚：移除 30 张表的 deleted_at 列（幂等，不存在则跳过）。"""
    bind = op.get_bind()
    is_sqlite = bind.dialect.name == "sqlite"

    for table_name in _TABLES:
        if not _has_column(table_name):
            continue
        if is_sqlite:
            with op.batch_alter_table(table_name) as batch_op:
                batch_op.drop_column("deleted_at")
        else:
            op.drop_column(table_name, "deleted_at")

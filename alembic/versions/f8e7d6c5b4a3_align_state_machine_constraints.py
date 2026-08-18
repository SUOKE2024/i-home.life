"""状态机-模型约束对齐：budgets / procurement_orders / inspections CheckConstraint 扩展

Revision ID: f8e7d6c5b4a3
Revises: y9a0b1c2d3e4
Create Date: 2026-08-17

背景（2026-08-17 全景全量全链路走查）：
三处状态机合法状态不在 DB CheckConstraint 允许集内，真实写入会抛 IntegrityError（500）：
- budgets：审批流状态机 5 态（draft/submitted/approved/executed/closed），
  原约束仅 ('draft','approved','active','completed')，submit/execute/close 写入即崩
- procurement_orders：状态机 delivered→completed 为合法终态，原约束缺 'completed'
- inspections：状态机 failed→rework 为中间态，原约束缺 'rework'

设计：
  - 幂等：_has_constraint 守卫，已存在 skip；仅扩允许集（不缩），存量数据安全
  - SQLite 用 batch_alter_table（SQLite 不支持原生 DROP CONSTRAINT）；PG 直接 drop/create
  - downgrade 恢复旧约束（允许集缩小；若期间写入过新状态则 downgrade 由约束拒绝——
    与 y9a0b1c2d3e4 phone NOT NULL 同策略：不做破坏性回滚外的特殊处理）
"""
from typing import Sequence, Union

import logging

from alembic import op
import sqlalchemy as sa

logger = logging.getLogger("alembic.runtime.migration")


# revision identifiers, used by Alembic.
revision: str = "f8e7d6c5b4a3"
down_revision: Union[str, None] = "y9a0b1c2d3e4"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

# (table, constraint_name, new_allowed_set_sql)
_UPGRADE_SQL: dict[str, tuple[str, str]] = {
    "budgets": (
        "chk_budget_status",
        "status IN ('draft', 'submitted', 'approved', 'executed', 'closed', 'active', 'completed')",
    ),
    "procurement_orders": (
        "chk_procurement_order_status",
        "status IN ('draft', 'pending', 'confirmed', 'shipped', 'delivered', 'completed', 'cancelled')",
    ),
    "inspections": (
        "chk_inspection_status",
        "status IN ('pending', 'passed', 'failed', 'rework')",
    ),
}

# downgrade 恢复原允许集（2026-08-17 走查前的状态）
_DOWNGRADE_SQL: dict[str, str] = {
    "budgets": "status IN ('draft', 'approved', 'active', 'completed')",
    "procurement_orders": "status IN ('draft', 'pending', 'confirmed', 'shipped', 'delivered', 'cancelled')",
    "inspections": "status IN ('pending', 'passed', 'failed')",
}


def _has_constraint(table: str, constraint_name: str) -> bool:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    try:
        constraints = [c["name"] for c in inspector.get_check_constraints(table)]
    except Exception:
        return True
    return constraint_name in constraints


def _replace_check_constraint(table: str, constraint_name: str, new_sql: str) -> None:
    if not _has_constraint(table, constraint_name):
        logger.info("[%s] constraint %s.%s missing, skip", revision, table, constraint_name)
        return
    bind = op.get_bind()
    if bind.dialect.name == "sqlite":
        with op.batch_alter_table(table) as batch_op:
            batch_op.drop_constraint(constraint_name, type_="check")
            batch_op.create_check_constraint(constraint_name, new_sql)
    else:
        op.drop_constraint(constraint_name, table, type_="check")
        op.create_check_constraint(constraint_name, table, new_sql)
    logger.info("[%s] replaced constraint: %s.%s", revision, table, constraint_name)


def upgrade() -> None:
    bind = op.get_bind()
    logger.info("[%s] upgrade start: dialect=%s", revision, bind.dialect.name)
    for table, (constraint_name, new_sql) in _UPGRADE_SQL.items():
        _replace_check_constraint(table, constraint_name, new_sql)
    logger.info("[%s] upgrade done", revision)


def downgrade() -> None:
    bind = op.get_bind()
    logger.info("[%s] downgrade start: dialect=%s", revision, bind.dialect.name)
    for table, old_sql in _DOWNGRADE_SQL.items():
        constraint_name = _UPGRADE_SQL[table][0]
        _replace_check_constraint(table, constraint_name, old_sql)
    logger.info("[%s] downgrade done", revision)

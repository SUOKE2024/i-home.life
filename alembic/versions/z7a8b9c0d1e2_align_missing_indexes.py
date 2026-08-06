"""补齐缺失索引（A 类 30 + B 类 5）并补建 bom_items.version 列

Revision ID: z7a8b9c0d1e2
Revises: z6a7b8c9d0e1
Create Date: 2026-08-06

背景（2026-08-06 schema 索引三方权威核验，基于 Base.metadata vs 空库迁移链 vs 真实库）：
- A 类 30 个：model 声明 index=True，但建表迁移漏建 → 空库（CI/新环境）缺，
  查询走全表扫描，性能与生产不一致。
  - 其中 budgets.ix_budgets_project_id 为 unique=True（model unique=True, index=True）。
  - bom_items.ix_bom_items_version 依赖的 version 列也是 model 后加、迁移链漏加
    （init 建表无此列）→ 必须先补列再建索引（否则 SQLite 报 no such column）。
- B 类 5 个：迁移链（j1a2b3c4d5e6 v1.1.27 性能索引 / c3d4e5f6a7b8 /
  t5a6b7c8d9e0）已建、model 未声明（单列 index=True 之外的复合/补充索引），
  真实库因历史 create_all 建表而缺 → 补建以对齐空库迁移链语义。
- C 类（unique 标志相反）已由 z6a7b8c9d0e1 单独修复，不在此范围。

设计：
  - upgrade 幂等：列 _has_column skip；索引存在且 unique 标志一致则 skip，
    标志不一致 drop+重建对齐目标（防同名列 historic 形态漂移）
  - downgrade 仅 drop A 类 30 个（本迁移在空库的产物 / 真实库 create_all 残留，
    删除后空库回到"迁移链漏建"语义、真实库对齐迁移链语义）；
    B 类 5 个为前序迁移产物保留，bom_items.version 列不删（删列破坏性大，
    upgrade 时 _has_column 幂等 skip）
"""
from typing import Sequence, Union

import logging

from alembic import op
import sqlalchemy as sa

# 复用 alembic 内置 logger 命名空间：随 alembic 命令输出，无需额外配置
logger = logging.getLogger("alembic.runtime.migration")


# revision identifiers, used by Alembic.
revision: str = "z7a8b9c0d1e2"
down_revision: Union[str, None] = "z6a7b8c9d0e1"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

# ── 补列（model 有、空库无；幂等 _has_column）──
# (表, 列, 类型, nullable, server_default)
_ADD_COLUMNS = [
    ("bom_items", "version", sa.Integer(), False, "1"),
]

# ── 索引对齐（表, 索引名, 列, unique）──
# A 类 30 个：model index=True 但迁移链漏建（空库缺）
# B 类 5 个：迁移链已建、真实库缺（补齐对齐）
_INDEXES = [
    # ── A 类 ──
    ("ar_measurement_points", "ix_ar_measurement_points_session_id", ["session_id"], False),
    ("ar_scan_sessions", "ix_ar_scan_sessions_project_id", ["project_id"], False),
    ("ar_scan_sessions", "ix_ar_scan_sessions_survey_id", ["survey_id"], False),
    ("ar_wall_features", "ix_ar_wall_features_session_id", ["session_id"], False),
    ("bay_compliance", "ix_bay_compliance_project_id", ["project_id"], False),
    ("bom_items", "ix_bom_items_version", ["version"], False),
    ("budget_lines", "ix_budget_lines_budget_id", ["budget_id"], False),
    ("budgets", "ix_budgets_project_id", ["project_id"], True),
    ("change_orders", "ix_change_orders_project_id", ["project_id"], False),
    ("construction_tasks", "ix_construction_tasks_project_id", ["project_id"], False),
    ("escrow_payments", "ix_escrow_payments_order_id", ["order_id"], False),
    ("escrow_payments", "ix_escrow_payments_project_id", ["project_id"], False),
    ("hard_decoration_floor_plans", "ix_hard_decoration_floor_plans_scheme_id", ["scheme_id"], False),
    ("identity_verifications", "ix_identity_verifications_reviewer_id", ["reviewer_id"], False),
    ("inspections", "ix_inspections_task_id", ["task_id"], False),
    ("milestone_trackers", "ix_milestone_trackers_project_id", ["project_id"], False),
    ("orchestrator_tasks", "ix_orchestrator_tasks_assigned_user_id", ["assigned_user_id"], False),
    ("orchestrator_tasks", "ix_orchestrator_tasks_project_id", ["project_id"], False),
    ("order_lines", "ix_order_lines_material_id", ["material_id"], False),
    ("order_lines", "ix_order_lines_order_id", ["order_id"], False),
    ("payments", "ix_payments_project_id", ["project_id"], False),
    ("payments", "ix_payments_settlement_id", ["settlement_id"], False),
    ("points_rankings", "ix_points_rankings_user_id", ["user_id"], False),
    ("procurement_orders", "ix_procurement_orders_construction_task_id", ["construction_task_id"], False),
    ("progress_alerts", "ix_progress_alerts_project_id", ["project_id"], False),
    ("quality_issues", "ix_quality_issues_project_id", ["project_id"], False),
    ("quotations", "ix_quotations_material_id", ["material_id"], False),
    ("quotations", "ix_quotations_project_id", ["project_id"], False),
    ("quotations", "ix_quotations_supplier_id", ["supplier_id"], False),
    ("settlements", "ix_settlements_project_id", ["project_id"], False),
    # ── B 类（前序迁移产物、真实库缺）──
    ("agent_messages", "ix_agent_messages_session_id_created_at", ["session_id", "created_at"], False),
    ("agent_skills", "ix_agent_skills_created_by", ["created_by"], False),
    ("audit_logs", "ix_audit_logs_user_id_created_at", ["user_id", "created_at"], False),
    ("construction_tasks", "ix_construction_tasks_project_id_status", ["project_id", "status"], False),
    ("device_tokens", "ix_device_tokens_user_platform", ["user_id", "platform"], False),
]

# downgrade 仅回收 A 类 30 个（_INDEXES 前 30 项即 A 类；本迁移补建 / 真实库 create_all 残留）


def _has_column(table: str, column: str) -> bool:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    try:
        return column in [c["name"] for c in inspector.get_columns(table)]
    except Exception:
        return False


def _index_spec(table: str, index_name: str) -> tuple | None:
    """返回 (columns, unique)；不存在返回 None。"""
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    try:
        for ix in inspector.get_indexes(table):
            if ix.get("name") == index_name:
                return (tuple(ix.get("column_names") or []), bool(ix.get("unique", False)))
    except Exception:
        return None
    return None


def _add_columns() -> None:
    for table, column, col_type, nullable, server_default in _ADD_COLUMNS:
        if _has_column(table, column):
            logger.info("[%s] skip add column: %s.%s already exists", revision, table, column)
            continue
        op.add_column(
            table,
            sa.Column(column, col_type, nullable=nullable, server_default=server_default),
        )
        logger.info("[%s] added column: %s.%s", revision, table, column)


def _align_indexes() -> None:
    for table, index_name, columns, unique in _INDEXES:
        spec = _index_spec(table, index_name)
        target = (tuple(columns), unique)
        if spec is None:
            op.create_index(index_name, table, columns, unique=unique)
            logger.info("[%s] created index: %s.%s cols=%s unique=%s", revision, table, index_name, columns, unique)
            continue
        if spec == target:
            logger.info("[%s] skip: %s.%s already aligned %s", revision, table, index_name, spec)
            continue
        # 同名列存在但形态不一致 → drop + 重建对齐目标
        op.drop_index(index_name, table_name=table)
        op.create_index(index_name, table, columns, unique=unique)
        logger.info("[%s] rebuilt: %s.%s %s -> %s", revision, table, index_name, spec, target)


def upgrade() -> None:
    bind = op.get_bind()
    logger.info("[%s] upgrade start: dialect=%s", revision, bind.dialect.name)

    _add_columns()
    _align_indexes()

    logger.info("[%s] upgrade done", revision)


def downgrade() -> None:
    bind = op.get_bind()
    logger.info("[%s] downgrade start: dialect=%s", revision, bind.dialect.name)

    # 仅回收 A 类 30 个（B 类 5 个为前序迁移产物，保留；version 列不删）
    for table, index_name, _columns, _unique in _INDEXES[:30]:
        if _index_spec(table, index_name) is None:
            logger.info("[%s] skip drop: %s.%s not exists", revision, table, index_name)
            continue
        op.drop_index(index_name, table_name=table)
        logger.info("[%s] dropped index: %s.%s", revision, table, index_name)

    logger.info("[%s] downgrade done", revision)

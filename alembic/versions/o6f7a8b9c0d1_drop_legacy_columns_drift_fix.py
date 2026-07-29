"""drop legacy unused columns drift fix

Revision ID: o6f7a8b9c0d1
Revises: n5e6f7a8b9c0
Create Date: 2026-07-30

v1.2.7 schema drift 收尾：5 张表的旧列残留（model 已改名/移除，DB 未清理）。
经核验：5 列生产数据全为 0 行（non_null=0）、全代码无引用（grep 确认），
是 model 字段改名后 DB 旧列未同步 DROP 的历史残留。ORM 不 SELECT 这些列
故不阻断运行，但属真实 drift，本次清理使 DB 与 model 完全对齐。

受影响列（均 0 数据、无引用）：
  escrow_payments.amount         model 改名 total_amount（procurement_enhanced.py:71）
  milestone_trackers.due_date    model 已移除（progress_alert.py MilestoneTracker 无此字段）
  orchestrator_tasks.agent_type  model 改用 assigned_agent + task_type（orchestrator_task.py:18,22）
  quality_issues.title           model 改用 description（quality.py:24，QualityIssue 无 title）
  rectification_orders.issue_id  model 改名 issue_ids 复数（quality.py:58，JSON 字符串）

特性：
  - 幂等：has_column 检查不存在则跳过
  - SQLite batch mode 兼容
  - 回滚：downgrade ADD COLUMN（ nullable=True，因旧数据已不存在无法恢复原值，
    但 0 数据无损失；回滚仅恢复列结构供紧急回退）

注：生产通过直接 ALTER TABLE DROP COLUMN IF EXISTS 执行（ssh psql）。
"""
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = "o6f7a8b9c0d1"
down_revision = "n5e6f7a8b9c0"
branch_labels = None
depends_on = None


# (表, 旧列名, 回滚用的列定义)
_LEGACY_COLUMNS = [
    ("escrow_payments", "amount", sa.Column("amount", sa.Float(), nullable=True)),
    ("milestone_trackers", "due_date", sa.Column("due_date", sa.DateTime(timezone=True), nullable=True)),
    ("orchestrator_tasks", "agent_type", sa.Column("agent_type", sa.String(30), nullable=True)),
    ("quality_issues", "title", sa.Column("title", sa.String(200), nullable=True)),
    ("rectification_orders", "issue_id", sa.Column("issue_id", sa.String(36), nullable=True)),
]


def _has_column(table_name: str, column_name: str) -> bool:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    try:
        cols = [c["name"] for c in inspector.get_columns(table_name)]
    except Exception:
        return True  # 表不存在视为已处理
    return column_name in cols


def upgrade():
    """DROP 5 个无引用旧列（幂等，不存在则跳过）。"""
    bind = op.get_bind()
    is_sqlite = bind.dialect.name == "sqlite"
    for table_name, col_name, _ in _LEGACY_COLUMNS:
        if not _has_column(table_name, col_name):
            continue
        if is_sqlite:
            with op.batch_alter_table(table_name) as batch_op:
                batch_op.drop_column(col_name)
        else:
            op.drop_column(table_name, col_name)


def downgrade():
    """回滚：恢复 5 个旧列（nullable=True，旧数据无法恢复但 0 数据无损失）。"""
    bind = op.get_bind()
    is_sqlite = bind.dialect.name == "sqlite"
    for table_name, col_name, col_def in reversed(_LEGACY_COLUMNS):
        if _has_column(table_name, col_name):
            continue
        if is_sqlite:
            with op.batch_alter_table(table_name) as batch_op:
                batch_op.add_column(col_def)
        else:
            op.add_column(table_name, col_def)

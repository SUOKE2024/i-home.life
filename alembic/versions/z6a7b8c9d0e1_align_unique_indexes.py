"""对齐 2 个 unique 索引（a2a_tasks / agent_approvals）

Revision ID: z6a7b8c9d0e1
Revises: z0e1f2a3b4c5
Create Date: 2026-08-06

背景（2026-08-06 schema 差异排查）：
model 声明 `unique=True, index=True`（a2a_tasks.task_id / agent_approvals.approval_id），
但建表迁移（l3c4d5e6f7a8 / u6b7c8d9e0f1）用 op.create_index 漏传 unique →
迁移链建的显式索引 ix_*_task_id / ix_*_approval_id 为**非 unique**，与 model 不一致。

澄清（勿误判为数据完整性 bug）：
两表**均已存在 UNIQUE 约束**兜底——a2a_tasks 列级 unique=True 生成的
sqlite_autoindex、agent_approvals 的 uq_approval_id UniqueConstraint，
故重复数据实际无法插入。本迁移修复的是**迁移链与 model 的元数据不一致**
（冗余非 unique 显式索引），重建为 unique 索引后 compare_db_schema.py 差异收敛。

特性：
  - 幂等：检测索引 unique 标志——已 unique 则 skip，非 unique 则 drop+重建
  - SQLite 无 ALTER INDEX，用 drop_index + create_index(unique=True) 重建
  - downgrade 还原为原迁移链的非 unique 索引（可逆）
"""
from typing import Sequence, Union

import logging

from alembic import op
import sqlalchemy as sa

# 复用 alembic 内置 logger 命名空间：随 alembic 命令输出，无需额外配置
logger = logging.getLogger("alembic.runtime.migration")


# revision identifiers, used by Alembic.
revision: str = "z6a7b8c9d0e1"
down_revision: Union[str, None] = "z0e1f2a3b4c5"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

# (表, 索引名, 列)
_TARGETS = [
    ("a2a_tasks", "ix_a2a_tasks_task_id", ["task_id"]),
    ("agent_approvals", "ix_agent_approvals_approval_id", ["approval_id"]),
]


def _index_unique(table: str, index_name: str) -> bool | None:
    """返回索引是否 unique；不存在返回 None。"""
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    try:
        for ix in inspector.get_indexes(table):
            if ix.get("name") == index_name:
                return bool(ix.get("unique", False))
    except Exception:
        return None
    return None


def upgrade() -> None:
    bind = op.get_bind()
    logger.info("[%s] upgrade start: dialect=%s", revision, bind.dialect.name)

    for table, index_name, columns in _TARGETS:
        unique = _index_unique(table, index_name)
        if unique is None:
            logger.info("[%s] skip: index %s.%s not exists", revision, table, index_name)
            continue
        if unique:
            logger.info("[%s] skip: %s.%s already unique", revision, table, index_name)
            continue
        # 非 unique → 重建为 unique（对齐 model unique=True, index=True）
        op.drop_index(index_name, table_name=table)
        op.create_index(index_name, table, columns, unique=True)
        logger.info("[%s] rebuilt as unique: %s.%s", revision, table, index_name)

    logger.info("[%s] upgrade done", revision)


def downgrade() -> None:
    bind = op.get_bind()
    logger.info("[%s] downgrade start: dialect=%s", revision, bind.dialect.name)

    for table, index_name, columns in _TARGETS:
        unique = _index_unique(table, index_name)
        if unique is None:
            logger.info("[%s] skip: index %s.%s not exists", revision, table, index_name)
            continue
        if not unique:
            logger.info("[%s] skip: %s.%s already non-unique", revision, table, index_name)
            continue
        # 还原为原迁移链的非 unique 索引（可逆）
        op.drop_index(index_name, table_name=table)
        op.create_index(index_name, table, columns)
        logger.info("[%s] reverted to non-unique: %s.%s", revision, table, index_name)

    logger.info("[%s] downgrade done", revision)

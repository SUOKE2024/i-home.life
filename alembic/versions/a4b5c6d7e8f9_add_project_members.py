"""新增 project_members 表（F40 三方协作授权载体）

Revision ID: a4b5c6d7e8f9
Revises: b8c8d9e0f1a2
Create Date: 2026-09-24

背景（2026-09-24 生产环境多角色交叉验证 C-01，Critical）：
  ``app/rbac.py:verify_project_collaborator_access`` 此前只校验「角色 ∈
  {designer, contractor, supplier}」即放行，**不校验该用户与该项目是否存在成员关系**。
  全库存无任何「用户 ↔ 项目」关系实体 → 该函数等价于「任何协作角色可访问全平台任意
  项目」。生产实测：供应商令牌（与目标项目无任何关联）读 ``GET /api/feed/{project_id}``
  返回 200，泄漏 budget_breakdown 逐项材料单价与 settlement_summary（total/paid/balance）。
  同根因波及 9 个 API 模块（feed / chat / files / floorplans / construction_drawing /
  construction_snapshot / hard_decoration / gaussian_recon / vr_panorama）。

本迁移落地 F40「协作方被指派到具体项目」的授权前提。空表时行为变化：
  协作类端点在无成员记录时对非 owner / 非 admin 一律 403（修复前为放行）。
  即修复后需显式 POST 成员才能协作——这是有意的安全收严，非回归。

配套：``app/models/project_member.py``（role 单源 MEMBER_ROLES）+
``app/api/projects.py`` 成员管理端点 + ``tests/test_project_members.py``。
"""
from typing import Sequence, Union

import logging

from alembic import op
import sqlalchemy as sa

logger = logging.getLogger("alembic.runtime.migration")


# revision identifiers, used by Alembic.
revision: str = "a4b5c6d7e8f9"
down_revision: Union[str, None] = "b8c8d9e0f1a2"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

_TABLE = "project_members"


def _has_table(table: str) -> bool:
    bind = op.get_bind()
    return table in set(sa.inspect(bind).get_table_names())


def upgrade() -> None:
    bind = op.get_bind()
    logger.info("[%s] upgrade start: dialect=%s", revision, bind.dialect.name)

    if _has_table(_TABLE):
        logger.info("[%s] skip create table: %s already exists", revision, _TABLE)
        logger.info("[%s] upgrade done (no-op)", revision)
        return

    op.create_table(
        _TABLE,
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("project_id", sa.String(36), sa.ForeignKey("projects.id"), nullable=False),
        sa.Column("user_id", sa.String(36), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("role", sa.String(30), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.UniqueConstraint("project_id", "user_id", name="uq_project_member_project_user"),
        sa.CheckConstraint(
            "role IN ('designer', 'contractor', 'supplier')",
            name="chk_project_member_role",
        ),
    )
    op.create_index("ix_project_members_project_id", _TABLE, ["project_id"])
    op.create_index("ix_project_members_user_id", _TABLE, ["user_id"])
    logger.info("[%s] created table %s + 2 indexes", revision, _TABLE)
    logger.info("[%s] upgrade done", revision)


def downgrade() -> None:
    bind = op.get_bind()
    logger.info("[%s] downgrade start: dialect=%s", revision, bind.dialect.name)

    if not _has_table(_TABLE):
        logger.info("[%s] skip drop table: %s absent", revision, _TABLE)
        logger.info("[%s] downgrade done (no-op)", revision)
        return

    # 先删索引再删表：SQLite batch 模式下索引不随表自动消失（历史教训：
    # drop 带索引的列未先 drop_index 会报 no such column）
    op.drop_index("ix_project_members_user_id", table_name=_TABLE)
    op.drop_index("ix_project_members_project_id", table_name=_TABLE)
    op.drop_table(_TABLE)
    logger.info("[%s] dropped table %s", revision, _TABLE)
    logger.info("[%s] downgrade done", revision)

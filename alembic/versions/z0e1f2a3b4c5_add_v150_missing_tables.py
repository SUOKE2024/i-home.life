"""补 v1.5.0 缺失的 4 张表建表迁移（schema 债修复）

Revision ID: z0e1f2a3b4c5
Revises: y0f1a2b3c4d5
Create Date: 2026-08-06

背景（2026-08-06 空库 downgrade 全链路排查发现）：
F41-F44/F49 的 4 张表（elderly_adaptation_schemes / escrow_trustee_accounts /
material_eco_certs / partial_renovation_plans）只有 ORM model 定义，从未有建表迁移，
仅靠 Base.metadata.create_all 建表。后果：
  - 空库（CI 从零迁移）upgrade head 后缺失这 4 张表（118 vs model 121）
  - check_schema_drift 报 drift；x9e0/w8d9 依赖的表在空库不存在致 downgrade 崩溃
本迁移补齐建表，使 CI 空库迁移与生产 schema 等价。

特性：
  - 幂等：_has_table 检查，本地/生产已有表（create_all 建过）则 skip
  - 列/索引/唯一约束与 app/models 对齐（含 w8d9 的 henf_grade 列）
  - 建表顺序按 FK 依赖：material_eco_certs→materials / 其余→projects/escrow_payments
  - SQLite / PostgreSQL 通用
"""
from typing import Sequence, Union

import logging

from alembic import op
import sqlalchemy as sa

# 复用 alembic 内置 logger 命名空间：随 alembic 命令输出，无需额外配置
logger = logging.getLogger("alembic.runtime.migration")


# revision identifiers, used by Alembic.
revision: str = "z0e1f2a3b4c5"
down_revision: Union[str, None] = "y0f1a2b3c4d5"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _has_table(table: str) -> bool:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    try:
        return table in inspector.get_table_names()
    except Exception:
        return False


def _create_if_missing(table_name: str, create_fn) -> None:
    """幂等建表：表已存在（本地/生产 create_all 建过）则 skip 并记录。"""
    if _has_table(table_name):
        logger.info("[%s] skip: table %s already exists", revision, table_name)
        return
    create_fn()
    logger.info("[%s] created: %s", revision, table_name)


def upgrade() -> None:
    bind = op.get_bind()
    logger.info("[%s] upgrade start: dialect=%s", revision, bind.dialect.name)

    # 1) material_eco_certs — F44 环保材料认证标签（FK→materials，含 F50 henf_grade）
    def _create_eco_certs() -> None:
        op.create_table(
            "material_eco_certs",
            sa.Column("id", sa.String(36), primary_key=True),
            sa.Column("material_id", sa.String(36), nullable=False),
            sa.Column("eco_grade", sa.String(10), nullable=False),
            sa.Column("henf_grade", sa.String(10), nullable=True),
            sa.Column("certification", sa.String(100), nullable=False,
                      server_default="无认证"),
            sa.Column("source", sa.String(20), nullable=False,
                      server_default="third_party"),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False,
                      server_default=sa.text("CURRENT_TIMESTAMP")),
            sa.ForeignKeyConstraint(["material_id"], ["materials.id"]),
            sa.UniqueConstraint("material_id", name="uq_material_eco_certs_material_id"),
        )
        op.create_index("ix_material_eco_certs_material_id", "material_eco_certs", ["material_id"], unique=True)
        op.create_index("ix_material_eco_certs_eco_grade", "material_eco_certs", ["eco_grade"])
        op.create_index("ix_material_eco_certs_henf_grade", "material_eco_certs", ["henf_grade"])

    _create_if_missing("material_eco_certs", _create_eco_certs)

    # 2) partial_renovation_plans — F42 局部焕新计划（FK→projects，含 F49 套餐字段）
    def _create_partial_renovation() -> None:
        op.create_table(
            "partial_renovation_plans",
            sa.Column("id", sa.String(36), primary_key=True),
            sa.Column("project_id", sa.String(36), nullable=False),
            sa.Column("name", sa.String(200), nullable=False),
            sa.Column("scope_type", sa.String(30), nullable=False),
            sa.Column("budget_level", sa.String(20), nullable=False,
                      server_default="comfort"),
            sa.Column("duration_days", sa.Integer(), nullable=False, server_default="7"),
            sa.Column("budget_lower", sa.Float(), nullable=False, server_default="0"),
            sa.Column("budget_upper", sa.Float(), nullable=False, server_default="0"),
            sa.Column("tasks", sa.JSON(), nullable=True),
            sa.Column("interference_plan", sa.JSON(), nullable=True),
            sa.Column("status", sa.String(20), nullable=False, server_default="draft"),
            sa.Column("package_code", sa.String(32), nullable=True),
            sa.Column("fixed_price", sa.Float(), nullable=True),
            sa.Column("dry_construction", sa.Boolean(), nullable=False,
                      server_default=sa.false()),
            sa.Column("zero_relocation", sa.Boolean(), nullable=False,
                      server_default=sa.false()),
            sa.Column("notes", sa.Text(), nullable=True),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False,
                      server_default=sa.text("CURRENT_TIMESTAMP")),
            sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False,
                      server_default=sa.text("CURRENT_TIMESTAMP")),
            sa.ForeignKeyConstraint(["project_id"], ["projects.id"]),
        )
        op.create_index("ix_partial_renovation_plans_project_id", "partial_renovation_plans", ["project_id"])
        op.create_index("ix_partial_renovation_plans_scope_type", "partial_renovation_plans", ["scope_type"])
        op.create_index("ix_partial_renovation_plans_package_code", "partial_renovation_plans", ["package_code"])

    _create_if_missing("partial_renovation_plans", _create_partial_renovation)

    # 3) elderly_adaptation_schemes — F41 适老改造方案（FK→projects）
    def _create_elderly() -> None:
        op.create_table(
            "elderly_adaptation_schemes",
            sa.Column("id", sa.String(36), primary_key=True),
            sa.Column("project_id", sa.String(36), nullable=False),
            sa.Column("name", sa.String(200), nullable=False),
            sa.Column("occupant_type", sa.String(30), nullable=False,
                      server_default="elderly_living"),
            sa.Column("items", sa.JSON(), nullable=True),
            sa.Column("accessibility_report", sa.JSON(), nullable=True),
            sa.Column("compliance_status", sa.String(20), nullable=False,
                      server_default="warning"),
            sa.Column("notes", sa.Text(), nullable=True),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False,
                      server_default=sa.text("CURRENT_TIMESTAMP")),
            sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False,
                      server_default=sa.text("CURRENT_TIMESTAMP")),
            sa.ForeignKeyConstraint(["project_id"], ["projects.id"]),
        )
        op.create_index("ix_elderly_adaptation_schemes_project_id", "elderly_adaptation_schemes", ["project_id"])

    _create_if_missing("elderly_adaptation_schemes", _create_elderly)

    # 4) escrow_trustee_accounts — F43 资金托管存管账户（FK→escrow_payments）
    def _create_escrow_trustee() -> None:
        op.create_table(
            "escrow_trustee_accounts",
            sa.Column("id", sa.String(36), primary_key=True),
            sa.Column("escrow_payment_id", sa.String(36), nullable=False),
            sa.Column("trustee_type", sa.String(20), nullable=False,
                      server_default="bank"),
            sa.Column("account_no_masked", sa.String(30), nullable=False),
            sa.Column("interest_to_owner", sa.Boolean(), nullable=False,
                      server_default=sa.true()),
            sa.Column("owner_confirmed", sa.Boolean(), nullable=False,
                      server_default=sa.false()),
            sa.Column("contractor_confirmed", sa.Boolean(), nullable=False,
                      server_default=sa.false()),
            sa.Column("status", sa.String(30), nullable=False, server_default="active"),
            sa.Column("release_rule", sa.String(30), nullable=False,
                      server_default="node_based"),
            sa.Column("released_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False,
                      server_default=sa.text("CURRENT_TIMESTAMP")),
            sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False,
                      server_default=sa.text("CURRENT_TIMESTAMP")),
            sa.ForeignKeyConstraint(["escrow_payment_id"], ["escrow_payments.id"]),
            sa.UniqueConstraint("escrow_payment_id", name="uq_escrow_trustee_accounts_escrow_payment_id"),
        )
        op.create_index(
            "ix_escrow_trustee_accounts_escrow_payment_id",
            "escrow_trustee_accounts", ["escrow_payment_id"], unique=True,
        )

    _create_if_missing("escrow_trustee_accounts", _create_escrow_trustee)

    logger.info("[%s] upgrade done", revision)


def downgrade() -> None:
    bind = op.get_bind()
    logger.info("[%s] downgrade start: dialect=%s", revision, bind.dialect.name)

    # 逆序删除（先删引用方，FK 依赖安全）；整表删除 SQLite/PG 均用迁移级 op.drop_table
    for table_name in (
        "escrow_trustee_accounts",
        "elderly_adaptation_schemes",
        "partial_renovation_plans",
        "material_eco_certs",
    ):
        if not _has_table(table_name):
            logger.info("[%s] skip: table %s not exists", revision, table_name)
            continue
        op.drop_table(table_name)
        logger.info("[%s] dropped: %s", revision, table_name)
    logger.info("[%s] downgrade done", revision)

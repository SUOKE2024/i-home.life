"""v1.8.0: Agent Skill 资产化 — 新建 agent_skills 表

Revision ID: t5a6b7c8d9e0
Revises: s4a5b6c7d8e9
Create Date: 2026-08-03 14:00:00.000000

借鉴 YC QM（2026-07-31 开源）的 Skill 设计：
- scope-owned：每个 Skill 归属 personal/project/team/org 作用域
- share by grant：可授权给指定用户/团队
- admin gated promotion：提升到 org 级需 admin 审核
- 版本化 + 回退：每次更新 version+1，可回退到历史版本
- skill_pack 导入：从 git URL 导入外部 Skill 包

迁移采用幂等设计（与 j0f5a9c2d4e6_add_agent_memory_scope.py 风格一致）。
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 't5a6b7c8d9e0'
down_revision: Union[str, None] = 's4a5b6c7d8e9'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

_TABLE_NAME = 'agent_skills'


def upgrade() -> None:
    conn = op.get_bind()
    inspector = sa.inspect(conn)

    if inspector.has_table(_TABLE_NAME):
        print(f"  skip: table {_TABLE_NAME} already exists")
        return

    op.create_table(
        _TABLE_NAME,
        sa.Column('id', sa.String(36), nullable=False),
        sa.Column('name', sa.String(100), nullable=False),
        sa.Column('description', sa.Text(), nullable=False, server_default=''),
        sa.Column('owner_scope', sa.String(20), nullable=False),
        sa.Column('owner_id', sa.String(36), nullable=False),
        sa.Column('agent_name', sa.String(50), nullable=False),
        sa.Column('system_prompt', sa.Text(), nullable=False, server_default=''),
        sa.Column('provider', sa.String(30), nullable=False, server_default='deepseek'),
        sa.Column('tools', sa.Text(), nullable=False, server_default='[]'),
        sa.Column('cost_tier', sa.String(20), nullable=False, server_default='standard'),
        sa.Column('acceptance_criteria', sa.Text(), nullable=False, server_default='[]'),
        sa.Column('version', sa.Integer(), nullable=False, server_default='1'),
        sa.Column('status', sa.String(20), nullable=False, server_default='draft'),
        sa.Column('parent_version_id', sa.String(36), nullable=True),
        sa.Column('share_scope', sa.String(20), nullable=False, server_default='none'),
        sa.Column('share_grants', sa.Text(), nullable=False, server_default='[]'),
        sa.Column('created_by', sa.String(36), nullable=False),
        sa.Column('reviewed_by', sa.String(36), nullable=True),
        sa.Column('reviewed_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('skill_pack_source', sa.String(500), nullable=True),
        sa.Column('deleted_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            'created_at', sa.DateTime(timezone=True),
            server_default=sa.func.now(), nullable=False,
        ),
        sa.Column(
            'updated_at', sa.DateTime(timezone=True),
            server_default=sa.func.now(), nullable=False,
        ),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint(
            'owner_scope', 'owner_id', 'name', 'version',
            name='uq_skill_owner_name_ver',
        ),
        sa.CheckConstraint(
            "status IN ('draft', 'active', 'archived')", name='chk_skill_status',
        ),
        sa.CheckConstraint(
            "owner_scope IN ('personal', 'project', 'team', 'org')",
            name='chk_skill_owner_scope',
        ),
        sa.CheckConstraint(
            "share_scope IN ('none', 'grant', 'org')", name='chk_skill_share_scope',
        ),
        sa.ForeignKeyConstraint(['created_by'], ['users.id']),
    )
    op.create_index('ix_agent_skills_owner_scope', _TABLE_NAME, ['owner_scope'])
    op.create_index('ix_agent_skills_owner_id', _TABLE_NAME, ['owner_id'])
    op.create_index('ix_agent_skills_status', _TABLE_NAME, ['status'])
    op.create_index('ix_agent_skills_created_by', _TABLE_NAME, ['created_by'])
    print(f"  created: table {_TABLE_NAME}")


def downgrade() -> None:
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    if not inspector.has_table(_TABLE_NAME):
        return
    op.drop_table(_TABLE_NAME)
    print(f"  dropped: table {_TABLE_NAME}")

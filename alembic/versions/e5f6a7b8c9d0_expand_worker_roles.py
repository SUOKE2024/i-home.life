"""expand worker roles: add carpenter, plumber_electrician, curtain_installer

Revision ID: e5f6a7b8c9d0
Revises: d4e5f6a7b8c9
Create Date: 2026-07-16

服务者角色扩展：新增 3 个施工工种
- carpenter: 木工
- plumber_electrician: 水电安装工
- curtain_installer: 窗帘安装工

注意：本迁移无 DDL 变更。
role 字段为 VARCHAR(20)，已能容纳新角色名。
role_attributes 为 TEXT(JSON)，由应用层管理结构。
此迁移主要用于版本追踪和部署记录。
"""

from alembic import op
import sqlalchemy as sa

# revision identifiers
revision = 'e5f6a7b8c9d0'
down_revision = 'd4e5f6a7b8c9'
branch_labels = None
depends_on = None


def upgrade():
    # 无 schema 变更 — role 字段 VARCHAR(20) 已支持新值
    # 此迁移仅作版本标记
    pass


def downgrade():
    # 无需回滚 — 旧角色值依然合法
    pass

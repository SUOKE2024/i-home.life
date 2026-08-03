"""add project card collect fields (house_type/location/contact)

Revision ID: r0a1b2c3d4e5
Revises: q1f2e3d4c5b6
Create Date: 2026-08-02

创建项目卡片时 UI 收集的户型/定位/联系方式此前被静默丢弃（schema 无对应字段）。
为 projects 表补 6 个可空列：
  - description   String(500) 项目描述
  - house_type    String(50)  户型（公寓/别墅/... 或户型描述字符串）
  - latitude      Float       纬度
  - longitude     Float       经度
  - contact_name  String(100) 联系人姓名
  - contact_phone String(30)  联系电话

特性：
  - 幂等：has_column 检查已存在则跳过
  - SQLite batch mode 兼容
  - 回滚：DROP COLUMN
"""
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = "r0a1b2c3d4e5"
down_revision = "q1f2e3d4c5b6"
branch_labels = None
depends_on = None

_COLUMNS = [
    ("description", sa.Column("description", sa.String(500), nullable=True)),
    ("house_type", sa.Column("house_type", sa.String(50), nullable=True)),
    ("latitude", sa.Column("latitude", sa.Float(), nullable=True)),
    ("longitude", sa.Column("longitude", sa.Float(), nullable=True)),
    ("contact_name", sa.Column("contact_name", sa.String(100), nullable=True)),
    ("contact_phone", sa.Column("contact_phone", sa.String(30), nullable=True)),
]


def _has_column(table_name: str, column_name: str) -> bool:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    try:
        cols = [c["name"] for c in inspector.get_columns(table_name)]
    except Exception:
        return True  # 表不存在视为已处理，避免报错
    return column_name in cols


def upgrade():
    bind = op.get_bind()
    is_sqlite = bind.dialect.name == "sqlite"
    for col_name, col in _COLUMNS:
        if _has_column("projects", col_name):
            continue
        if is_sqlite:
            with op.batch_alter_table("projects") as batch_op:
                batch_op.add_column(col)
        else:
            op.add_column("projects", col)


def downgrade():
    bind = op.get_bind()
    is_sqlite = bind.dialect.name == "sqlite"
    for col_name, _ in reversed(_COLUMNS):
        if not _has_column("projects", col_name):
            continue
        if is_sqlite:
            with op.batch_alter_table("projects") as batch_op:
                batch_op.drop_column(col_name)
        else:
            op.drop_column("projects", col_name)

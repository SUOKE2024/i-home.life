"""add FK indexes to projects.owner_id, floors.project_id, rooms.floor_id

Revision ID: d4e5f6a7b8c9
Revises: c3d4e5f6a7b8
Create Date: 2026-07-16 09:00:00.000000

为 Project.owner_id / Floor.project_id / Room.floor_id 添加索引，
提升按项目/楼层查询的性能（这些是高频过滤字段）。
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'd4e5f6a7b8c9'
down_revision: Union[str, None] = 'c3d4e5f6a7b8'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


# (index_name, table_name, column_name)
_INDEXES = [
    ('ix_projects_owner_id', 'projects', 'owner_id'),
    ('ix_floors_project_id', 'floors', 'project_id'),
    ('ix_rooms_floor_id', 'rooms', 'floor_id'),
]


def upgrade() -> None:
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    existing_indexes = {
        (idx['name'])
        for tbl in inspector.get_table_names()
        for idx in inspector.get_indexes(tbl)
        if idx.get('name')
    }
    for index_name, table_name, column_name in _INDEXES:
        if table_name not in inspector.get_table_names():
            continue
        if index_name in existing_indexes:
            continue
        op.create_index(index_name, table_name, [column_name])


def downgrade() -> None:
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    existing_indexes = {
        (idx['name'])
        for tbl in inspector.get_table_names()
        for idx in inspector.get_indexes(tbl)
        if idx.get('name')
    }
    for index_name, _table_name, _column_name in _INDEXES:
        if index_name in existing_indexes:
            op.drop_index(index_name)

"""add webauthn passkey support

Revision ID: b2c3d4e5f6a7
Revises: a1b2c3d4e5f6
Create Date: 2026-07-14 12:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'b2c3d4e5f6a7'
down_revision: Union[str, None] = 'a1b2c3d4e5f6'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 清理前次失败残留的临时表
    conn = op.get_bind()
    conn.exec_driver_sql("DROP TABLE IF EXISTS _alembic_tmp_users")
    conn.exec_driver_sql("DROP TABLE IF EXISTS _alembic_tmp_webauthn_credentials")

    # 1. 让 users.hashed_password 变为可空（支持纯 Passkey 用户）
    with op.batch_alter_table('users') as batch_op:
        batch_op.alter_column('hashed_password',
                              existing_type=sa.String(length=200),
                              nullable=True)

    # 2. 创建 webauthn_credentials 表（若不存在）
    inspector = sa.inspect(conn)
    if 'webauthn_credentials' not in inspector.get_table_names():
        op.create_table(
            'webauthn_credentials',
            sa.Column('id', sa.String(length=36), nullable=False),
            sa.Column('user_id', sa.String(length=36), nullable=False),
            sa.Column('credential_id', sa.String(length=512), nullable=False),
            sa.Column('public_key', sa.Text(), nullable=False),
            sa.Column('sign_count', sa.Integer(), nullable=False, server_default='0'),
            sa.Column('device_name', sa.String(length=200), nullable=True),
            sa.Column('credential_type', sa.String(length=50), nullable=True),
            sa.Column('aaguid', sa.String(length=36), nullable=True),
            sa.Column('is_passkey', sa.Boolean(), nullable=False, server_default='0'),
            sa.Column('is_active', sa.Boolean(), nullable=False, server_default='1'),
            sa.Column('last_used_at', sa.DateTime(), server_default=sa.func.now()),
            sa.Column('created_at', sa.DateTime(), server_default=sa.func.now()),
            sa.PrimaryKeyConstraint('id'),
            sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
        )
        with op.batch_alter_table('webauthn_credentials') as batch_op:
            batch_op.create_index('ix_webauthn_credentials_user_id', ['user_id'])
            batch_op.create_index('ix_webauthn_credentials_credential_id', ['credential_id'], unique=True)


def downgrade() -> None:
    op.drop_table('webauthn_credentials')
    with op.batch_alter_table('users') as batch_op:
        batch_op.alter_column('hashed_password',
                              existing_type=sa.String(length=200),
                              nullable=False)

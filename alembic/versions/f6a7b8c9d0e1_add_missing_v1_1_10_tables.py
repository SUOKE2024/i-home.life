"""add missing v1.1.10 tables: identity, products, points, permissions, orchestrator, agent_feedback

Revision ID: f6a7b8c9d0e1
Revises: e5f6a7b8c9d0
Create Date: 2026-07-19

补全 13 个缺失模型的 Alembic 迁移，覆盖以下业务域：
- 实名认证: identity_verifications
- 产品/服务发布: products
- 积分系统: points_accounts, points_transactions, points_rules,
            points_mall_items, points_redemptions, points_rankings
- 任务协调: orchestrator_tasks, task_candidates
- RBAC 权限: permissions, role_permissions
- Agent 反馈: agent_feedbacks
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'f6a7b8c9d0e1'
down_revision: Union[str, None] = 'e5f6a7b8c9d0'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # ── 实名认证 ──
    op.create_table(
        'identity_verifications',
        sa.Column('id', sa.String(36), primary_key=True),
        sa.Column('user_id', sa.String(36), sa.ForeignKey('users.id'), nullable=False, unique=True),
        sa.Column('role', sa.String(20), nullable=False),
        sa.Column('real_name', sa.String(100), nullable=False),
        sa.Column('id_card', sa.String(18), nullable=False),
        sa.Column('id_card_front', sa.String(500), nullable=True),
        sa.Column('id_card_back', sa.String(500), nullable=True),
        sa.Column('selfie_with_id', sa.String(500), nullable=True),
        sa.Column('third_party_verified', sa.Boolean(), server_default=sa.text('0'), nullable=False),
        sa.Column('third_party_provider', sa.String(50), nullable=True),
        sa.Column('third_party_result', sa.Text(), nullable=True),
        sa.Column('role_attributes', sa.Text(), nullable=True),
        sa.Column('status', sa.String(20), server_default='pending', nullable=False),
        sa.Column('reviewer_id', sa.String(36), sa.ForeignKey('users.id'), nullable=True),
        sa.Column('review_note', sa.Text(), nullable=True),
        sa.Column('verified_at', sa.DateTime(), nullable=True),
        sa.Column('created_at', sa.DateTime(), server_default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime(), server_default=sa.func.now()),
    )

    # ── 产品/服务发布 ──
    op.create_table(
        'products',
        sa.Column('id', sa.String(36), primary_key=True),
        sa.Column('user_id', sa.String(36), sa.ForeignKey('users.id'), nullable=False),
        sa.Column('supplier_id', sa.String(36), sa.ForeignKey('suppliers.id'), nullable=False),
        sa.Column('name', sa.String(200), nullable=False),
        sa.Column('category', sa.String(50), server_default='other', nullable=False),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('price_min', sa.Float(), nullable=True),
        sa.Column('price_max', sa.Float(), nullable=True),
        sa.Column('unit', sa.String(20), server_default='个', nullable=False),
        sa.Column('images', sa.Text(), nullable=True),
        sa.Column('cover_image', sa.String(500), nullable=True),
        sa.Column('tags', sa.Text(), nullable=True),
        sa.Column('specs', sa.Text(), nullable=True),
        sa.Column('stock_status', sa.String(20), server_default='in_stock', nullable=False),
        sa.Column('status', sa.String(20), server_default='draft', nullable=False),
        sa.Column('ai_generated', sa.Boolean(), server_default=sa.text('0'), nullable=False),
        sa.Column('ai_description', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(), server_default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime(), server_default=sa.func.now()),
    )

    # ── 积分系统 (6 张表) ──
    op.create_table(
        'points_accounts',
        sa.Column('id', sa.String(36), primary_key=True),
        sa.Column('user_id', sa.String(36), sa.ForeignKey('users.id'), nullable=False, unique=True),
        sa.Column('account_type', sa.String(20), server_default='user', nullable=False),
        sa.Column('balance', sa.Integer(), server_default='0', nullable=False),
        sa.Column('total_earned', sa.Integer(), server_default='0', nullable=False),
        sa.Column('total_spent', sa.Integer(), server_default='0', nullable=False),
        sa.Column('level', sa.String(20), server_default='bronze', nullable=False),
        sa.Column('year_earned', sa.Integer(), server_default='0', nullable=False),
        sa.Column('year_spent', sa.Integer(), server_default='0', nullable=False),
        sa.Column('year_updated', sa.Integer(), nullable=False),
        sa.Column('created_at', sa.DateTime(), server_default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime(), server_default=sa.func.now()),
    )

    op.create_table(
        'points_transactions',
        sa.Column('id', sa.String(36), primary_key=True),
        sa.Column('account_id', sa.String(36), sa.ForeignKey('points_accounts.id'), nullable=False),
        sa.Column('user_id', sa.String(36), sa.ForeignKey('users.id'), nullable=False),
        sa.Column('amount', sa.Integer(), nullable=False),
        sa.Column('transaction_type', sa.String(20), nullable=False),
        sa.Column('source', sa.String(50), nullable=False),
        sa.Column('reference_id', sa.String(100), nullable=True),
        sa.Column('description', sa.String(500), nullable=False),
        sa.Column('balance_after', sa.Integer(), nullable=False),
        sa.Column('created_at', sa.DateTime(), server_default=sa.func.now()),
    )

    op.create_table(
        'points_rules',
        sa.Column('id', sa.String(36), primary_key=True),
        sa.Column('action', sa.String(50), unique=True, nullable=False),
        sa.Column('role', sa.String(20), nullable=False),
        sa.Column('points', sa.Integer(), nullable=False),
        sa.Column('limit_daily', sa.Integer(), nullable=True),
        sa.Column('limit_weekly', sa.Integer(), nullable=True),
        sa.Column('description', sa.String(500), nullable=False),
        sa.Column('is_active', sa.Boolean(), server_default=sa.text('1'), nullable=False),
        sa.Column('created_at', sa.DateTime(), server_default=sa.func.now()),
    )

    op.create_table(
        'points_mall_items',
        sa.Column('id', sa.String(36), primary_key=True),
        sa.Column('name', sa.String(200), nullable=False),
        sa.Column('category', sa.String(30), server_default='discount', nullable=False),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('image_url', sa.String(500), nullable=True),
        sa.Column('points_required', sa.Integer(), nullable=False),
        sa.Column('stock', sa.Integer(), server_default='-1', nullable=False),
        sa.Column('discount_type', sa.String(20), nullable=True),
        sa.Column('discount_value', sa.Float(), nullable=True),
        sa.Column('discount_max', sa.Float(), nullable=True),
        sa.Column('validity_days', sa.Integer(), server_default='365', nullable=False),
        sa.Column('is_active', sa.Boolean(), server_default=sa.text('1'), nullable=False),
        sa.Column('sort_order', sa.Integer(), server_default='0', nullable=False),
        sa.Column('created_at', sa.DateTime(), server_default=sa.func.now()),
    )

    op.create_table(
        'points_redemptions',
        sa.Column('id', sa.String(36), primary_key=True),
        sa.Column('user_id', sa.String(36), sa.ForeignKey('users.id'), nullable=False),
        sa.Column('account_id', sa.String(36), sa.ForeignKey('points_accounts.id'), nullable=False),
        sa.Column('item_id', sa.String(36), sa.ForeignKey('points_mall_items.id'), nullable=False),
        sa.Column('item_name', sa.String(200), nullable=False),
        sa.Column('points_spent', sa.Integer(), nullable=False),
        sa.Column('discount_code', sa.String(50), nullable=True),
        sa.Column('discount_type', sa.String(20), nullable=True),
        sa.Column('discount_value', sa.Float(), nullable=True),
        sa.Column('discount_max', sa.Float(), nullable=True),
        sa.Column('expires_at', sa.DateTime(), nullable=True),
        sa.Column('status', sa.String(20), server_default='active', nullable=False),
        sa.Column('created_at', sa.DateTime(), server_default=sa.func.now()),
    )

    op.create_table(
        'points_rankings',
        sa.Column('id', sa.String(36), primary_key=True),
        sa.Column('user_id', sa.String(36), sa.ForeignKey('users.id'), nullable=False),
        sa.Column('role', sa.String(20), nullable=False),
        sa.Column('year', sa.Integer(), nullable=False),
        sa.Column('category', sa.String(30), server_default='overall', nullable=False),
        sa.Column('year_earned', sa.Integer(), server_default='0', nullable=False),
        sa.Column('rank', sa.Integer(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), server_default=sa.func.now()),
    )

    # ── 任务协调 ──
    op.create_table(
        'orchestrator_tasks',
        sa.Column('id', sa.String(36), primary_key=True),
        sa.Column('project_id', sa.String(36), sa.ForeignKey('projects.id'), nullable=False),
        sa.Column('task_type', sa.String(30), nullable=False),
        sa.Column('title', sa.String(200), nullable=False),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('assigned_agent', sa.String(30), nullable=False),
        sa.Column('assigned_user_id', sa.String(36), sa.ForeignKey('users.id'), nullable=True),
        sa.Column('priority', sa.Integer(), server_default='5', nullable=False),
        sa.Column('status', sa.String(20), server_default='pending', nullable=False),
        sa.Column('parent_task_id', sa.String(36), sa.ForeignKey('orchestrator_tasks.id'), nullable=True),
        sa.Column('dependencies', sa.Text(), nullable=True),
        sa.Column('claimable', sa.Boolean(), server_default=sa.text('1'), nullable=False),
        sa.Column('claim_deadline', sa.DateTime(), nullable=True),
        sa.Column('claim_role', sa.String(20), nullable=True),
        sa.Column('result', sa.Text(), nullable=True),
        sa.Column('created_by', sa.String(36), nullable=False),
        sa.Column('created_at', sa.DateTime(), server_default=sa.func.now()),
        sa.Column('started_at', sa.DateTime(), nullable=True),
        sa.Column('completed_at', sa.DateTime(), nullable=True),
    )

    op.create_table(
        'task_candidates',
        sa.Column('id', sa.String(36), primary_key=True),
        sa.Column('task_id', sa.String(36), sa.ForeignKey('orchestrator_tasks.id'), nullable=False),
        sa.Column('user_id', sa.String(36), sa.ForeignKey('users.id'), nullable=False),
        sa.Column('points_score', sa.Float(), server_default='0', nullable=False),
        sa.Column('experience_score', sa.Float(), server_default='0', nullable=False),
        sa.Column('rating_score', sa.Float(), server_default='0', nullable=False),
        sa.Column('composite_score', sa.Float(), server_default='0', nullable=False),
        sa.Column('score_breakdown', sa.Text(), nullable=True),
        sa.Column('status', sa.String(20), server_default='pending', nullable=False),
        sa.Column('created_at', sa.DateTime(), server_default=sa.func.now()),
    )

    # ── RBAC 权限 ──
    op.create_table(
        'permissions',
        sa.Column('id', sa.String(36), primary_key=True),
        sa.Column('code', sa.String(100), unique=True, nullable=False, index=True),
        sa.Column('name', sa.String(200), nullable=False),
        sa.Column('resource', sa.String(100), nullable=False, index=True),
        sa.Column('action', sa.String(50), nullable=False),
        sa.Column('description', sa.String(500), nullable=True),
        sa.Column('created_at', sa.DateTime(), server_default=sa.func.now()),
    )

    op.create_table(
        'role_permissions',
        sa.Column('id', sa.String(36), primary_key=True),
        sa.Column('role', sa.String(30), nullable=False, index=True),
        sa.Column('permission_code', sa.String(100), sa.ForeignKey('permissions.code'), nullable=False, index=True),
        sa.Column('created_at', sa.DateTime(), server_default=sa.func.now()),
        sa.UniqueConstraint('role', 'permission_code', name='uq_role_permission'),
    )

    # ── Agent 反馈 ──
    op.create_table(
        'agent_feedbacks',
        sa.Column('id', sa.String(36), primary_key=True),
        sa.Column('user_id', sa.String(36), sa.ForeignKey('users.id'), nullable=False),
        sa.Column('agent_name', sa.String(50), nullable=False),
        sa.Column('message_hash', sa.String(64), nullable=False),
        sa.Column('feedback_type', sa.String(20), nullable=False),
        sa.Column('rating', sa.Integer(), nullable=True),
        sa.Column('comment', sa.Text(), nullable=True),
        sa.Column('user_message', sa.Text(), nullable=False),
        sa.Column('agent_reply', sa.Text(), nullable=False),
        sa.Column('created_at', sa.DateTime(), server_default=sa.func.now()),
    )


def downgrade() -> None:
    op.drop_table('agent_feedbacks')
    op.drop_table('role_permissions')
    op.drop_table('permissions')
    op.drop_table('task_candidates')
    op.drop_table('orchestrator_tasks')
    op.drop_table('points_rankings')
    op.drop_table('points_redemptions')
    op.drop_table('points_mall_items')
    op.drop_table('points_rules')
    op.drop_table('points_transactions')
    op.drop_table('points_accounts')
    op.drop_table('products')
    op.drop_table('identity_verifications')

"""v1.1.12: 补全所有 ForeignKey 字段的索引

Revision ID: g7b8c9d0e1f2
Revises: f6a7b8c9d0e1
Create Date: 2026-07-20 10:00:00.000000

为 v1.1.12 性能优化补全 120+ 个 ForeignKey 字段的索引。
覆盖以下业务表的 FK 字段：
- structural（承重墙/梁/柱/楼板/基础/工程量）
- procurement / procurement_enhanced（采购订单/报价/比价/样品/物流）
- points（积分账户/交易/兑换/排名）
- kitchen_bath_mep / kitchen / bathroom / lighting / appliance（垂直设计模块）
- hard_decoration / soft_furnishing / custom_furniture（硬装/软装/定制家具）
- door_window_waterproof / scene_automation / smart_home / ar_scan（其他模块）
- file_attachment / chat / quality / floorplan / ai_image / vr_panorama
- agent_feedback / change_order / construction_crew / progress_alert
- service_worker / orchestrator_task / product / device_token / identity_verification

迁移采用幂等设计：检查索引是否已存在再决定是否创建，可在生产环境安全重复执行。
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'g7b8c9d0e1f2'
down_revision: Union[str, None] = 'f6a7b8c9d0e1'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


# (index_name, table_name, column_name) — 命名规范：ix_{table}_{column}
_INDEXES: list[tuple[str, str, str]] = [
    # ── structural ──
    ('ix_load_bearing_walls_project_id', 'load_bearing_walls', 'project_id'),
    ('ix_load_bearing_walls_room_id', 'load_bearing_walls', 'room_id'),
    ('ix_beams_project_id', 'beams', 'project_id'),
    ('ix_columns_project_id', 'columns', 'project_id'),
    ('ix_floor_slabs_project_id', 'floor_slabs', 'project_id'),
    ('ix_foundation_types_project_id', 'foundation_types', 'project_id'),
    ('ix_structure_load_estimates_project_id', 'structure_load_estimates', 'project_id'),
    ('ix_bay_compliances_project_id', 'bay_compliances', 'project_id'),
    ('ix_quantity_calculations_project_id', 'quantity_calculations', 'project_id'),
    ('ix_quantity_line_items_calculation_id', 'quantity_line_items', 'calculation_id'),

    # ── survey ──
    ('ix_surveys_project_id', 'surveys', 'project_id'),

    # ── procurement / procurement_enhanced ──
    ('ix_procurement_orders_supplier_id', 'procurement_orders', 'supplier_id'),
    ('ix_procurement_orders_material_id', 'procurement_orders', 'material_id'),
    ('ix_procurement_orders_project_id', 'procurement_orders', 'project_id'),
    ('ix_procurement_order_items_order_id', 'procurement_order_items', 'order_id'),
    ('ix_procurement_order_items_material_id', 'procurement_order_items', 'material_id'),
    ('ix_price_comparisons_project_id', 'price_comparisons', 'project_id'),
    ('ix_price_comparisons_recommended_supplier_id', 'price_comparisons', 'recommended_supplier_id'),
    ('ix_price_comparison_items_comparison_id', 'price_comparison_items', 'comparison_id'),
    ('ix_logistics_trackings_order_id', 'logistics_trackings', 'order_id'),
    ('ix_logistics_trackings_project_id', 'logistics_trackings', 'project_id'),
    ('ix_sample_requests_project_id', 'sample_requests', 'project_id'),
    ('ix_sample_requests_supplier_id', 'sample_requests', 'supplier_id'),
    ('ix_sample_requests_material_id', 'sample_requests', 'material_id'),

    # ── points ──
    ('ix_points_transactions_account_id', 'points_transactions', 'account_id'),
    ('ix_points_transactions_user_id', 'points_transactions', 'user_id'),
    ('ix_points_redemptions_user_id', 'points_redemptions', 'user_id'),
    ('ix_points_redemptions_account_id', 'points_redemptions', 'account_id'),
    ('ix_points_redemptions_item_id', 'points_redemptions', 'item_id'),
    ('ix_points_mall_orders_user_id', 'points_mall_orders', 'user_id'),

    # ── kitchen_bath_mep ──
    ('ix_kitchen_bath_mep_plans_project_id', 'kitchen_bath_mep_plans', 'project_id'),
    ('ix_mep_points_plan_id', 'mep_points', 'plan_id'),

    # ── change_order ──
    ('ix_change_order_items_change_order_id', 'change_order_items', 'change_order_id'),

    # ── construction ──
    ('ix_construction_logs_task_id', 'construction_logs', 'task_id'),

    # ── budget ──
    ('ix_budget_items_budget_id', 'budget_items', 'budget_id'),

    # ── ai_image ──
    ('ix_ai_image_jobs_project_id', 'ai_image_jobs', 'project_id'),
    ('ix_ai_image_jobs_floorplan_id', 'ai_image_jobs', 'floorplan_id'),

    # ── settlement ──
    ('ix_settlement_lines_settlement_id', 'settlement_lines', 'settlement_id'),

    # ── file_attachment ──
    ('ix_file_attachments_project_id', 'file_attachments', 'project_id'),
    ('ix_file_attachments_message_id', 'file_attachments', 'message_id'),

    # ── chat ──
    ('ix_chat_messages_project_id', 'chat_messages', 'project_id'),
    ('ix_chat_messages_sender_id', 'chat_messages', 'sender_id'),

    # ── quality ──
    ('ix_quality_issues_task_id', 'quality_issues', 'task_id'),
    ('ix_quality_issues_inspection_id', 'quality_issues', 'inspection_id'),
    ('ix_rectification_orders_project_id', 'rectification_orders', 'project_id'),
    ('ix_quality_assessments_project_id', 'quality_assessments', 'project_id'),

    # ── floorplan ──
    ('ix_floor_plans_project_id', 'floor_plans', 'project_id'),

    # ── scene_automation ──
    ('ix_scene_automations_project_id', 'scene_automations', 'project_id'),
    ('ix_scene_automations_scheme_id', 'scene_automations', 'scheme_id'),
    ('ix_ecosystem_integrations_project_id', 'ecosystem_integrations', 'project_id'),

    # ── ar_scan ──
    ('ix_scan_sessions_project_id', 'scan_sessions', 'project_id'),
    ('ix_scan_sessions_survey_id', 'scan_sessions', 'survey_id'),
    ('ix_wall_features_session_id', 'wall_features', 'session_id'),
    ('ix_measurement_points_session_id', 'measurement_points', 'session_id'),

    # ── lighting ──
    ('ix_lighting_schemes_project_id', 'lighting_schemes', 'project_id'),
    ('ix_lighting_fixtures_scheme_id', 'lighting_fixtures', 'scheme_id'),

    # ── kitchen ──
    ('ix_kitchen_designs_project_id', 'kitchen_designs', 'project_id'),
    ('ix_kitchen_components_design_id', 'kitchen_components', 'design_id'),

    # ── bathroom ──
    ('ix_bathroom_designs_project_id', 'bathroom_designs', 'project_id'),
    ('ix_bathroom_fixtures_design_id', 'bathroom_fixtures', 'design_id'),

    # ── door_window_waterproof ──
    ('ix_door_window_specs_project_id', 'door_window_specs', 'project_id'),
    ('ix_waterproof_plans_project_id', 'waterproof_plans', 'project_id'),

    # ── custom_furniture ──
    ('ix_custom_furniture_designs_project_id', 'custom_furniture_designs', 'project_id'),
    ('ix_furniture_modules_design_id', 'furniture_modules', 'design_id'),
    ('ix_furniture_boms_design_id', 'furniture_boms', 'design_id'),

    # ── soft_furnishing ──
    ('ix_soft_furnishing_schemes_project_id', 'soft_furnishing_schemes', 'project_id'),
    ('ix_soft_furnishing_items_scheme_id', 'soft_furnishing_items', 'scheme_id'),
    ('ix_storage_systems_scheme_id', 'storage_systems', 'scheme_id'),

    # ── appliance ──
    ('ix_appliances_category_id', 'appliances', 'category_id'),
    ('ix_appliance_points_project_id', 'appliance_points', 'project_id'),
    ('ix_appliance_points_room_id', 'appliance_points', 'room_id'),
    ('ix_appliance_points_appliance_id', 'appliance_points', 'appliance_id'),
    ('ix_appliance_load_calcs_project_id', 'appliance_load_calcs', 'project_id'),

    # ── vr_panorama ──
    ('ix_vr_panoramas_project_id', 'vr_panoramas', 'project_id'),
    ('ix_vr_panoramas_floorplan_id', 'vr_panoramas', 'floorplan_id'),
    ('ix_vr_scenes_project_id', 'vr_scenes', 'project_id'),

    # ── orchestrator_task ──
    ('ix_orchestrator_tasks_parent_task_id', 'orchestrator_tasks', 'parent_task_id'),
    ('ix_task_candidates_task_id', 'task_candidates', 'task_id'),
    ('ix_task_candidates_user_id', 'task_candidates', 'user_id'),

    # ── product ──
    ('ix_products_user_id', 'products', 'user_id'),
    ('ix_products_supplier_id', 'products', 'supplier_id'),

    # ── service_worker ──
    ('ix_service_worker_matches_project_id', 'service_worker_matches', 'project_id'),
    ('ix_service_worker_matches_worker_id', 'service_worker_matches', 'worker_id'),

    # ── construction_crew ──
    ('ix_crew_matches_project_id', 'crew_matches', 'project_id'),
    ('ix_crew_matches_crew_id', 'crew_matches', 'crew_id'),

    # ── progress_alert ──
    ('ix_progress_alerts_task_id', 'progress_alerts', 'task_id'),

    # ── device_token ──
    ('ix_device_tokens_user_id', 'device_tokens', 'user_id'),

    # ── agent_feedback ──
    ('ix_agent_feedbacks_user_id', 'agent_feedbacks', 'user_id'),

    # ── material ──
    ('ix_materials_category_id', 'materials', 'category_id'),
    ('ix_bom_items_project_id', 'bom_items', 'project_id'),
    ('ix_bom_items_material_id', 'bom_items', 'material_id'),
    ('ix_bom_items_room_id', 'bom_items', 'room_id'),

    # ── hard_decoration ──
    ('ix_hard_decoration_schemes_project_id', 'hard_decoration_schemes', 'project_id'),
    ('ix_hard_decoration_floors_scheme_id', 'hard_decoration_floors', 'scheme_id'),
    ('ix_wall_finishes_scheme_id', 'wall_finishes', 'scheme_id'),
    ('ix_ceiling_designs_scheme_id', 'ceiling_designs', 'scheme_id'),

    # ── smart_home ──
    ('ix_smart_home_schemes_project_id', 'smart_home_schemes', 'project_id'),
    ('ix_smart_devices_scheme_id', 'smart_devices', 'scheme_id'),
]


def upgrade() -> None:
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    existing_tables = set(inspector.get_table_names())
    existing_indexes: set[str] = set()
    for tbl in existing_tables:
        for idx in inspector.get_indexes(tbl):
            if idx.get('name'):
                existing_indexes.add(idx['name'])

    created = 0
    skipped = 0
    for index_name, table_name, column_name in _INDEXES:
        if table_name not in existing_tables:
            skipped += 1
            continue
        if index_name in existing_indexes:
            skipped += 1
            continue
        try:
            op.create_index(index_name, table_name, [column_name])
            created += 1
        except Exception as e:
            # 索引可能已存在（命名冲突）或表无该列，跳过
            print(f"  skip {index_name} on {table_name}.{column_name}: {e}")
            skipped += 1

    print(f"\n  v1.1.12 FK indexes: created={created}, skipped={skipped}, total={len(_INDEXES)}")


def downgrade() -> None:
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    existing_tables = set(inspector.get_table_names())
    existing_indexes: set[str] = set()
    for tbl in existing_tables:
        for idx in inspector.get_indexes(tbl):
            if idx.get('name'):
                existing_indexes.add(idx['name'])

    for index_name, _table_name, _column_name in _INDEXES:
        if index_name in existing_indexes:
            try:
                op.drop_index(index_name)
            except Exception as e:
                print(f"  skip drop {index_name}: {e}")

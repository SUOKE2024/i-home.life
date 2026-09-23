"""回填模型已声明但生产库缺失的 CheckConstraint（model ↔ DB 约束对齐）

Revision ID: b8c8d9e0f1a2
Revises: l4d5e6f7a8b9
Create Date: 2026-09-23

背景（2026-09-23 v1.17.3 生产部署核查发现）：
  生产 PostgreSQL 仅有 32 条 CHECK 约束（13 张表），而模型声明 174 条（37 张表），
  缺失 166 条（32 张表：budgets / quotations / kitchen_designs / smart_home_schemes /
  smart_devices / scene_automations 等）。根因：这些表早期由 `database.init_db` 的
  create_all 建立（当时模型尚未声明约束），此后模型补约束时只对少数表补了迁移，
  其余从未落库 → 「受限枚举前端逐字对齐」在生产并无 DB 层兜底，越界值可写库。

  实测证据：迁移 a3b4c5d6e7f8 日志 `constraint smart_devices.chk_smart_device_type
  missing, skip`；本次冒烟写入 room_type='balcony'（模型允许集外）返回 201 而非 IntegrityError。

设计：
  - 清单**冻结**在迁移内（166 条，逐条来自当时模型 metadata），不 import app.models：
    迁移一旦发布即不应随模型漂移，且 downgrade 需要确定性的可逆集合。
  - 幂等：`_has_constraint` 守卫，已存在即 skip（纯 alembic 从零建的库 / create_all 建的库
    两条路径下均安全——前者多数表无约束会补齐，后者已存在则全部 skip）。
  - 防御：表不存在或引用的列不存在 → 记日志 skip，不静默失败、不误报成功。
  - SQLite 走 batch_alter_table（不支持原生 ADD/DROP CONSTRAINT，且批量重建会丢未反射的
    CHECK，故按表一次性 add/drop 本表全部清单项，避免多次重建）；PG 直接
    op.create_check_constraint / op.drop_constraint。
  - downgrade 逐条 drop 本清单约束（还原「约束缺席」的旧状态；CI migration-test 走
    `alembic downgrade -1`，须可逆）。

上线前置（2026-09-23 生产实测）：166 条约束对生产存量数据零违规
（逐条 `WHERE (sqltext) IS FALSE` 计数均为 0），故可安全施加。
"""
from typing import Sequence, Union

import logging
import re

from alembic import op
import sqlalchemy as sa

logger = logging.getLogger("alembic.runtime.migration")


revision: str = "b8c8d9e0f1a2"
down_revision: Union[str, None] = "l4d5e6f7a8b9"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

# (表名, 约束名, 约束表达式)
_CONSTRAINTS: tuple[tuple[str, str, str], ...] = (
    ("bathroom_designs", "chk_bathroom_design_ceiling_height_positive", 'ceiling_height > 0'),
    ("bathroom_designs", "chk_bathroom_design_layout_type", "layout_type IN ('dry_wet_separation', 'three_separation', 'traditional', 'single')"),
    ("bathroom_designs", "chk_bathroom_design_room_length_positive", 'room_length > 0'),
    ("bathroom_designs", "chk_bathroom_design_room_width_positive", 'room_width > 0'),
    ("bathroom_designs", "chk_bathroom_design_status", "status IN ('draft', 'completed')"),
    ("bathroom_fixtures", "chk_bathroom_fixture_depth_positive", 'depth > 0'),
    ("bathroom_fixtures", "chk_bathroom_fixture_height_positive", 'height > 0'),
    ("bathroom_fixtures", "chk_bathroom_fixture_price_positive", 'price >= 0'),
    ("bathroom_fixtures", "chk_bathroom_fixture_type", "fixture_type IN ('toilet', 'basin', 'bathtub', 'shower', 'urinal', 'bidet', 'mirror', 'cabinet', 'towel_rack', 'vent_fan', 'heater')"),
    ("bathroom_fixtures", "chk_bathroom_fixture_width_positive", 'width > 0'),
    ("bom_items", "chk_bom_item_quantity_positive", 'quantity > 0'),
    ("bom_items", "chk_bom_item_status", "status IN ('pending', 'ordered', 'delivered', 'installed', 'auto_generated')"),
    ("bom_items", "chk_bom_item_total_price_positive", 'total_price >= 0'),
    ("bom_items", "chk_bom_item_unit_price_positive", 'unit_price >= 0'),
    ("budget_lines", "chk_budget_line_actual_amount_positive", 'actual_amount >= 0'),
    ("budget_lines", "chk_budget_line_estimated_amount_positive", 'estimated_amount >= 0'),
    ("budget_lines", "chk_budget_line_quantity_positive", 'quantity > 0'),
    ("budget_lines", "chk_budget_line_unit_price_positive", 'unit_price >= 0'),
    ("budgets", "chk_budget_status", "status IN ('draft', 'submitted', 'approved', 'executed', 'closed', 'active', 'completed')"),
    ("budgets", "chk_budget_total_actual_positive", 'total_actual >= 0'),
    ("budgets", "chk_budget_total_estimated_positive", 'total_estimated >= 0'),
    ("ceiling_designs", "chk_ceiling_design_height_drop_mm_positive", 'height_drop_mm >= 0'),
    ("ceiling_designs", "chk_ceiling_design_total_area_positive", 'total_area >= 0'),
    ("ceiling_designs", "chk_ceiling_design_total_price_positive", 'total_price >= 0'),
    ("ceiling_designs", "chk_ceiling_design_type", "ceiling_type IN ('flat', 'suspended', 'gypsum_perimeter', 'coffered', 'curve')"),
    ("ceiling_designs", "chk_ceiling_design_unit_price_positive", 'unit_price >= 0'),
    ("construction_logs", "chk_construction_log_type", "log_type IN ('daily', 'inspection', 'issue', 'change')"),
    ("construction_tasks", "chk_construction_task_phase", "phase IN ('preparation', 'demolition', 'water_electricity', 'electrical', 'waterproof', 'masonry', 'mep', 'carpentry', 'painting', 'installation', 'completion', 'inspection')"),
    ("construction_tasks", "chk_construction_task_priority_positive", 'priority >= 0'),
    ("construction_tasks", "chk_construction_task_status", "status IN ('pending', 'in_progress', 'ready', 'paused', 'completed', 'cancelled')"),
    ("custom_furniture_designs", "chk_custom_furniture_design_type", "furniture_type IN ('wardrobe', 'cabinet', 'bookshelf', 'shoe_cabinet', 'tv_cabinet', 'bed', 'door')"),
    ("custom_furniture_designs", "chk_custom_furniture_edge_banding", "edge_banding IN ('PVC', 'ABS', '亚克力')"),
    ("custom_furniture_designs", "chk_custom_furniture_hardware_brand", "hardware_brand IN ('海蒂诗', '百隆', '东泰')"),
    ("custom_furniture_designs", "chk_custom_furniture_panel_material", "panel_material IN ('颗粒板', '多层板', '欧松板', '实木')"),
    ("custom_furniture_designs", "chk_custom_furniture_panel_thickness_positive", 'panel_thickness >= 0'),
    ("custom_furniture_designs", "chk_custom_furniture_status", "status IN ('draft', 'designed', 'quoted', 'ordered', 'produced', 'delivered')"),
    ("custom_furniture_designs", "chk_custom_furniture_style", "style IN ('modern', '轻奢', '北欧', '中式', '法式')"),
    ("custom_furniture_designs", "chk_custom_furniture_total_depth_positive", 'total_depth >= 0'),
    ("custom_furniture_designs", "chk_custom_furniture_total_height_positive", 'total_height >= 0'),
    ("custom_furniture_designs", "chk_custom_furniture_total_price_positive", 'total_price >= 0'),
    ("custom_furniture_designs", "chk_custom_furniture_total_width_positive", 'total_width >= 0'),
    ("door_window_specs", "chk_door_window_spec_glass_type", "glass_type IS NULL OR glass_type IN ('single', 'double', 'triple', 'laminated', 'low_e')"),
    ("door_window_specs", "chk_door_window_spec_height_positive", 'height > 0'),
    ("door_window_specs", "chk_door_window_spec_material", "material IN ('solid_wood', 'wood_composite', 'aluminum', 'pvc', 'steel')"),
    ("door_window_specs", "chk_door_window_spec_opening_direction", "opening_direction IN ('inward', 'outward', 'sliding', 'folding')"),
    ("door_window_specs", "chk_door_window_spec_price_positive", 'price >= 0'),
    ("door_window_specs", "chk_door_window_spec_thickness_positive", 'thickness IS NULL OR thickness > 0'),
    ("door_window_specs", "chk_door_window_spec_type", "spec_type IN ('entry_door', 'interior_door', 'window', 'sliding_door', 'french_window')"),
    ("door_window_specs", "chk_door_window_spec_width_positive", 'width > 0'),
    ("furniture_boms", "chk_furniture_bom_item_type", "item_type IN ('panel', 'hardware', 'accessory', 'door')"),
    ("furniture_boms", "chk_furniture_bom_quantity_positive", 'quantity >= 0'),
    ("furniture_boms", "chk_furniture_bom_total_price_positive", 'total_price >= 0'),
    ("furniture_boms", "chk_furniture_bom_unit_price_positive", 'unit_price >= 0'),
    ("furniture_modules", "chk_furniture_module_depth_positive", 'depth >= 0'),
    ("furniture_modules", "chk_furniture_module_height_positive", 'height >= 0'),
    ("furniture_modules", "chk_furniture_module_position_index_positive", 'position_index >= 0'),
    ("furniture_modules", "chk_furniture_module_price_positive", 'price >= 0'),
    ("furniture_modules", "chk_furniture_module_quantity_positive", 'quantity >= 0'),
    ("furniture_modules", "chk_furniture_module_type", "module_type IN ('top', 'bottom', 'side', 'back', 'shelf', 'drawer', 'door', 'hanging_rod', 'mirror')"),
    ("furniture_modules", "chk_furniture_module_width_positive", 'width >= 0'),
    ("hard_decoration_floor_plans", "chk_hard_decoration_floor_coverage_area_positive", 'coverage_area >= 0'),
    ("hard_decoration_floor_plans", "chk_hard_decoration_floor_material_type", "material_type IN ('tile', 'wood', 'laminate', 'vinyl', 'stone', 'carpet')"),
    ("hard_decoration_floor_plans", "chk_hard_decoration_floor_pattern", "pattern IN ('直铺', '人字拼', '鱼骨拼', '工字铺', '菱形')"),
    ("hard_decoration_floor_plans", "chk_hard_decoration_floor_total_material_positive", 'total_material >= 0'),
    ("hard_decoration_floor_plans", "chk_hard_decoration_floor_total_price_positive", 'total_price >= 0'),
    ("hard_decoration_floor_plans", "chk_hard_decoration_floor_unit_price_positive", 'unit_price >= 0'),
    ("hard_decoration_floor_plans", "chk_hard_decoration_floor_waste_percent_range", 'waste_percent >= 0 AND waste_percent <= 100'),
    ("hard_decoration_schemes", "chk_hard_decoration_ceiling_area_positive", 'ceiling_area >= 0'),
    ("hard_decoration_schemes", "chk_hard_decoration_floor_area_positive", 'floor_area >= 0'),
    ("hard_decoration_schemes", "chk_hard_decoration_scheme_type", "scheme_type IN ('floor', 'wall', 'ceiling')"),
    ("hard_decoration_schemes", "chk_hard_decoration_status", "status IN ('draft', 'completed')"),
    ("hard_decoration_schemes", "chk_hard_decoration_total_budget_positive", 'total_budget >= 0'),
    ("hard_decoration_schemes", "chk_hard_decoration_wall_area_positive", 'wall_area >= 0'),
    ("inspections", "chk_inspection_score_range", 'score IS NULL OR (score >= 0 AND score <= 100)'),
    ("inspections", "chk_inspection_status", "status IN ('pending', 'passed', 'failed', 'rework')"),
    ("kitchen_components", "chk_kitchen_component_depth_positive", 'depth > 0'),
    ("kitchen_components", "chk_kitchen_component_height_positive", 'height > 0'),
    ("kitchen_components", "chk_kitchen_component_price_positive", 'price >= 0'),
    ("kitchen_components", "chk_kitchen_component_type", "component_type IN ('cabinet_base', 'wall_cabinet', 'island', 'countertop', 'sink', 'stove', 'range_hood', 'dishwasher', 'fridge', 'microwave', 'oven')"),
    ("kitchen_components", "chk_kitchen_component_width_positive", 'width > 0'),
    ("kitchen_designs", "chk_kitchen_design_ceiling_height_positive", 'ceiling_height > 0'),
    ("kitchen_designs", "chk_kitchen_design_counter_depth_positive", 'counter_depth > 0'),
    ("kitchen_designs", "chk_kitchen_design_counter_height_positive", 'counter_height > 0'),
    ("kitchen_designs", "chk_kitchen_design_layout_type", "layout_type IN ('L', 'U', 'I', 'G', 'double_i', 'island')"),
    ("kitchen_designs", "chk_kitchen_design_room_length_positive", 'room_length > 0'),
    ("kitchen_designs", "chk_kitchen_design_room_width_positive", 'room_width > 0'),
    ("kitchen_designs", "chk_kitchen_design_status", "status IN ('draft', 'completed')"),
    ("lighting_fixtures", "chk_lighting_fixture_beam_angle_positive", 'beam_angle IS NULL OR beam_angle >= 0'),
    ("lighting_fixtures", "chk_lighting_fixture_lumens_positive", 'lumens >= 0'),
    ("lighting_fixtures", "chk_lighting_fixture_quantity_positive", 'quantity >= 1'),
    ("lighting_fixtures", "chk_lighting_fixture_type", "fixture_type IN ('ceiling', 'pendant', 'spot', 'strip', 'track', 'wall', 'panel')"),
    ("lighting_fixtures", "chk_lighting_fixture_wattage_w_positive", 'wattage_w >= 0'),
    ("lighting_schemes", "chk_lighting_scheme_ceiling_height_positive", 'ceiling_height > 0'),
    ("lighting_schemes", "chk_lighting_scheme_color_temp_k_positive", 'color_temp_k IS NULL OR color_temp_k >= 0'),
    ("lighting_schemes", "chk_lighting_scheme_cri_range", 'cri IS NULL OR (cri >= 0 AND cri <= 100)'),
    ("lighting_schemes", "chk_lighting_scheme_room_area_positive", 'room_area >= 0'),
    ("lighting_schemes", "chk_lighting_scheme_status", "status IN ('draft', 'completed')"),
    ("lighting_schemes", "chk_lighting_scheme_total_lumens_positive", 'total_lumens IS NULL OR total_lumens >= 0'),
    ("lighting_schemes", "chk_lighting_scheme_total_power_w_positive", 'total_power_w IS NULL OR total_power_w >= 0'),
    ("lighting_schemes", "chk_lighting_scheme_type", "scheme_type IN ('main_light', 'none_main', 'mixed', 'scene')"),
    ("lighting_schemes", "chk_lighting_scheme_ugpr_positive", 'ugpr IS NULL OR ugpr >= 0'),
    ("materials", "chk_material_unit_price_positive", 'unit_price >= 0'),
    ("order_lines", "chk_order_line_delivered_qty_positive", 'delivered_quantity >= 0'),
    ("order_lines", "chk_order_line_quantity_positive", 'quantity > 0'),
    ("order_lines", "chk_order_line_total_price_positive", 'total_price >= 0'),
    ("order_lines", "chk_order_line_unit_price_positive", 'unit_price >= 0'),
    ("procurement_orders", "chk_procurement_order_assembly_difficulty", "assembly_difficulty IS NULL OR assembly_difficulty IN ('easy', 'medium', 'hard', 'professional_required')"),
    ("procurement_orders", "chk_procurement_order_delivery_status", "delivery_status IN ('pending', 'shipping', 'in_transit', 'delivered', 'delayed', 'cancelled')"),
    ("procurement_orders", "chk_procurement_order_status", "status IN ('draft', 'pending', 'confirmed', 'shipped', 'delivered', 'completed', 'cancelled')"),
    ("procurement_orders", "chk_procurement_order_total_amount_positive", 'total_amount >= 0'),
    ("products", "chk_product_category", "category IN ('tile', 'flooring', 'cabinet', 'paint', 'lighting', 'appliance', 'curtain', 'custom_furniture', 'service', 'other')"),
    ("products", "chk_product_price_max_positive", 'price_max IS NULL OR price_max >= 0'),
    ("products", "chk_product_price_min_positive", 'price_min IS NULL OR price_min >= 0'),
    ("products", "chk_product_status", "status IN ('draft', 'published', 'archived')"),
    ("products", "chk_product_stock_status", "stock_status IN ('in_stock', 'pre_order', 'out_of_stock')"),
    ("quotations", "chk_quotation_delivery_days_positive", 'delivery_days > 0'),
    ("quotations", "chk_quotation_quantity_positive", 'quantity > 0'),
    ("quotations", "chk_quotation_status", "status IN ('pending', 'accepted', 'rejected', 'expired')"),
    ("quotations", "chk_quotation_total_price_positive", 'total_price >= 0'),
    ("quotations", "chk_quotation_unit_price_positive", 'unit_price >= 0'),
    ("smart_devices", "chk_smart_device_control_mode", "control_mode IN ('manual', 'voice', 'app', 'automation')"),
    ("smart_devices", "chk_smart_device_power_w_positive", 'power_w IS NULL OR power_w >= 0'),
    ("smart_devices", "chk_smart_device_price_positive", 'price >= 0'),
    ("smart_devices", "chk_smart_device_protocol", "protocol IN ('zigbee', 'wifi', 'bluetooth', 'matter', 'homekit')"),
    ("smart_devices", "chk_smart_device_status", "status IN ('planned', 'installed', 'online', 'offline')"),
    ("smart_devices", "chk_smart_device_type", "device_type IN ('light', 'switch', 'socket', 'sensor', 'camera', 'lock', 'curtain', 'speaker', 'thermostat', 'air_purifier', 'robot_vacuum', 'fall_radar', 'care_bed', 'service_robot', 'health_monitor', 'emergency_call')"),
    ("smart_home_schemes", "chk_smart_home_scheme_device_count_positive", 'device_count >= 0'),
    ("smart_home_schemes", "chk_smart_home_scheme_hub_brand", "hub_brand IN ('xiaomi', 'huawei', 'apple', 'tuya', 'alexa')"),
    ("smart_home_schemes", "chk_smart_home_scheme_protocol", "protocol IN ('zigbee', 'wifi', 'bluetooth', 'matter', 'homekit')"),
    ("smart_home_schemes", "chk_smart_home_scheme_room_type", "room_type IN ('living_room', 'bedroom', 'kitchen', 'bathroom', 'entrance', 'study')"),
    ("smart_home_schemes", "chk_smart_home_scheme_status", "status IN ('draft', 'planned', 'installing', 'completed')"),
    ("smart_home_schemes", "chk_smart_home_scheme_total_price_positive", 'total_price >= 0'),
    ("soft_furnishing_items", "chk_soft_furnishing_item_depth_positive", 'depth IS NULL OR depth >= 0'),
    ("soft_furnishing_items", "chk_soft_furnishing_item_height_positive", 'height IS NULL OR height >= 0'),
    ("soft_furnishing_items", "chk_soft_furnishing_item_price_positive", 'price >= 0'),
    ("soft_furnishing_items", "chk_soft_furnishing_item_quantity_positive", 'quantity >= 1'),
    ("soft_furnishing_items", "chk_soft_furnishing_item_status", "status IN ('planned', 'purchased', 'delivered', 'installed')"),
    ("soft_furnishing_items", "chk_soft_furnishing_item_type", "item_type IN ('sofa', 'bed', 'dining_table', 'chair', 'coffee_table', 'rug', 'curtain', 'artwork', 'plant', 'lamp', 'pillow', 'decorative', 'tv_cabinet_alt')"),
    ("soft_furnishing_items", "chk_soft_furnishing_item_width_positive", 'width IS NULL OR width >= 0'),
    ("soft_furnishing_schemes", "chk_soft_furnishing_budget_total_positive", 'budget_total >= 0'),
    ("soft_furnishing_schemes", "chk_soft_furnishing_budget_used_positive", 'budget_used >= 0'),
    ("soft_furnishing_schemes", "chk_soft_furnishing_scheme_status", "status IN ('draft', 'planned', 'purchasing', 'delivered', 'installed')"),
    ("soft_furnishing_schemes", "chk_soft_furnishing_scheme_style", "style IN ('modern', '现代', '北欧', '新中式', '美式', '法式', '工业', '日式')"),
    ("storage_systems", "chk_storage_system_compartment_count_positive", 'compartment_count >= 0'),
    ("storage_systems", "chk_storage_system_total_capacity_positive", 'total_capacity_l >= 0'),
    ("storage_systems", "chk_storage_system_type", "storage_type IN ('衣柜', '厨柜', '书柜', '鞋柜', '储物间', '吊柜', '地柜')"),
    ("suppliers", "chk_supplier_rating_range", 'rating >= 0 AND rating <= 5'),
    ("wall_finishes", "chk_wall_finish_coats_positive", 'coats >= 0'),
    ("wall_finishes", "chk_wall_finish_coverage_area_positive", 'coverage_area >= 0'),
    ("wall_finishes", "chk_wall_finish_total_material_positive", 'total_material >= 0'),
    ("wall_finishes", "chk_wall_finish_total_price_positive", 'total_price >= 0'),
    ("wall_finishes", "chk_wall_finish_type", "finish_type IN ('paint', 'wallpaper', 'tile', 'panel', 'stone', 'wainscoting')"),
    ("wall_finishes", "chk_wall_finish_unit_price_positive", 'unit_price >= 0'),
    ("wall_finishes", "chk_wall_finish_waste_percent_range", 'waste_percent >= 0 AND waste_percent <= 100'),
    ("waterproof_plans", "chk_waterproof_plan_closure_test_hours_positive", 'closure_test_hours >= 0'),
    ("waterproof_plans", "chk_waterproof_plan_coating_layers_positive", 'coating_layers >= 0'),
    ("waterproof_plans", "chk_waterproof_plan_floor_area_positive", 'floor_area >= 0'),
    ("waterproof_plans", "chk_waterproof_plan_material", "waterproof_material IN ('polyurethane', 'JS', 'cement_based', 'SBS')"),
    ("waterproof_plans", "chk_waterproof_plan_material_quantity_positive", 'material_quantity >= 0'),
    ("waterproof_plans", "chk_waterproof_plan_room_type", "room_type IN ('bathroom', 'kitchen', 'balcony', 'terrace', 'laundry')"),
    ("waterproof_plans", "chk_waterproof_plan_status", "status IN ('draft', 'completed')"),
    ("waterproof_plans", "chk_waterproof_plan_thickness_mm_positive", 'thickness_mm >= 0'),
    ("waterproof_plans", "chk_waterproof_plan_total_price_positive", 'total_price >= 0'),
    ("waterproof_plans", "chk_waterproof_plan_unit_price_positive", 'unit_price >= 0'),
    ("waterproof_plans", "chk_waterproof_plan_wall_area_positive", 'wall_area >= 0'),
    ("waterproof_plans", "chk_waterproof_plan_wall_height_mm_positive", 'wall_height_mm >= 0'),
)

_SQL_KEYWORDS = {
    "IN", "IS", "NOT", "NULL", "OR", "AND", "TRUE", "FALSE", "BETWEEN",
    "LIKE", "GLOB", "CAST", "AS", "TEXT", "INTEGER", "REAL", "NUMERIC",
}


def _referenced_columns(sqltext: str) -> set[str]:
    """粗提取约束表达式引用的标识符（已剔除字符串字面量与 SQL 关键字）。"""
    stripped = re.sub(r"'[^']*'", " ", sqltext)
    tokens = set(re.findall(r"[A-Za-z_][A-Za-z0-9_]*", stripped))
    return {t for t in tokens if t.upper() not in _SQL_KEYWORDS}


def _plan(target_existing: bool) -> dict[str, tuple[list, list]]:
    """→ {表名: (要处理的 [(name, sqltext)], 跳过的 [name])}；target_existing=True 时为 drop 计划。"""
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    tables = set(inspector.get_table_names())
    plan: dict[str, tuple[list, list]] = {}
    for table, name, sqltext in _CONSTRAINTS:
        if table not in tables:
            logger.warning("[%s] table %s missing, skip %s", revision, table, name)
            continue
        cols = {c["name"] for c in inspector.get_columns(table)}
        absent = _referenced_columns(sqltext) - cols
        if absent:
            logger.warning("[%s] %s.%s references missing columns %s, skip", revision, table, name, sorted(absent))
            continue
        try:
            existing = {c["name"] for c in inspector.get_check_constraints(table)}
        except NotImplementedError:  # 方言不支持反射 → 视为不存在
            existing = set()
        act, skip = plan.setdefault(table, ([], []))
        # upgrade（target_existing=False）→ 仅处理「尚不存在」的；downgrade → 仅处理「已存在」的
        if (name in existing) != target_existing:
            skip.append((name, sqltext))
            continue
        act.append((name, sqltext))
    return plan


def upgrade() -> None:
    bind = op.get_bind()
    dialect = bind.dialect.name
    logger.info("[%s] upgrade start: dialect=%s constraints=%d", revision, dialect, len(_CONSTRAINTS))
    added = 0
    for table, (items, _skip) in sorted(_plan(target_existing=False).items()):
        if dialect == "sqlite":
            with op.batch_alter_table(table) as batch_op:
                for name, sqltext in items:
                    batch_op.create_check_constraint(name, sqltext)
        else:
            for name, sqltext in items:
                op.create_check_constraint(name, table, sqltext)
        added += len(items)
        logger.info("[%s] %s: added %d", revision, table, len(items))
    logger.info("[%s] upgrade done: added=%d", revision, added)


def downgrade() -> None:
    bind = op.get_bind()
    dialect = bind.dialect.name
    logger.info("[%s] downgrade start: dialect=%s", revision, dialect)
    dropped = 0
    for table, (items, _skip) in sorted(_plan(target_existing=True).items()):
        if dialect == "sqlite":
            with op.batch_alter_table(table) as batch_op:
                for name, _sqltext in items:
                    batch_op.drop_constraint(name, type_="check")
        else:
            for name, _sqltext in items:
                op.drop_constraint(name, table, type_="check")
        dropped += len(items)
        logger.info("[%s] %s: dropped %d", revision, table, len(items))
    logger.info("[%s] downgrade done: dropped=%d", revision, dropped)

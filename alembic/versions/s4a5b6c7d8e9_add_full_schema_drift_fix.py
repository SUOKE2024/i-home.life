"""full schema drift fix (8 missing tables + 13 tables' columns)

Revision ID: s4a5b6c7d8e9
Revises: r0a1b2c3d4e5
Create Date: 2026-08-02

v1.4.x P0 schema drift 修复（第三轮）：check_schema_drift.py 对「全新迁移库」核查发现
alembic 迁移链严重落后于 ORM model —— 8 张表完全缺失 + 13 张表共 39 列缺失。
此前 v1.2.7（n5e6f7a8b9c0）修复过第一轮 drift，但 model 持续演进（v1.2.x~v1.4.x
新增 energy/health/matter/predictive/scene_behavior 等模块），迁移链未同步。

影响（全新迁移库 vs model）：
  缺失表（8）: matter_devices, predicted_scenes, risk_predictions, air_quality_records,
               energy_monitor_records, energy_saving_tips, health_monitors, scene_behavior_logs
  缺失列（13 张表）:
    ai_image_jobs       render_backend
    ar_scan_sessions    floorplan_id
    chat_messages       thread_root_id / is_deleted / deleted_at
    file_attachments    message_id
    material_categories deleted_at
    materials           deleted_at
    payments            stage_code / stage_order / due_at / invoice_no / invoice_url / invoiced_at
    procurement_orders  delivery_status / tracking_number / carrier / estimated_delivery_date /
                        actual_delivery_date / delivery_address / assembly_required /
                        assembly_difficulty / delivery_notes
    products            deleted_at
    projects            project_type / source / scan_session_id
    settlement_lines    is_anomaly / anomaly_type / anomaly_severity / anomaly_detail
    settlements         anomaly_count / critical_anomaly_count / suggested_deduction /
                        review_required / review_reason / reviewed_by
    users               sub_role / is_verified

特性：
  - 幂等：has_table / has_column 检查已存在则跳过（生产可安全重复执行）
  - NOT NULL 新列一律带 server_default（存量行获得默认值，避免 ALTER 失败）
  - SQLite batch mode 兼容
  - 回滚：DROP COLUMN / DROP TABLE（幂等）

注：与既有 drift-fix（n5e6f7a8b9c0）一致，不补 CHECK 约束（应用层 ORM 校验），
FK 约束仅随新表 create_table 创建（补列场景不额外建 FK，避免 SQLite batch 重建风险）。
"""
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = "s4a5b6c7d8e9"
down_revision = "r0a1b2c3d4e5"
branch_labels = None
depends_on = None


def _has_table(table_name: str) -> bool:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    return inspector.has_table(table_name)


def _has_column(table_name: str, column_name: str) -> bool:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    try:
        cols = [c["name"] for c in inspector.get_columns(table_name)]
    except Exception:
        return True  # 表不存在视为已处理，避免报错
    return column_name in cols


def _has_index(table_name: str, index_name: str) -> bool:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    try:
        idxs = [i["name"] for i in inspector.get_indexes(table_name)]
    except Exception:
        return True
    return index_name in idxs


def _add_column(table_name: str, col: sa.Column) -> None:
    bind = op.get_bind()
    if bind.dialect.name == "sqlite":
        with op.batch_alter_table(table_name) as batch_op:
            batch_op.add_column(col)
    else:
        op.add_column(table_name, col)


def _create_index(table_name: str, index_name: str, columns: list[str]) -> None:
    if _has_index(table_name, index_name):
        return
    bind = op.get_bind()
    if bind.dialect.name == "sqlite":
        with op.batch_alter_table(table_name) as batch_op:
            batch_op.create_index(index_name, columns)
    else:
        op.create_index(index_name, table_name, columns)


# (表, 列名, Column 构造, 关联 index 定义 [(index_name, [cols])])
_COLUMNS: list[tuple[str, str, sa.Column, list[tuple[str, list[str]]]]] = [
    # ai_image_jobs 1 列
    ("ai_image_jobs", "render_backend",
     sa.Column("render_backend", sa.String(20), nullable=False, server_default=sa.text("'mock'")), []),
    # ar_scan_sessions 1 列（model index=True）
    ("ar_scan_sessions", "floorplan_id",
     sa.Column("floorplan_id", sa.String(36), nullable=True),
     [("ix_ar_scan_sessions_floorplan_id", ["floorplan_id"])]),
    # chat_messages 3 列
    ("chat_messages", "thread_root_id",
     sa.Column("thread_root_id", sa.String(36), nullable=True), []),
    ("chat_messages", "is_deleted",
     sa.Column("is_deleted", sa.Boolean(), nullable=False, server_default=sa.false()), []),
    ("chat_messages", "deleted_at",
     sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True), []),
    # file_attachments 1 列（model index=True）
    ("file_attachments", "message_id",
     sa.Column("message_id", sa.String(36), nullable=True),
     [("ix_file_attachments_message_id", ["message_id"])]),
    # material_categories / materials / products 软删除列
    ("material_categories", "deleted_at",
     sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True), []),
    ("materials", "deleted_at",
     sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True), []),
    ("products", "deleted_at",
     sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True), []),
    # payments 6 列（发票/阶段）
    ("payments", "stage_code",
     sa.Column("stage_code", sa.String(30), nullable=True), []),
    ("payments", "stage_order",
     sa.Column("stage_order", sa.Integer(), nullable=False, server_default=sa.text("0")), []),
    ("payments", "due_at",
     sa.Column("due_at", sa.DateTime(timezone=True), nullable=True), []),
    ("payments", "invoice_no",
     sa.Column("invoice_no", sa.String(50), nullable=True), []),
    ("payments", "invoice_url",
     sa.Column("invoice_url", sa.String(500), nullable=True), []),
    ("payments", "invoiced_at",
     sa.Column("invoiced_at", sa.DateTime(timezone=True), nullable=True), []),
    # procurement_orders 9 列（交付/安装）
    ("procurement_orders", "delivery_status",
     sa.Column("delivery_status", sa.String(30), nullable=False, server_default=sa.text("'pending'")), []),
    ("procurement_orders", "tracking_number",
     sa.Column("tracking_number", sa.String(100), nullable=True), []),
    ("procurement_orders", "carrier",
     sa.Column("carrier", sa.String(50), nullable=True), []),
    ("procurement_orders", "estimated_delivery_date",
     sa.Column("estimated_delivery_date", sa.DateTime(timezone=True), nullable=True), []),
    ("procurement_orders", "actual_delivery_date",
     sa.Column("actual_delivery_date", sa.DateTime(timezone=True), nullable=True), []),
    ("procurement_orders", "delivery_address",
     sa.Column("delivery_address", sa.Text(), nullable=True), []),
    ("procurement_orders", "assembly_required",
     sa.Column("assembly_required", sa.Boolean(), nullable=False, server_default=sa.false()), []),
    ("procurement_orders", "assembly_difficulty",
     sa.Column("assembly_difficulty", sa.String(30), nullable=True), []),
    ("procurement_orders", "delivery_notes",
     sa.Column("delivery_notes", sa.Text(), nullable=True), []),
    # projects 3 列（项目类型/来源/AR 扫描会话）
    ("projects", "project_type",
     sa.Column("project_type", sa.String(30), nullable=False, server_default=sa.text("'full_renovation'")), []),
    ("projects", "source",
     sa.Column("source", sa.String(20), nullable=False, server_default=sa.text("'manual'")), []),
    ("projects", "scan_session_id",
     sa.Column("scan_session_id", sa.String(36), nullable=True), []),
    # settlement_lines 4 列（异常标记）
    ("settlement_lines", "is_anomaly",
     sa.Column("is_anomaly", sa.Boolean(), nullable=False, server_default=sa.false()), []),
    ("settlement_lines", "anomaly_type",
     sa.Column("anomaly_type", sa.String(50), nullable=True), []),
    ("settlement_lines", "anomaly_severity",
     sa.Column("anomaly_severity", sa.String(20), nullable=True), []),
    ("settlement_lines", "anomaly_detail",
     sa.Column("anomaly_detail", sa.String(500), nullable=True), []),
    # settlements 6 列（审核/异常汇总）
    ("settlements", "anomaly_count",
     sa.Column("anomaly_count", sa.Integer(), nullable=False, server_default=sa.text("0")), []),
    ("settlements", "critical_anomaly_count",
     sa.Column("critical_anomaly_count", sa.Integer(), nullable=False, server_default=sa.text("0")), []),
    ("settlements", "suggested_deduction",
     sa.Column("suggested_deduction", sa.Float(), nullable=False, server_default=sa.text("0")), []),
    ("settlements", "review_required",
     sa.Column("review_required", sa.Boolean(), nullable=False, server_default=sa.false()), []),
    ("settlements", "review_reason",
     sa.Column("review_reason", sa.String(500), nullable=True), []),
    ("settlements", "reviewed_by",
     sa.Column("reviewed_by", sa.String(36), nullable=True), []),
    # users 2 列（实名认证/工种子角色）
    ("users", "sub_role",
     sa.Column("sub_role", sa.String(30), nullable=True), []),
    ("users", "is_verified",
     sa.Column("is_verified", sa.Boolean(), nullable=False, server_default=sa.false()), []),
]

# 缺失的 8 张表（定义与 model metadata 完全一致）
_TABLES: list[tuple[str, list[sa.Column], list[sa.Index]]] = [
    ("matter_devices", [
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("project_id", sa.String(36), sa.ForeignKey("projects.id"), nullable=False),
        sa.Column("matter_unique_id", sa.String(64), nullable=False, unique=True),
        sa.Column("device_type_id", sa.Integer(), nullable=False),
        sa.Column("vendor_id", sa.Integer(), nullable=False),
        sa.Column("product_id", sa.Integer(), nullable=False),
        sa.Column("software_version", sa.String(20), nullable=False),
        sa.Column("hardware_version", sa.String(20), nullable=False),
        sa.Column("commissioning_state", sa.String(30), nullable=False),
        sa.Column("fabric_index", sa.Integer(), nullable=True),
        sa.Column("node_id", sa.Integer(), nullable=True),
        sa.Column("clusters", sa.JSON(), nullable=True),
        sa.Column("endpoints", sa.JSON(), nullable=True),
        sa.Column("thread_credentials", sa.JSON(), nullable=True),
        sa.Column("wifi_credentials", sa.JSON(), nullable=True),
        sa.Column("last_seen_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("(CURRENT_TIMESTAMP)"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("(CURRENT_TIMESTAMP)"),
            nullable=False,
        ),
    ], [
        sa.Index("ix_matter_devices_project_id", "project_id"),
    ]),
    ("predicted_scenes", [
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("project_id", sa.String(36), sa.ForeignKey("projects.id"), nullable=False),
        sa.Column("user_id", sa.String(36), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("scene_name", sa.String(200), nullable=False),
        sa.Column("room_type", sa.String(30), nullable=True),
        sa.Column("trigger_time_hint", sa.String(100), nullable=True),
        sa.Column("trigger_condition", sa.JSON(), nullable=True),
        sa.Column("actions", sa.JSON(), nullable=True),
        sa.Column("confidence", sa.Float(), nullable=False),
        sa.Column("based_on_count", sa.Integer(), nullable=False),
        sa.Column("status", sa.String(20), nullable=False),
        sa.Column("explanation", sa.Text(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("(CURRENT_TIMESTAMP)"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("(CURRENT_TIMESTAMP)"),
            nullable=False,
        ),
    ], [
        sa.Index("ix_predicted_scenes_project_id", "project_id"),
        sa.Index("ix_predicted_scenes_status", "status"),
        sa.Index("ix_predicted_scenes_user_id", "user_id"),
    ]),
    ("risk_predictions", [
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("project_id", sa.String(36), sa.ForeignKey("projects.id"), nullable=False),
        sa.Column("risk_type", sa.String(30), nullable=False),
        sa.Column("risk_score", sa.Float(), nullable=False),
        sa.Column("probability", sa.Float(), nullable=False),
        sa.Column("impact_level", sa.String(20), nullable=False),
        sa.Column("trigger_factors", sa.JSON(), nullable=True),
        sa.Column("affected_tasks", sa.JSON(), nullable=True),
        sa.Column("mitigation_actions", sa.JSON(), nullable=True),
        sa.Column("status", sa.String(20), nullable=False),
        sa.Column(
            "predicted_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("(CURRENT_TIMESTAMP)"),
            nullable=False,
        ),
        sa.Column("resolved_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("(CURRENT_TIMESTAMP)"),
            nullable=False,
        ),
    ], [
        sa.Index("ix_risk_predictions_project_id", "project_id"),
    ]),
    ("air_quality_records", [
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("project_id", sa.String(36), sa.ForeignKey("projects.id"), nullable=False),
        sa.Column("scheme_id", sa.String(36), sa.ForeignKey("smart_home_schemes.id"), nullable=False),
        sa.Column("room_name", sa.String(100), nullable=False),
        sa.Column("pm25", sa.Float(), nullable=False),
        sa.Column("pm10", sa.Float(), nullable=False),
        sa.Column("co2", sa.Float(), nullable=False),
        sa.Column("tvoc", sa.Float(), nullable=False),
        sa.Column("formaldehyde", sa.Float(), nullable=False),
        sa.Column("temperature", sa.Float(), nullable=False),
        sa.Column("humidity", sa.Float(), nullable=False),
        sa.Column("aqi_index", sa.Integer(), nullable=False),
        sa.Column("aqi_level", sa.String(30), nullable=False),
        sa.Column("recorded_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("(CURRENT_TIMESTAMP)"),
            nullable=False,
        ),
    ], [
        sa.Index("ix_air_quality_records_project_id", "project_id"),
        sa.Index("ix_air_quality_records_scheme_id", "scheme_id"),
    ]),
    ("energy_monitor_records", [
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("project_id", sa.String(36), sa.ForeignKey("projects.id"), nullable=False),
        sa.Column("scheme_id", sa.String(36), sa.ForeignKey("smart_home_schemes.id"), nullable=False),
        sa.Column("period", sa.String(10), nullable=False),
        sa.Column("total_consumption_kwh", sa.Float(), nullable=False),
        sa.Column("device_breakdown", sa.JSON(), nullable=True),
        sa.Column("peak_power_w", sa.Float(), nullable=False),
        sa.Column("avg_power_w", sa.Float(), nullable=False),
        sa.Column("standby_consumption_kwh", sa.Float(), nullable=False),
        sa.Column("estimated_cost", sa.Float(), nullable=False),
        sa.Column("carbon_footprint_kg", sa.Float(), nullable=False),
        sa.Column("recorded_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("(CURRENT_TIMESTAMP)"),
            nullable=False,
        ),
    ], [
        sa.Index("ix_energy_monitor_records_project_id", "project_id"),
        sa.Index("ix_energy_monitor_records_scheme_id", "scheme_id"),
    ]),
    ("energy_saving_tips", [
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("scheme_id", sa.String(36), sa.ForeignKey("smart_home_schemes.id"), nullable=False),
        sa.Column("tip_type", sa.String(30), nullable=False),
        sa.Column("device_type", sa.String(50), nullable=True),
        sa.Column("device_name", sa.String(200), nullable=True),
        sa.Column("current_consumption", sa.Float(), nullable=True),
        sa.Column("potential_saving_pct", sa.Float(), nullable=True),
        sa.Column("suggestion", sa.Text(), nullable=False),
        sa.Column("priority", sa.String(10), nullable=False),
        sa.Column("status", sa.String(10), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("(CURRENT_TIMESTAMP)"),
            nullable=False,
        ),
    ], [
        sa.Index("ix_energy_saving_tips_scheme_id", "scheme_id"),
    ]),
    ("health_monitors", [
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("project_id", sa.String(36), sa.ForeignKey("projects.id"), nullable=False),
        sa.Column("scheme_id", sa.String(36), sa.ForeignKey("smart_home_schemes.id"), nullable=False),
        sa.Column("monitor_type", sa.String(50), nullable=False),
        sa.Column("value", sa.JSON(), nullable=False),
        sa.Column("alert_level", sa.String(20), nullable=False),
        sa.Column("alert_message", sa.String(500), nullable=True),
        sa.Column("device_id", sa.String(36), sa.ForeignKey("smart_devices.id"), nullable=True),
        sa.Column("recorded_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("(CURRENT_TIMESTAMP)"),
            nullable=False,
        ),
    ], [
        sa.Index("ix_health_monitors_device_id", "device_id"),
        sa.Index("ix_health_monitors_project_id", "project_id"),
        sa.Index("ix_health_monitors_scheme_id", "scheme_id"),
    ]),
    ("scene_behavior_logs", [
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("project_id", sa.String(36), sa.ForeignKey("projects.id"), nullable=False),
        sa.Column("user_id", sa.String(36), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("action_type", sa.String(30), nullable=False),
        sa.Column("scene_id", sa.String(36), sa.ForeignKey("scene_automations.id"), nullable=True),
        sa.Column("room_type", sa.String(30), nullable=True),
        sa.Column("time_of_day", sa.Integer(), nullable=True),
        sa.Column("day_of_week", sa.Integer(), nullable=True),
        sa.Column("duration_seconds", sa.Integer(), nullable=True),
        sa.Column("device_states_before", sa.JSON(), nullable=True),
        sa.Column("device_states_after", sa.JSON(), nullable=True),
        sa.Column("ambient_data", sa.JSON(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("(CURRENT_TIMESTAMP)"),
            nullable=False,
        ),
    ], [
        sa.Index("ix_scene_behavior_logs_action_type", "action_type"),
        sa.Index("ix_scene_behavior_logs_project_id", "project_id"),
        sa.Index("ix_scene_behavior_logs_scene_id", "scene_id"),
        sa.Index("ix_scene_behavior_logs_user_id", "user_id"),
    ]),
]


def upgrade() -> None:
    # 1) 补齐 8 张缺失表（幂等：表已存在则跳过）
    for table_name, columns, indexes in _TABLES:
        if _has_table(table_name):
            continue
        op.create_table(table_name, *columns, *indexes)

    # 2) 补齐 13 张表的缺失列（幂等：列已存在则跳过）
    for table_name, col_name, col, indexes in _COLUMNS:
        if _has_column(table_name, col_name):
            continue
        _add_column(table_name, col)
        for idx_name, idx_cols in indexes:
            _create_index(table_name, idx_name, idx_cols)


def downgrade() -> None:
    # 1) 删除补齐的列（幂等，逆序）
    bind = op.get_bind()
    is_sqlite = bind.dialect.name == "sqlite"
    for table_name, col_name, _, indexes in reversed(_COLUMNS):
        for idx_name, _ in indexes:
            if not _has_index(table_name, idx_name):
                continue
            if is_sqlite:
                with op.batch_alter_table(table_name) as batch_op:
                    batch_op.drop_index(idx_name)
            else:
                op.drop_index(idx_name, table_name=table_name)
        if not _has_column(table_name, col_name):
            continue
        if is_sqlite:
            with op.batch_alter_table(table_name) as batch_op:
                batch_op.drop_column(col_name)
        else:
            op.drop_column(table_name, col_name)

    # 2) 删除补齐的表（幂等，逆序，先删 index）
    for table_name, _, indexes in reversed(_TABLES):
        if not _has_table(table_name):
            continue
        for idx in indexes:
            if not _has_index(table_name, idx.name):
                continue
            if is_sqlite:
                with op.batch_alter_table(table_name) as batch_op:
                    batch_op.drop_index(idx.name)
            else:
                op.drop_index(idx.name, table_name=table_name)
        op.drop_table(table_name)

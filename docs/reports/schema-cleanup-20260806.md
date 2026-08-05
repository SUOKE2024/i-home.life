# 残留表与索引差异清理建议（2026-08-06）

> 依据 [scripts/compare_db_schema.py](file:///Users/netsong/Developer/i-home.life/scripts/compare_db_schema.py) 实测（真实库 `data/ihome.db` vs 空库迁移库）与 model metadata 三方交叉验证（model 声明 / 空库迁移链 / 真实库 create_all）。
> 结论基于证据：8 张残留表全仓零代码引用 + 0 行数据；索引分类经 `Base.metadata.tables[*].indexes` 权威比对。

## 一、8 张无 model 残留表 → 可安全忽略（建议 DROP）

| 表 | 代码引用 | 数据量 | 建议 |
|----|----------|--------|------|
| `assets_3d` | 无 | 0 行 | **可删**（确认无外部依赖后 DROP） |
| `digital_human_profiles` | 无 | 0 行 | **可删** |
| `knowledge_entries` | 无 | 0 行 | **可删** |
| `provider_api_keys` | 无 | 0 行 | **可删** |
| `provider_listings` | 无 | 0 行 | **可删** |
| `provider_settlements` | 无 | 0 行 | **可删** |
| `service_providers` | 无 | 0 行 | **可删**（此前有 service 层的 B2B 供应商预研，model 已移除） |
| `support_tickets` | 无 | 0 行 | **可删** |

判定依据：`grep` 全仓（app/tests/scripts/web/flutter）零命中；SQLite `COUNT(*)` 全为 0。
性质：历史 `create_all` 残留（旧版本 model 存在、后被移除，或手动建的临时表），无业务价值。
**处理**：不影响任何运行逻辑（无引用无数据），可安全忽略；彻底清理建议运维在**确认无外部系统写入**后 `DROP TABLE`（8 张），或留待大版本 schema 整理一并处理。**不建议**为它们补 model/迁移。

## 二、8 张表列差异（真实库有、model 无）→ 可安全忽略

`bom_items.fallback_note/quantity_source/version`、`chat_messages.auto_reply_meta`、`chat_rooms.agent_members`、`escrow_payments.amount`、`milestone_trackers.due_date`、`orchestrator_tasks.agent_type`、`quality_issues.title`、`rectification_orders.issue_id`

判定：均为**真实库 create_all 历史残留列**（旧 model 定义过、后被移除；`check_schema_drift` 只报"model 有 DB 无"方向，故本地从未告警）。空库（迁移链）无这些列，运行无影响。
**处理**：可忽略（保留无害）；如需彻底对齐，运维 `ALTER TABLE ... DROP COLUMN`（需评估是否有存量数据依赖——生产 PG 建议先查数据再删）。

## 三、28 张表索引差异 → 需修复（分三类）

> 权威比对方法：`Base.metadata.tables[t].indexes`（model 声明）∪ 空库（迁移链）∪ 真实库，三方交集取差。

### A 类：空库缺、model 声明（23 张表 30 个索引）→ **应补迁移**

model 的 `index=True` 单列索引未进迁移链（建表迁移漏建，仅 create_all 补过）→ CI 空库缺索引，生产（真实库）有。

`ar_measurement_points.session_id`、`ar_scan_sessions.project_id/survey_id`、`ar_wall_features.session_id`、`bay_compliance.project_id`、`bom_items.version`、`budget_lines.budget_id`、`budgets.project_id`、`change_orders.project_id`、`construction_tasks.project_id`、`escrow_payments.order_id/project_id`、`hard_decoration_floor_plans.scheme_id`、`identity_verifications.reviewer_id`、`inspections.task_id`、`milestone_trackers.project_id`、`orchestrator_tasks.assigned_user_id/project_id`、`order_lines.material_id/order_id`、`payments.project_id/settlement_id`、`points_rankings.user_id`、`procurement_orders.construction_task_id`、`progress_alerts.project_id`、`quality_issues.project_id`、`quotations.material_id/project_id/supplier_id`、`settlements.project_id`

**影响**：空库（CI/新环境）查询走全表扫描，性能与生产不一致。
**修复**：新增"索引对齐迁移"，对上述索引 `op.create_index`（`_has_index` 幂等，空库补建、真实库已存在 skip）。

### B 类：真实库缺、迁移链有（5 张表 5 个复合索引）→ **应补迁移（对真实库补建）**

model `__table_args__` 复合索引，真实库因表为旧 `create_all` 所建而缺失。

`agent_messages(session_id, created_at)`、`agent_skills.created_by`、`audit_logs(user_id, created_at)`、`construction_tasks(project_id, status)`、`device_tokens(user_id, platform)`

**影响**：生产真实库缺这 5 个复合索引（多为高频查询索引，如审计日志/消息列表），性能风险。
**修复**：同一"索引对齐迁移"内 `op.create_index` 幂等补建（空库已存在 skip，真实库补上）→ 双库最终一致。

### C 类：同名索引 unique 标志相反（2 个）→ **迁移链 bug，应修复**

| 索引 | 真实库（create_all） | 空库（迁移链） | model 声明 | 正确值 |
|------|---------------------|---------------|-----------|--------|
| `a2a_tasks.ix_a2a_tasks_task_id` | unique=TRUE ✅ | unique=FALSE ❌ | `unique=True, index=True` | unique |
| `agent_approvals.ix_agent_approvals_approval_id` | unique=TRUE ✅ | unique=FALSE ❌ | `unique=True, index=True` | unique |

判定：model 声明 `unique=True, index=True` → SQLAlchemy 建 **unique 索引**。迁移链（[l3c4d5e6f7a8](file:///Users/netsong/Developer/i-home.life/alembic/versions/l3c4d5e6f7a8_add_a2a_tasks_table.py) / [u6b7c8d9e0f1](file:///Users/netsong/Developer/i-home.life/alembic/versions/u6b7c8d9e0f1_add_agent_approval.py)）建索引时漏传 unique → 空库唯一性约束缺失，**可插入重复 task_id/approval_id**（数据完整性风险，比性能更严重）。
**修复**：索引对齐迁移内先 drop 非 unique 索引再以 unique 重建（幂等），或补 `UniqueConstraint`。

## 四、建议执行计划（按优先级）

| 优先级 | 动作 | 影响 |
|--------|------|------|
| P0 | C 类：修复 2 个索引为 unique（数据完整性） | 防重复数据 |
| P1 | A+B 类：新增"索引对齐迁移"补 35 个索引（幂等） | 空库/真实库索引一致，性能对齐 |
| P2 | 8 张残留表 DROP（确认无外部依赖后） | 消除 compare 脚本"仅 A 有"噪音 |
| P3 | 8 表残留列清理（可选，评估数据后 DROP COLUMN） | 彻底对齐 |

> 执行后重跑 `compare_db_schema.py` 应收敛到 0 差异（除残留表/列外）。P0/P1 落地后同步更新 CI [schema-compare](file:///Users/netsong/Developer/i-home.life/.github/workflows/schema-compare.yml) 监控。

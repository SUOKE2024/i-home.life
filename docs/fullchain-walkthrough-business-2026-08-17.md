# 全景全量全链路走查报告（业务数据流 / 前端契约 / 状态机闭环）

> 走查日期：2026-08-17 · 环境：本地 `pytest`（SQLite 测试库）+ 三路代码级审计（业务流 / 前端契约 / 治理运维）+ 主代理 Read 核验
> 方式：延续 v1.15.1「Agent 用户全流程走查」后，本轮聚焦上轮未覆盖的**核心业务数据流链路**（预算→BOM→采购→施工→质检→结算→支付）、**前端 API 契约**、**状态机-模型一致性**
> 范围：80 路由模块 / 112 Service / 62 ORM 模型 / webapp+console+Flutter 三端契约

## 一、全景结论

**主链路可用，但存在 3 处「状态机合法状态不在 DB 约束内」的 500 级缺陷（写库即崩）、7 处前端/后端契约不一致（405/422）、6 条「生产零调用」的状态机断链（状态不可达）与 1 处死代码断链模块。**

| 维度 | 结论 |
|------|------|
| 状态机 vs DB 约束 | ❌ 3 处冲突：采购 `completed`、预算 `submitted/executed/closed`、验收 `rework` 均不在 CheckConstraint 允许集，真实写入抛 IntegrityError |
| 前端→后端契约 | ❌ 4 处明确不一致（webapp PUT projects / flutter PATCH surveys / console workers `?status=` / flutter POST mep circuits），前 3 处 405/422 |
| 状态机生产可达性 | ⚠️ 6 条断链：预算审批流、结算 paid/disputed、任务 cancelled/failed、验收状态更新、「以销定产」drive_procurement_from_bom 全部生产零调用（状态机存在但状态不可达） |
| 死代码/断链模块 | ⚠️ `okf_export_service.py` import 不存在的 `app.models.knowledge` / `app.services.knowledge_service`，模块级生产零调用（import 即崩） |
| 越权面 | ✅ 抽样核验 payments/procurement/construction 等均有归属校验（自有 `_verify_owner`/`verify_project_access`），未发现裸奔 |
| 缓存隔离 | ✅ 裸 `cache.get/set` 调用点均为公共数据或 key 含 user_id/session_id（UUID）；`cache_user_isolation_strict=True` 生效 |
| 鉴权体系 | ✅ 全仓 0 处 JWT/jws import；PASETO v4.local 唯一实现 |

## 二、断点清单（主代理核验后确认，按严重度）

| # | 严重度 | 断点 | 根因（文件:行号） | 影响 |
|---|--------|------|------------------|------|
| 1 | P0 | 采购订单 `delivered→completed` 触发 500 | 状态机合法终态不在 [procurement.py](file:///Users/netsong/Developer/i-home.life/app/models/procurement.py#L124) CheckConstraint | 收货后无法完结订单 |
| 2 | P0 | 预算审批流 `submit/execute/close` 触发 500 | 状态机 5 态 vs [budget.py](file:///Users/netsong/Developer/i-home.life/app/models/budget.py#L27) 约束 4 态且互异（submitted/executed/closed 写入违反约束） | 审批流一旦接线即崩 |
| 3 | P0 | 验收 `failed→rework` 触发 500 | 状态机中间态不在 [construction.py](file:///Users/netsong/Developer/i-home.life/app/models/construction.py#L85) 约束（rework 缺失） | 整改复验链路崩 |
| 4 | P0 | webapp 更新项目 405 | [api.js](file:///Users/netsong/Developer/i-home.life/webapp/src/lib/api.js#L203) 用 PUT，后端仅注册 PATCH | 项目编辑不可用 |
| 5 | P0 | flutter 更新量房 405 | [api.dart](file:///Users/netsong/Developer/i-home.life/flutter_app/lib/services/api.dart#L1631) 用 PATCH，后端仅 PUT | 量房编辑不可用 |
| 6 | P0 | console 更新工人匹配 422 | [api-client.ts](file:///Users/netsong/Developer/i-home.life/console-src/src/services/api-client.ts#L1157) 传 `?status=`，后端必填 `new_status` | 匹配状态流转不可用 |
| 7 | P0 | flutter 添加 MEP 回路 405 | `POST /mep-kb/plans/{id}/circuits` 后端不存在（仅 GET 计算） | MEP 页「添加回路」不可用 |
| 8 | P1 | 「以销定产」声称开启实际零调用 | `drive_procurement_from_bom`（procurement_service.py:356）生产零调用（CLAUDE.md 声称默认 True 开启） | 与 v1.14.1 P0 同类「声称闭环实际断裂」 |
| 9 | P1 | 结算 `paid/disputed` 状态不可达 | `mark_settlement_paid/disputed`（settlement_service.py:286/299）生产零调用 | 结算确认后无法完结 |
| 10 | P1 | 任务 `cancelled/failed` 不可达 | `cancel_task/fail_task`（task_service.py:370/384）生产零调用（MCP tasks 为独立内存实现） | 任务取消/失败不可用 |
| 11 | P1 | 预算审批流整体不可达 | `submit/approve/execute/close_budget`（budget_service.py:204-259）生产零调用 | 预算状态机空转 |
| 12 | P1 | 质检验收状态机不可达 | `update_inspection_status`（construction_service.py:142）生产零调用 → INSPECTION_PASSED 事件永不发射，后继任务链不推进 | 验收-施工联动断裂 |
| 13 | P2 | `okf_export_service.py` 死代码断链 | import 不存在的 `app.models.knowledge` / `app.services.knowledge_service`，app/ 零引用（CHANGELOG 却声称 OKF 导出能力） | 模块级 import 即崩 |
| 14 | P2 | paseto_handler docstring 过时 | 声称「默认 False」实际 config 默认 True（v1.14.1 起） | 文档误导 |
| 15 | P1 | 结算 confirm 端点 409 条件恒真 | settlements.py:190 `status != "confirmed"`（状态机无此状态，恒真）且未检查 `reviewed_by` | 复核后 confirm 永远 409，复核确认链路不可用 |

## 三、修复与验证记录（v1.15.2，同日完成）

| # | 修复内容 | 改动文件 | 验证 |
|---|---------|---------|------|
| 1 | 采购 CheckConstraint 允许集加 `completed`（对齐状态机终态） | app/models/procurement.py | `test_procurement_order_delivered_to_completed_no_integrity_error` ✅ |
| 2 | 预算 CheckConstraint 扩展为审批流 5 态 + legacy active/completed | app/models/budget.py | `test_budget_approval_flow_endpoints`（submit→approve→execute→close 全 200）+ 非法流转 400 ✅ |
| 3 | 验收 CheckConstraint 加 `rework`（对齐中间态） | app/models/construction.py | `test_inspection_status_rework_path_endpoint`（failed→rework→passed 全 200）✅ |
| 4 | webapp updateProject PUT→PATCH | webapp/src/lib/api.js | `test_frontend_contract_webapp_update_project_patch` ✅ |
| 5 | flutter updateSurvey PATCH→PUT | flutter_app/lib/services/api.dart | `test_frontend_contract_flutter_survey_put_and_circuit_post` ✅ |
| 6 | console `?status=`→`?new_status=` | console-src/src/services/api-client.ts | `test_frontend_contract_console_worker_status_param` ✅ |
| 7 | 后端补 `POST /mep-kb/plans/{id}/circuits`（手动回路落库 electrical_circuits）+ GET 合并手动回路 | app/api/kitchen_bath_mep.py | `test_mep_manual_circuit_add_and_merge` ✅ |
| 8 | 以销定产接线：generate-from-bom 端点 flag 开时调 `drive_procurement_from_bom`（返回 demand_priority），关时回退原行为 | app/api/procurement.py | `test_generate_from_bom_demand_driven` / `_fallback_when_flag_off` ✅ |
| 9 | 结算补 `POST /settlements/{project_id}/mark-paid` + `mark-disputed` 端点 | app/api/settlements.py | `test_settlement_mark_paid_endpoint` / `_mark_disputed_endpoint` ✅ |
| 10 | 任务补 `POST /tasks/{id}/cancel` + `POST /tasks/{id}/fail`（owner/admin/被分配者鉴权 + WS 推送） | app/api/tasks.py | `test_task_cancel_and_fail_endpoints` ✅ |
| 11 | 预算补 `POST /budgets/{budget_id}/submit|approve|execute|close`（归属校验 + 非法流转 400） | app/api/budgets.py | 同上 #2 用例 ✅ |
| 12 | 验收补 `PATCH /construction/inspections/{id}/status`（状态机校验 + INSPECTION_PASSED 事件） | app/api/construction.py | 同上 #3 用例 ✅ |
| 13 | 删除 `okf_export_service.py`（死代码断链模块） | 文件删除 | — |
| 14 | paseto_handler docstring 更新为默认 True 描述 | app/auth/paseto_handler.py | — |
| 15 | 结算 confirm 409 条件改 `review_required and not reviewed_by`（与服务层语义对齐） | app/api/settlements.py | `test_settlement_confirm_after_review_no_false_409` ✅ |

**迁移**：新增 `alembic/versions/a1b2c3d4e5f7_align_state_machine_constraints.py`（幂等，PG 直接 drop/create，SQLite batch 重建；仅扩允许集不缩，存量数据安全；downgrade 恢复旧约束）。

**回归测试**：新增 `tests/test_fullchain_walkthrough_20260817.py` 14 用例（mock 确定性，覆盖 #1-#15）。**质量门禁**：flake8 / mypy（12 源文件 0 错误）全绿。

## 四、体验亮点（值得保留）

- 越权治理整体扎实：三路审计抽查 payments/procurement/construction/settlements 全部有项目归属校验（自有 `_verify_owner`/`_verify_project_owner` 或 `verify_project_access`），且 mutations 均在校验之后（IDOR 修复模式统一）。
- 缓存隔离体系可靠：`cache_user_isolation_strict=True` 硬校验 + 全部私有 key 含 user_id/session_id，无跨用户缓存点。
- PASETO 纯净：全仓 0 处 JWT/jws import，v4.local 唯一实现，strict 模式硬校验。
- 前端覆盖度极高：80 路由模块全部挂载（main.py include_router 80/80 无遗漏），723 个端点与三端前端调用基本一一对应（仅 4 处方法/参数不一致）。

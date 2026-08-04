# 项目全链路（创建→完工验收）断裂修复设计

> 日期：2026-08-04
> 范围：方案 A — 链路修复（5 处断裂 + 端到端串联 + 强制验收报告闸门）
> 决策：用户已确认方案 A + 强制验收报告闸门

## 一、诊断结论（5 处确定性断裂）

| # | 断裂 | 证据 |
|---|------|------|
| 1 | 事件总线编排规则全死（零发射点） | `rg "bus.emit\|EventType."` 除 orchestration_rules/event_bus 外无命中；5 条规则订阅了从不发射的事件 |
| 2 | 项目状态机被 PATCH 绕过 | `update_project_status`（project_service.py:123）无任何 API 调用；PATCH 走 `update_project` 的 `setattr(status)` 直绕校验 |
| 3 | 项目级竣工验收端点缺失 | 无 `POST /projects/{id}/accept`；通往 completed 仅靠绕过校验的 PATCH |
| 4 | phase 未持久化，timeline 基于幻影状态 | projects.py:211 `status_stage_map` 引用 design/in_progress/construction，模型只有 draft/active/completed/cancelled |
| 5 | INSPECTION_PASSED 规则含 `pass` 占位 | orchestration_rules.py:68 后继任务推进未实现 |

## 二、修复设计

### 2.1 事件总线发射点接线（断裂 1）

新增 `app/services/lifecycle_events.py`，封装 `emit_*` 辅助函数（受 feature flag 门控），在 5 处业务点调用：

| 事件 | 发射点（文件:行） | 触发的编排规则 |
|------|----------------|--------------|
| `PROJECT_CREATED` | project_service.py `create_project` commit 后（~L104） | auto_create_budget_on_project |
| `BOM_GENERATED` | material_service.py `snapshot_bom_version`（L234，BOM 版本快照=定稿）commit 后（L266） | auto_generate_procurement |
| `MATERIAL_DELIVERED` | procurement_service 订单→delivered 转换处（~L490 现有 task-ready 逻辑旁） | update_construction_on_delivery |
| `INSPECTION_PASSED` | quality_service inspection→passed 转换处（~L321） | advance_construction_after_inspection |
| `CHANGE_ORDER_APPROVED` | change_order_service.py:121 `order.status="approved"` 处 | update_budget_on_change_order |

**flag 门控**：`lifecycle_orchestration_enabled`（默认 False 生产 / True 开发）。关闭时发射函数 no-op，编排规则仍订阅但不触发，零回归。

**去重**：procurement_service.py:490 已直接把 task 置 ready（与 `update_construction_on_delivery` 规则重复）。统一为：保留事件发射，将直接调用改为依赖事件触发（删除 489-493 的直接 task 更新，交由编排规则处理）。受 flag 控制，关闭时保留原直接逻辑作为回退。

### 2.2 Project phase 字段 + 状态机（断裂 2、4）

**模型变更**（app/models/project.py）：

```python
phase: Mapped[str] = mapped_column(String(30), nullable=False, default="initiation")
# initiation / design / budget / procurement / construction / quality / settlement / completed / cancelled
```

**phase 状态机**（app/services/project_service.py）：

```python
PHASE_ORDER = ["initiation","design","budget","procurement","construction","quality","settlement","completed"]

def _assert_phase_transition(project, target):
    if target == "cancelled":
        return  # 任何阶段均可取消
    if target not in PHASE_ORDER:
        raise ProjectPhaseError(...)
    cur = PHASE_ORDER.index(project.phase) if project.phase in PHASE_ORDER else -1
    if PHASE_ORDER.index(target) <= cur:
        raise ProjectPhaseError(...)  # 仅允许前进
```

**status 联动**：phase→completed 时同步 status→completed；phase 离开 initiation 时同步 status→active。

**PATCH 修复**（project_service.py `update_project`）：若 `update_data` 含 `status`，改调 `update_project_status`（不再 `setattr` 直绕）。

**alembic 迁移**：`add_project_phase_column`，backfill 已有项目 phase=`construction` if status==active else `initiation` if draft else `completed`。

### 2.3 竣工验收端点（断裂 3）

新增 `POST /projects/{project_id}/accept`（app/api/projects.py）：

```python
@router.post("/{project_id}/accept", summary="竣工验收")
async def accept_project(project_id, data: AcceptanceRequest, current_user, db):
    # 1. 项目归属校验
    # 2. 状态机校验：phase 必须为 quality 或 settlement
    # 3. 强制验收报告闸门：
    #    - 调 quality_service.generate_acceptance_report(db, project_id) 生成/取最新报告
    #    - 查 QualityIssue where project_id and status in (open, in_progress)
    #    - 若存在未闭环质量问题 → 409 Conflict，返回未闭环项清单
    #    - 若报告 pass_rate < 100% → 409
    # 4. 通过：update_project_status → completed；phase → completed
    # 5. WS broadcast "project.accepted"
    # 6. 返回验收报告 + 项目状态
```

**闸门严格度**（用户选定：强制）：调用 `quality_service.generate_acceptance_report(db, project_id, phase=None)`（全阶段），闸门判定：
- 报告中 `failed > 0`（即存在 status=open/in_progress 的 QualityIssue 匹配到 checklist 项）→ 409，返回 fail 项清单
- 或直接查 `QualityIssue where project_id and status in (open, in_progress)` 存在 → 409
- 无人工强制绕过路径

`acceptance_checklist_enabled=False` 时报告走 `_summarize_issues_only` 回退，闸门退化为"无 open/in_progress 质量问题"判定。

### 2.4 timeline 修正（断裂 4）

`GET /projects/{id}/timeline`：删除 `status_stage_map` 幻影映射，改为 `active_stage = PHASE_ORDER.index(project.phase) + 1`（phase 直接驱动）。

### 2.5 INSPECTION_PASSED 占位补全（断裂 5）

orchestration_rules.py:68 `pass` 替换为：

```python
for successor in successors.get("successors", []):
    # 查后继任务的所有前置是否均 completed
    if successor.predecessor_id:
        preds = await service.get_task_chain(successor.id)  # 含 predecessors
        if all(p.status == "completed" for p in preds.get("predecessors", [])):
            await service.update_task_status(successor.id, "ready")
```

利用现有 `predecessor_id`/`successors` 关系（construction.py:25,45）。

## 三、Feature Flag 与回滚

- `lifecycle_orchestration_enabled`（config.py + .env.example，默认 False 生产）
- 关闭时：事件发射 no-op；procurement 保留原直接 task-ready 逻辑；PATCH 状态机校验仍启用（独立于 flag，属 bugfix 不回滚）；accept 端点仍可用（独立于 flag）
- 回滚：alembic downgrade 删 phase 列 + flag=False

## 四、测试计划（tests/test_lifecycle_chain.py）

1. `test_create_project_emits_event_and_auto_creates_budget` — 创建项目后预算自动生成
2. `test_bom_generated_emits_procurement_suggestions` — BOM 生成后采购建议自动创建
3. `test_material_delivered_advances_task_to_ready` — 材料到货后任务就绪
4. `test_inspection_passed_advances_successor_chain` — 验收通过后后继任务推进（覆盖原 pass 占位）
5. `test_change_order_approved_updates_budget` — 变更审批后预算更新
6. `test_phase_state_machine_rejects_backward` — phase 不允许后退
7. `test_patch_project_status_uses_state_machine` — PATCH 不再绕过校验
8. `test_accept_project_blocked_by_open_quality_issues` — 强制闸门：有未闭环质量问题 → 409
9. `test_accept_project_success` — 闸门通过 → completed
10. `test_timeline_reads_phase_directly` — timeline 不再依赖幻影 status

现有 `pytest` 基线 1821 passed 不得回退。

## 五、改动文件清单

| 文件 | 改动 |
|------|------|
| app/models/project.py | +phase 字段 |
| app/services/project_service.py | +phase 状态机；修 update_project 走状态机 |
| app/services/lifecycle_events.py | 新建 emit_* 辅助 |
| app/services/orchestration_rules.py | 补全 pass 占位 |
| app/services/procurement_service.py | MATERIAL_DELIVERED 发射；flag 去重 |
| app/services/material_service.py | BOM_GENERATED 发射 |
| app/services/quality_service.py | INSPECTION_PASSED 发射 |
| app/services/change_order_service.py | CHANGE_ORDER_APPROVED 发射 |
| app/api/projects.py | +POST /accept；修 timeline |
| app/schemas/project.py | +phase/AcceptanceRequest |
| app/config.py + .env.example | +lifecycle_orchestration_enabled |
| alembic/versions/* | +add_project_phase_column |
| tests/test_lifecycle_chain.py | 新建 10 用例 |
| tests/test_projects.py / test_procurement.py | 适配 patch 不绕状态机 |

## 六、不做（YAGNI）

- 不重构 orchestrator（意图分类器）为生命周期编排器——超出当前范围
- 不审计 74 路由越权——属方案 B
- 不新增 PROJECT_COMPLETED 事件类型——accept 端点直接状态机+WS 即可
- 不改前端 Flutter/console——后端契约先稳定，前端后续对接

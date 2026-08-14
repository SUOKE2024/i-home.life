# 设计流程编排：风格/预算选供应商 → VR 效果图 → 可行性分析

**日期**：2026-08-14
**状态**：待评审（设计文档，不含实现代码）
**关联**：i-home.life 索克家居 AI 智能装修平台

---

## 1. 背景与目标

### 1.1 用户旅程

```
项目入库 → 量房 → 户型图绘制 → [选风格/预算 → 匹配供应商] → 渲染 VR 效果图
         → 调整/智能体建议（循环）→ 选定确认 → 后续流程可行性分析
```

用户希望：项目完成量房与户型图后，能基于**风格/预算**等条件，**随机或自选**供应商，随后**渲染 VR 全景（效果）图**；在调整选定完成后，自动安排**后续流程的可行性分析**。

### 1.2 目标

把项目内已散落的「量房 / 户型 / 供应商 / VR 渲染 / 比价 / 风险」能力串成一个**确定性编排闭环**，补齐三个真实缺口：

1. 供应商按「风格 + 预算档位」匹配（现有只按物料品类匹配）。
2. 每个房间一张 2D 效果图 + 全屋 VR 漫游组合（现有渲染粒度是单全景图）。
3. 四维度「后续流程可行性分析」聚合（现有只有零散的工期估算 / 风险预测）。

### 1.3 非目标（YAGNI，明确不做）

- 不做真实 GPU 渲染集群 / 2D→3D `.spz` 内容管线（沿用 ai_render 4 级降级链，M3 余项）。
- 不做真实供应商询价 API / 支付下单（沿用现有 mock 报价，诚实标注）。
- 不做前端页面（本次只出后端设计；前端交互在 §11 简述，作为后续范围）。
- 不引入微服务 / 任务队列（K8s/Redis/Celery 均不引入，沿用模块化单体 + 阿里云 FC 架构）。

---

## 2. 现状与缺口

### 2.1 可复用的现有积木

| 能力 | 现状 | 复用入口 |
|------|------|---------|
| 项目 | `projects` 模型 | — |
| 量房 | `app/api/surveys.py`，`POST /api/surveys/{id}/apply` 应用量房生成户型 | — |
| 户型图 | `FloorPlan` 模型，`data` 存 walls/doors/windows/rooms JSON | `app/models/floorplan.py` |
| 供应商 | `Supplier` 模型（按 `category` + `rating` 匹配） | `app/services/procurement_service.py` `compare_suppliers` |
| 效果图渲染 | ai_render 4 级降级链（L0 ControlNet → L1 mock-geometry → L2 placeholder → L3 503） | `app/services/ai_render_service.py` `render_2d(layout_json, style, user_id, db, require_real)` |
| 效果图漫游 | 2D 效果图发布为 `content_source=effect` 全景 | `app/services/vr_panorama_service.py` `publish_effect_render` |
| 全屋漫游组合 | `VRScene`（`panorama_ids` 有序列表 + `transition_type`） | `app/models/vr_panorama.py` |
| 工期估算 | 确定性施工计划估算（含缓冲） | `app/api/b2b_delivery.py` `_estimate_construction(area)` |
| 预算比价 | BOM 比价 / 供应商报价 | `app/services/procurement_service.py` `compare_suppliers` |
| 物料可供应性 | 供应商库存 / 交期 | `app/services/procurement_service.py` `get_material_availability` |
| 施工条件/风险 | 延期 / 风险预测 | `app/services/predictive_maintenance_service.py` `analyze_project_risks` |

### 2.2 缺口

1. **编排层缺失**：没有一条「量房户型就绪 → 选供应商 → 渲染 → 调整 → 可行性分析」的状态机。
2. **供应商风格/预算维度缺失**：`Supplier` 无 `styles` / `price_tier`，无法按风格+预算硬过滤。
3. **批量房间渲染 + 全屋漫游组合缺失**：现有渲染单张、漫游组合是手工拼 `VRScene`。
4. **可行性分析无聚合**：四维度结果散落，无统一输出。

---

## 3. 架构方案（已选定：方案 A）

**确定性编排 Service + 状态机**，LLM「智能体意见」作为独立建议端点（旁路，不阻塞主流程）。

核心原则：

- 供应商匹配、状态流转、渲染触发、可行性聚合全部**确定性**，可测（守住 pytest 2361 基线门禁）。
- LLM 只出现在「调整建议」旁路，LLM 不可用时返回空建议 + 诚实标注，不阻断主流程。
- 复用现有确定性 service 最大化，只新增编排层 + 字段 + 聚合。

---

## 4. 数据模型

### 4.1 `Supplier` 新增字段

在 `app/models/procurement.py` 的 `Supplier` 上新增：

```python
# 支持的装修风格列表（JSON 字符串，形如 ["modern","nordic","奶油风"]）
styles: Mapped[str] = mapped_column(Text, nullable=False, default="[]")
# 价格档位：economy / standard / premium
price_tier: Mapped[str] = mapped_column(String(20), nullable=False, default="standard")
```

配套 property（对齐 `VRPanorama.hotspot_list` 的 JSON 访问器模式）：

```python
@property
def styles_list(self) -> list[str]: ...
@styles_list.setter
def styles_list(self, value: list[str]): ...
```

需要 Alembic migration（`styles` 默认 `[]`、`price_tier` 默认 `standard`，向后兼容现有行）。

### 4.2 新增 `DesignFlow` 编排会话表

```python
class DesignFlow(Base):
    __tablename__ = "design_flows"

    id: str = uuid pk
    project_id: str = FK projects, index
    floorplan_id: str = FK floor_plans          # 前置就绪的户型
    style: str                                   # 用户选定风格（自由文本，兼容 SUPPORTED_STYLES）
    budget: float                                # 用户预算（元）
    price_tier: str = economy/standard/premium   # 由 budget + area 推导
    supplier_selection_mode: str = random/manual # 随机 / 自选
    supplier_id: str | None = FK suppliers       # 选定供应商
    scene_id: str | None = FK vr_scenes          # 全屋漫游场景
    stage: str                                   # 状态机当前阶段（§6）
    created_at / updated_at
```

### 4.3 新增 `DesignFlowFeasibility` 可行性分析结果表

```python
class DesignFlowFeasibility(Base):
    __tablename__ = "design_flow_feasibilities"

    id: str = uuid pk
    flow_id: str = FK design_flows, index
    duration_analysis: Text(JSON)    # 工期可行性
    budget_analysis: Text(JSON)      # 预算可行性
    material_analysis: Text(JSON)    # 物料可供应性
    risk_analysis: Text(JSON)        # 施工条件/风险
    summary: Text(JSON)              # 聚合结论 + 各维度 source 诚实标注
    status: str = pending/partial/completed/failed
    created_at
```

> 设计取舍：四维度用 JSON 列（`Text` 存 JSON 字符串 + property 访问器），避免为每个维度建表。单一分析结果一张表，`flow_id` 唯一索引便于「一个会话一份最新分析」。

### 4.4 预算档位映射（`budget → price_tier`）

用**每平米预算**分档（避免面积差异导致误判）：

| 每平米预算（元/㎡） | price_tier |
|---------------------|-----------|
| `< 1500` | `economy` |
| `1500 ~ 3000` | `standard` |
| `> 3000` | `premium` |

> 阈值首次硬编码为常量，标注「可配置/后续调优」。分档在 `design_flow_service` 内实现，不落独立表。

---

## 5. 服务层设计

新增 `app/services/design_flow_service.py`，纯确定性编排：

| 函数 | 职责 |
|------|------|
| `start_design_flow(db, project_id, floorplan_id, style, budget)` | 校验前置（`FloorPlan` 存在且 `is_active`），推导 `price_tier`，创建会话（`stage=init`） |
| `match_suppliers(db, style, price_tier)` | 硬过滤：`is_active=True AND styles 包含 style AND price_tier==price_tier`，按 `rating` 降序返回候选 |
| `select_supplier(db, flow, mode, supplier_id=None)` | `random`：从候选随机选一个；`manual`：校验 `supplier_id` 在候选中，写入 `flow.supplier_id` |
| `trigger_render(db, flow, user_id)` | 逐房间 `render_2d` → 逐房间落 `VRPanorama(content_source=effect)` → 组合 `VRScene`（§7） |
| `adjust(db, flow, changes, user_id)` | 应用 `changes`（style/budget/supplier_id/effect_tweak）→ 重渲染（§8） |
| `confirm(db, flow)` | `stage=confirmed` → 触发 `analyze_feasibility` |
| `analyze_feasibility(db, flow)` | 四维度聚合（§9） |
| `suggest_adjustment(db, flow, user_id)` | LLM 调整建议（旁路，§10） |

**前置校验规则**：`start_design_flow` 必须确认项目已有「量房 + 户型图」。校验方式——`floorplan_id` 指向的 `FloorPlan.is_active=True`；量房记录可选校验（存在 `surveys` 记录且已 apply），文档建议：**强校验 `floorplan` 就绪，弱校验（告警）量房记录**，避免历史数据无 survey 而阻塞。

**供应商随机选择**：`random` 模式用 `secrets.choice(candidates)`（非 `random`，避免可预测性争议；候选 ≥1 时执行）。

---

## 6. 状态机

`DesignFlow.stage` 取值与流转：

```
init ──匹配供应商──▶ supplier_matched ──渲染──▶ rendered
  │                                              │
  │◀──────────── 调整（重选供应商/重渲染）────────┘
  │                                              │
  │                             确认 confirm ──▶ confirmed ──▶ feasibility_done
  │                                              │
  └────────────── cancel（任意阶段）─────────────▶ cancelled
```

| stage | 含义 | 允许操作 |
|-------|------|---------|
| `init` | 已建会话 | match suppliers |
| `supplier_matched` | 供应商已匹配 | render / adjust / cancel |
| `rendered` | 效果图已渲染 | adjust / confirm / cancel |
| `confirmed` | 用户确认 | analyze feasibility / cancel |
| `feasibility_done` | 可行性分析完成 | 终态 |
| `cancelled` | 已取消 | 终态 |

状态流转由 service 层显式校验，非法流转返回 409（复用项目现有 HTTPException 风格）。

---

## 7. 渲染与全屋漫游

### 7.1 每房间一张 2D 效果图

1. 从 `FloorPlan.data` 解析 `rooms`（复用 `quantity_takeoff_service.parse_floorplan_geometry` 或直接 `json.loads`）。
2. 对每个房间构造 `layout_json`（房间几何 + 全户型上下文，供几何锁定）。
3. 调用 `ai_render_service.render_2d(layout_json=..., style=flow.style, user_id=..., db=db, require_real=...)`。
4. 拿到的 `image_url` 用 `publish_effect_render`（或直接创建）落 `VRPanorama(content_source="effect", room_name=房间名)`。

**降级链透传**：`render_2d` 返回的 `degradation_chain_level`（0/1/2/3）逐房间记录，前端据此诚实标注「AI 效果图 / mock / 占位」；`require_real=True` 且 L3 时抛 503（沿用现有契约，不伪造）。

### 7.2 全屋 VR 漫游

渲染完所有房间后，创建 `VRScene`：

- `panorama_ids` = 各房间 `VRPanorama.id`（按 `rooms` 顺序）。
- `transition_type = "fade"`（默认，可配 `warp/none`）。
- `default_panorama_id` = 第一个房间。
- 写入 `flow.scene_id`。

前端复用现有 VR 漫游组件（`webapp/src/pages/VirtualTour.jsx` / `VRPanoramaPage.tsx`），`content_source=effect` 走 2D 平面预览并标注「效果图预览 · 非实景」。

---

## 8. 调整闭环

`adjust(flow, changes, user_id)` 接收：

```json
{
  "style": "nordic",          // 可选：换风格
  "budget": 200000,           // 可选：调预算
  "supplier_id": "uuid",      // 可选：换供应商
  "effect_tweak": {...}       // 可选：效果图微调（配色等）
}
```

规则（对齐「任意环节调整均触发重渲染」）：

- `style` 或 `budget` 变化 → 重新推导 `price_tier` → **重新匹配 + 重选供应商**（沿用当前 `selection_mode`）→ **重渲染**。
- `supplier_id` 变化 → **重渲染**（风格不变）。
- `effect_tweak` 变化 → **重渲染**（风格/供应商不变）。

每次 `adjust` 后 `stage` 回到 `supplier_matched` 或 `rendered`（视是否换供应商），并**清空旧 `scene_id` / 旧房间全景引用**（软删或复用 `deleted_at`，避免孤儿数据）。

---

## 9. 可行性分析（四维度聚合）

`analyze_feasibility(db, flow)` 依次聚合，各维度**独立降级**（单维度失败标 `partial`，不影响其它维度）：

| 维度 | 复用 | 输出 |
|------|------|------|
| 工期 | `_estimate_construction(flow.floorplan.total_area)` | 阶段计划 + 总工期 + 缓冲 |
| 预算 | `compare_suppliers` / BOM 报价（筛选 `supplier_id`） | 报价汇总 vs `flow.budget`，超支/节省 |
| 物料可供应性 | `get_material_availability`（筛选 `supplier_id`） | 库存 / 交期满足度 |
| 施工条件/风险 | `analyze_project_risks(project_id)` | 风险列表 + 等级 |

**聚合结论** `summary` 含：

- 四维度结果引用 + 每维度 `source` 诚实标注（如 `"预算：基于模拟报价（source=mock）"`）。
- 一个布尔/分级「可推进」信号（如 `go / go_with_conditions / no_go`），供前端与下游流程判断。

> 诚实降级红线：供应商报价若为 mock（`source="mock"`），预算可行性必须在 `summary` 与 `budget_analysis` 中显式标注「模拟报价，非真实询价」，禁止伪装实时数据。

---

## 10. LLM 智能体意见（旁路）

`POST /api/design-flow/{id}/suggest` → `suggest_adjustment(db, flow, user_id)`：

- 基于当前 `flow` 快照（style/budget/supplier/房间数/面积）+ 用户偏好 hint，调用 `BaseAgent._chat()` 生成调整建议（如「预算可下探 10%，建议换 `economy` 档供应商」「奶油风更适配小户型」）。
- **只读建议**，不直接改状态；用户采纳后走 `POST /adjust` 端点。
- LLM 不可用 → 返回 `{"suggestions": [], "source": "unavailable"}`，**不阻断主流程**。

---

## 11. API 设计

新增 `app/api/design_flow.py`（前缀 `/api/design-flow`），全部走 `get_current_user` + `verify_project_access`：

| 方法 | 路径 | 说明 |
|------|------|------|
| POST | `/api/design-flow` | 创建会话（project_id, floorplan_id, style, budget） |
| GET | `/api/design-flow/{id}` | 会话详情 + 当前 stage |
| POST | `/api/design-flow/{id}/suppliers/match` | 匹配候选供应商 |
| POST | `/api/design-flow/{id}/suppliers/select` | 随机/自选供应商（mode, supplier_id?） |
| POST | `/api/design-flow/{id}/render` | 触发渲染 |
| POST | `/api/design-flow/{id}/adjust` | 调整（触发重渲染） |
| POST | `/api/design-flow/{id}/confirm` | 确认 → 触发可行性分析 |
| GET | `/api/design-flow/{id}/feasibility` | 查询可行性分析结果 |
| POST | `/api/design-flow/{id}/suggest` | LLM 调整建议（旁路） |

**同步/异步取舍**：渲染与可行性分析先走**同步**（mock/确定性 service 快速返回；真实渲染后端已设 60s 超时）。若后续真实渲染耗时增长，再引入 `asyncio.create_task` + `ws_manager.broadcast_to_project` 推送进度（复用现有 `app/ws.py`）。本次不提前异步化（YAGNI）。

---

## 12. 测试策略

新增 `tests/test_design_flow.py`，覆盖：

1. 前置校验：无 `floorplan` / `is_active=False` → 创建失败。
2. 供应商匹配：`styles` 不包含 / `price_tier` 不符 → 被过滤；候选按 `rating` 降序。
3. 随机选择：`selection_mode=random` 选中结果在候选中。
4. 状态机：非法流转（如 `init` 直接 confirm）→ 409；正常流转到 `feasibility_done`。
5. 渲染：每房间生成 `VRPanorama(content_source=effect)`，`VRScene.panorama_ids` 数量 = 房间数。
6. 调整重渲染：改 style → 重匹配 + 重渲染；改 supplier → 重渲染。
7. 可行性四维度：各维度聚合 + 单维度失败标 `partial`。
8. LLM 建议降级：无 API key → `suggestions=[]` + `source=unavailable`，主流程不受影响。

> 复用现有测试夹具模式（`tests/conftest.py` 的 `client`/`db_session`），遵循 `.claude/guides/testing.md`。

---

## 13. 迁移与版本

- Alembic migration：`Supplier` 加 `styles` + `price_tier`；新增 `design_flows` + `design_flow_feasibilities` 表。
- 新增 API 需同步 `main.py` `include_router`（无条件加载）。
- 版本号全链路 bump（见 `.claude/templates/version-bump.md`）。

---

## 14. 前端（后续范围，本次不实现）

- 用户侧（webapp）：选风格/预算 → 供应商卡片（随机/自选按钮）→ VR 漫游查看 → 调整 → 可行性分析面板。
- 控制台（console-src）：供应商管理页新增 `styles` / `price_tier` 编辑。
- Flutter：对齐 webapp 流程。

---

## 15. 默认决策摘要（review 重点，均可调整）

以下为本设计的默认决策，已在正文固化；review 时请重点确认：

1. **预算档位**（§4.4）：用「每平米预算」分档——`<1500` → economy，`1500~3000` → standard，`>3000` → premium；阈值首版硬编码常量。
2. **前置校验**（§5）：强校验 `floorplan.is_active=True`；量房记录仅弱校验（告警，不阻塞）。
3. **可行性信号**（§9）：三级 `go / go_with_conditions / no_go`。

# 「家的生命线」双重重构落地评估报告

- 日期：2026-08-11
- 范围：移动端（Flutter）+ Web 端（webapp/）对「空间智能 × 时间叙事」原创设计的落地实现检查
- 对照基准：`docs/design-2026-mockups.html`（2026 原创方案 mockup，5 屏）

## 一、结论摘要

| 层 | 落地状态 |
|---|---|
| **设计概念前端表达**（空间首页/生命线/Ambient 卡片流/bento cockpit） | **0% 未落地**——两端仍是「功能列表 + 图标网格」传统范式 |
| **后端能力层**（健康分/里程碑/A2UI 卡片/资金托管/溯源/主动通知） | **~80% 就绪**——设计要消费的数据与机制几乎全部存在 |
| **身份层**（LOGO/头像体系/主题三态） | **已落地**（本轮已交付，见下） |

**核心结论**：落地缺口不在数据与后端，而在**前端表达层重构**。「家的生命线」所需的全部后端燃料（施工健康分、里程碑、A2UI 8 类卡片、节点放款、一板一码溯源）都已在库，但移动端与 web 端没有任何页面把它们表达为「空间即导航 / 生命线叙事 / Ambient 管家」。这是一个明确的「前端表达层待开发」状态，而非「能力缺失」。

已随本轮落地的身份层基础：新 LOGO（使用项目原有 LOGO，两端同一视觉）、`AvatarController` 手绘头像体系（启动随机/宫格/相册）、亮/暗/跟随系统三态主题。

## 二、四维度逐项评估

### 1. 空间即导航（户型即首页）— ❌ 未落地

**Mockup 设计**：户型图取代图标网格成为首页；每个房间按阶段着色，点房间弹出该空间状态（效果图/进度/下一步动作）。

**现状**：
- 移动端首页 = `home_page.dart` 直接内嵌聊天页（`const Expanded(child: AIChatPage())`，[home_page.dart:54](file:///Users/netsong/Developer/i-home.life/flutter_app/lib/pages/home_page.dart#L49-L55)）；工作台 `dashboard_page.dart` 是「项目总数/施工中/面积」三张统计卡（[dashboard_page.dart:76-80](file:///Users/netsong/Developer/i-home.life/flutter_app/lib/pages/dashboard_page.dart#L76-L80)）。
- web 端首页 `Dashboard.jsx` 为统计卡 + 快捷入口网格（[Dashboard.jsx:62-75](file:///Users/netsong/Developer/i-home.life/webapp/src/pages/Dashboard.jsx#L62-L75)）；项目页 `Projects.jsx` 为 CRUD 列表。
- 「户型图」仅以**工具**形式存在：`smart_home_page.dart` 户型绘制器（[smart_home_page.dart:2099](file:///Users/netsong/Developer/i-home.life/flutter_app/lib/pages/smart_home_page.dart#L2099)）、AR 扫描上传、CAD 页——均非「户型即首页」的导航范式。

**后端就绪**：`floorplans` CRUD API（房间/楼层数据结构）、`project.total_area`。缺的是前端把「户型 + 房间状态」渲染为导航。

### 2. 生命线叙事（7 节点时间轴 + 健康分）— ❌ 未落地（后端能力就绪）

**Mockup 设计**：量房→设计→预算→施工→质检→结算→入住 7 节点主轨 + 当前节点子工序 + 施工健康分环。

**现状**：两端关键词扫描「生命线/健康分/进度环/健康度」**0 命中**（Flutter lib 与 webapp src 均无）。无 7 节点时间轴，无健康分展示，无子工序步进。

**后端能力（全部就绪）**：
- 施工健康分：`health_monitor.py` `health_score` 5 级预警（[health_monitor.py:57](file:///Users/netsong/Developer/i-home.life/app/services/health_monitor.py#L57)）+ `predictive_maintenance_service.py` 施工健康度 summary（[predictive_maintenance_service.py:300-336](file:///Users/netsong/Developer/i-home.life/app/services/predictive_maintenance_service.py#L300-L336)）。
- 节点进度：`/api/construction/progress-analysis`、`/api/payments/milestones/{project_id}`（[payments.py:75](file:///Users/netsong/Developer/i-home.life/app/api/payments.py#L75)）。
- 主动预警：`/api/construction/progress-alerts`（[construction.py:440](file:///Users/netsong/Developer/i-home.life/app/api/construction.py#L440)）。

### 3. Ambient 管家（主动卡片流 + Agent 归因）— ◑ 机制就绪，表达未落地

**Mockup 设计**：AI 从「聊天标签页」升级为主动卡片流；每条建议标注「由哪个智能体产生、依据什么」。

**现状**：
- 「AI 管家」两端均为**被动聊天页**：webapp `Ai.jsx:89`、Flutter `ai_chat_page.dart`。
- A2UI 卡片协议已内化：Flutter 渲染器含 8 类卡片（设计/预算/进度/采购/质检/结算/材料/告警，[a2ui_renderer.dart:361/505/764/1028/1172/1343/1525/1638](file:///Users/netsong/Developer/i-home.life/flutter_app/lib/services/a2ui_renderer.dart#L361-L1638)），但**仅在聊天消息内渲染**（[ai_chat_page.dart:1076](file:///Users/netsong/Developer/i-home.life/flutter_app/lib/pages/ai_chat_page.dart#L1070-L1080)）——没有「首页主动卡片流」入口。
- Agent 主动回复机制存在（chat_service 聊天室 Agent 成员 + 自动回复），但无「主动卡片 feed」的容器。

### 4. 信任资产（节点放款/溯源/审计）— ◑ B 端有，C 端未落地

**Mockup 设计**：资金托管节点流水、材料一板一码溯源、质检 HMAC 审计。

**现状**：
- 后端就绪：`escrow_trustee.py` 存管账户（[escrow_trustee.py:117](file:///Users/netsong/Developer/i-home.life/app/api/escrow_trustee.py#L117)）、`payments` 里程碑、`MaterialBoardTrace` F50 一板一码（[eco_material.py:41](file:///Users/netsong/Developer/i-home.life/app/models/eco_material.py#L41)）、审计 HMAC。
- web 端：console（B 端）有 `PaymentsPage` 支付管理；**webapp（C 端）与移动端无托管/溯源视图**。
- ⚠️ 发现 P2 缺陷：`MaterialBoardTrace` 未注册进 `app/models/__init__.py` `__all__`（`from app.models import MaterialBoardTrace` 失败；docs 计数 128 vs 注册 127），虽已进 `Base.metadata`（表安全），仍须补注册。

## 三、并行全量工程健康度（要点）

- **版本一致性**：config/.env/.env.example/.env.production.example/pubspec/config.dart/settings_page/MCP/deploy-production.sh/webapp/console/CI 全部 1.13.1 ✓
- **门禁**：Flutter analyze 0 issues、Flutter test 95/95、webapp build ✓、console build ✓、flake8 0、mypy 0（353 文件）
- **全量 pytest**：运行中（基线 test_baseline.json = 2139 passed / 10 skipped / 4 xfailed）
- **发现项**：
  - P2 `MaterialBoardTrace` 未注册 `__all__`（见上）
  - P2 `agent_traces` 无建表迁移（依赖运行时 create_all；[b0c1d2e3f4a5:55](file:///Users/netsong/Developer/i-home.life/alembic/versions/b0c1d2e3f4a5_add_agent_trace_token_budget.py#L55) 注释自证），本地 `data/ihome.db` 实测缺该表
  - P3 console 页面 65（tsx）vs 文档声称 64；README「128 ORM 模型」实为 metadata 128 表、`__all__` 注册 127
  - 覆盖缺口收敛至 14 个 API 模块无前端页面（多为基建/语音/管理类：auth/files/config/health/admin/notifications/analytics/voice*/sensor_snapshot/product_batch/camera_scan）
  - 工作树残留 `scripts/deploy-remote.sh` 未提交改动

## 四、落地路线建议

- **P0 移动端空间首页**：复用 `floorplans` + 房间状态 + A2UI 卡片，把 `home_page` 从「纯聊天」重构为「空间即导航」首页（户型图 + 房间阶段着色 + 点击浮层），聊天降为次入口。
- **P1 生命线 + Ambient 流**：移动端 7 节点时间轴（progress-analysis + milestones + health_score 环）；把 A2UI 8 类卡片从聊天内提为首页「主动卡片流」，卡片 footer 标注 Agent 归因；webapp 三栏 bento cockpit 同构。
- **P2 信任资产 C 端化**：webapp/移动端补资金托管节点视图与材料溯源入口（后端已就绪）。
- **P2 缺陷修复**：`MaterialBoardTrace` 补注册 `__all__`；`agent_traces` 补建表迁移（对齐 F40 迁移链补齐模式）；README console 页数 64→65 校准。

## 六、落地执行状态（2026-08-11 更新）

按第四节路线执行完毕，验证全绿：

| 项 | 状态 | 证据 |
|---|---|---|
| P0 移动端空间首页 | ✅ | `home_page.dart` 重构为「家的生命线」：项目卡/7 节点生命线/健康分环/空间状态/主动卡片流/管家入口；`AIChatPage` 增 `prefillText` |
| P1 Ambient 主动卡片流 | ✅ | 移动端 + webapp 均落地：进度预警卡片 + Agent 归因 footer「Health OS 自动生成」 |
| P1 webapp bento 工作台 | ✅ | `Dashboard.jsx` 三栏 bento（空间/生命线+主动流/健康&信任）+ api.js 3 方法 + pages.css 样式族 |
| P2 MaterialBoardTrace 注册 | ✅ | `__all__` 128/128，`from app.models import MaterialBoardTrace` 可用 |
| P2 agent_traces 建表迁移 | ✅ | `c0d1e2f3a4b5` 幂等建表；空库 upgrade→downgrade -1→upgrade 往返 ✓；本地库 drift 0 缺失 |
| P2 基线/文档校准 | ✅ | test_baseline 2151/2/4；README/CLAUDE console 66 页 |
| 验证 | ✅ | Flutter analyze 0 + 96 tests；webapp build ✓；flake8/mypy 0 |

### 追加：「空间即导航」打通户型图逐房间状态 + A2UI 8 类卡片并入首页 feed（2026-08-11）

| 项 | 状态 | 证据 |
|---|---|---|
| 后端 room_status 字段 | ✅ | `FloorPlan.room_status`（Text JSON，`{"客厅": "in_progress"}`）模型/Schema/Service 全链路；Create/Update/PATCH 支持；`floorplans` 列表与详情接口返回 |
| 数据库迁移 | ✅ | database.py `_SCHEMA_MIGRATION_VERSION` 7→8（幂等 ALTER）；alembic `a7b8c9d0e1f2` 空库 upgrade→downgrade→upgrade 往返 ✓ |
| Feed API | ✅ | 新增 `GET /api/feed/{project_id}`：`home_feed_service` 将项目现有数据组合为 A2UI 8 类卡片（alert_card←预警 / design_plan←户型 / construction_progress←里程碑 / budget_breakdown←预算 / procurement_order←订单 / qa_report←质检 / settlement_summary←结算 / material_card←材料），附 `source_note` 诚实标注 |
| 移动端首页 | ✅ | `home_page.dart`：激活户型「户型图逐房间」网格（rooms 几何 + room_status 着色）；非激活户型房间状态摘要；feed 用 `A2UIRenderer` 渲染 A2UI 卡片（预警列表保留为回退） |
| webapp Dashboard | ✅ | 新增 `A2UICard.jsx`（8 类卡片 web 渲染器）；空间状态卡片户型图逐房间；管家主动卡片并入 A2UI feed |
| 测试 | ✅ | 后端 +4（floorplan room_status 1 + feed 3）；Flutter +1（户型图逐房间 + A2UI feed）= 97；pytest 全量见门禁 |
| 基线校准 | ✅ | `test_baseline.json` 2151/2/4 → **2155/2/4**（venv 全量 2161 collected = 2155 passed + 2 skipped + 4 xfailed，16:37 EXIT_CODE=0）；CLAUDE.md 路由 74→75 / include_router 77→78 同步 |

诚实边界：7 节点与健康分为**按现有数据推断**（项目状态 + 户型存在 + 里程碑完成度 / 预警严重度扣分），已在 UI 标注「阶段概览 · 按现有数据推断」「仅供参考」；逐房间状态为**真实后端字段**（`floor_plans.room_status`，可由用户/AI 管家维护），未标注时 UI 明示「房间施工状态暂未标注」；feed 卡片均由项目现有业务表组合，footer 标注「按 A2UI 协议生成，仅供导航参考」。

## 五、证据索引

| 维度 | 位置 |
|---|---|
| 移动端首页=聊天 | flutter_app/lib/pages/home_page.dart#L54 |
| 移动端工作台=统计卡 | flutter_app/lib/pages/dashboard_page.dart#L76 |
| web 工作台=统计卡+快捷 | webapp/src/pages/Dashboard.jsx#L62 |
| web 项目页=CRUD | webapp/src/pages/Projects.jsx |
| A2UI 卡片仅聊天内渲染 | flutter_app/lib/services/a2ui_renderer.dart（8 类）；ai_chat_page.dart#L1076 |
| 健康分后端 | app/services/health_monitor.py#L57；predictive_maintenance_service.py#L300 |
| 里程碑/预警 API | app/api/payments.py#L75；construction.py#L440 |
| 托管/溯源 | app/api/escrow_trustee.py#L117；app/models/eco_material.py#L41 |

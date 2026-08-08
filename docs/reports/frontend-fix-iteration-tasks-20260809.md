# 下一轮迭代任务拆解清单 — 前端修复

> 生成日期：2026-08-09 · 依据：`docs/reports/backlog-external-frontend-20260808.md` + 工作区前端未提交改动实测状态
> 目标：前端缺口（console +12 页 / Flutter +3 页）收尾发布，并规划剩余前端待办

---

## 〇、当前状态基线（实测）

| 项 | 状态 |
|----|------|
| console-src 新页面（未提交） | 12 页：A2A / AIImage / AgentApprovals / AgentIdentity / AgentMemory / AgentSkills / Eval / Harness / Identity / MCP / Points / Surveys |
| console-src 修改（未提交） | App.tsx / SideNav.tsx（路由）/ api-client.ts（API 封装）/ domain.ts（类型） |
| flutter_app 新页面（未提交） | 3 页：b2b_delivery / sketch_to_3d / ifc_export |
| flutter_app 修改（未提交） | api.dart（类型化方法）/ project_detail_page.dart（功能入口 +3） |
| 版本基线 | v1.11.0 已发布（tag 已推送）；CHANGELOG [Unreleased](08-09) 记录前端缺口 |

---

## 阶段 P0：已开发前端缺口收尾（当前工作区 → 提交发布）

**目标**：把已完成的前端缺口（B1 Agent 治理 8 页 + C 单端独缺 7 页）提交并验证发布。

| # | 任务 | 验收标准 | 依赖 |
|---|------|---------|------|
| P0.1 | console 构建验证 | `cd console-src && npm run build` 0 错误 | 无 |
| P0.2 | flutter 静态检查 | `cd flutter_app && flutter analyze` 0 issues | 无 |
| P0.3 | 12 页功能自查（flag 门控/诚实降级） | 各页对接真实 API；flag 关闭时降级不报错 | 后端 flag 状态 |
| P0.4 | 全量回归 | pytest 2046 passed 不回退（前端不改后端，回归保障） | 后端 |
| P0.5 | CHANGELOG [Unreleased](08-09) → 新版本块 | 版本号全链路 bump（模板 version-bump.md） | P0.1-P0.4 |
| P0.6 | 提交 + push（+ 按需打 tag） | `origin/main..HEAD` = 0 | P0.5 |
| P0.7 | CLAUDE.md / CODE_WIKI / backlog 状态同步 | 基线数字与页面计数一致 | P0.6 |

**风险**：console-src/flutter 改动量大（api-client +768 / domain +843 行），review 需聚焦契约（API 字段与后端 schema 对齐）。

---

## 阶段 P1：前端页面修复与体验完善（B1/C 已开发页）

**目标**：对已开发 19 页做 QA 与移动端/Web 对齐修复。

| # | 任务 | 验收标准 |
|---|------|---------|
| P1.1 | 空态/错误态/加载态覆盖 | 每页 3 态齐全，无裸奔异常 |
| P1.2 | 越权与 403 处理 | 无权限时诚实提示，不伪装成功 |
| P1.3 | 移动端适配（Flutter 3 新页） | 小屏布局无溢出 |
| P1.4 | 与 Web 既有页面功能对齐 | 功能项无缺（对照 DeliveryPage/Sketch3DPage/IFCExportPage） |
| P1.5 | 时区/时间展示复核 | 新页时间字段统一 +08:00（沿用 `_BJ_TZ` 约定） |

---

## 阶段 P2：剩余前端缺口补页（backlog B2/B3/B4）

**目标**：补齐数据/管理型页面（依赖运营数据或生态接入后有价值）。

| # | 模块 | 端 | 后端路径 |
|---|------|----|---------|
| P2.1 | B2 物联监测 5 页 | Flutter | /api/energy /api/sensors /api/health-monitor /api/construction-drawing /api/analytics |
| P2.2 | B3 管理后台 4 页 | Web console | /api/admin /api/notifications /api/files /api/payments |
| P2.3 | B4 供应链边缘 4 页 | Flutter | /api/products/camera /api/products/batch /api/location /api/voice/* |

**前置依赖**：B2/B3 部分页（energy/health-monitor 数据源、admin 运营数据）需 A1 生态接入或运营数据就绪；voice 需语音服务配置。

---

## 阶段 P3：生态桥接真实接入（backlog A1，P0 商务决策）

**目标**：5 个桥接 stub → 真实设备联动（打通 sensor 触发 → 设备控制闭环）。

| # | 桥接 | 所需凭据 | 当前 |
|---|------|---------|------|
| P3.1 | MijiaBridge | python-miio 签名（登录已真实，补齐 get_devices/send_command） | 部分 |
| P3.2 | HomeKitBridge | HAP pairing_code / setup_payload | 纯 stub |
| P3.3 | HarmonyOSBridge | app_id / app_secret / device_id | 纯 stub |
| P3.4 | MatterBridge | passcode / discriminator | 纯 stub |
| P3.5 | TuyaBridge | access_id / access_secret / endpoint | 纯 stub |
| P3.6 | scene_automation 真实执行 | `action_status="pending"` → 真实执行 | 打通 |

**风险**：需商务/凭据决策，无法纯代码闭环（诚实降级保留，禁止伪装真实能力）。

---

## 阶段 P4：灰度 flag 开启（backlog A2，无代码）

**目标**：运营决策驱动，按需开启商业运营 Agent / 以销定产 / 真实渲染等 flag。

| flag | 说明 |
|------|------|
| growth/marketing/competitor_research/finance_recon | 商业运营 4 Agent（每日简报编排） |
| business_ops_orchestrator_enabled | Orchestrator 日报聚合（FC 定时触发） |
| procurement_demand_driven_enabled | 以销定产 |
| real_ai_render_enabled / real_embedding_enabled 等 | 外部依赖能力（需先完成凭据配置） |

---

## 优先级建议

1. **P0（收尾发布）**：立即执行——代码已开发完成，仅差验证/提交，产出最高
2. **P1（修复完善）**：P0 后跟进——19 页 QA
3. **P2（补页）**：随运营数据就绪排期
4. **P3/P4**：商务/运营决策驱动，无代码排期或纯 flag 操作

> 备注：`/api/analytics` collect_events 为「仅接收不持久化」预留端点（设计如此，勿当 bug）。

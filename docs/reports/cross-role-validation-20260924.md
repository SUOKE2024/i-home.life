# i-home.life 多角色交叉验证综合报告

| Field | Value |
|-------|-------|
| **Date** | 2026-09-24 |
| **Target** | 生产 `https://i-home.life`（v1.17.4）+ `https://i-home.life/console/` + webapp |
| **Method** | 3 个独立智能体模拟业主 / 管理员 / 供应商三角色并行真实操作（HTTP 实测 + 浏览器自动化） |
| **Scope** | 全景业务功能 + 全量业务数据 + 全链路业务流程 |
| **Request Volume** | 约 515 次 HTTP + 控制台 71 路由全量遍历 + webapp 5 页交互 |
| **Issues** | **Critical 1 · High 6 · Medium 5 · Low 2 · Observe 6** |

## 0. 结论速览

- **数据隔离与「诚实降级」两条红线：部分守住，但存在 1 处 Critical 越权与 1 处违反诚实降级的合规误判。**
- **6 条 High 全部为真实缺陷，已由主代理逐一读源码 + 生产实测双重核验**（不采信子代理结论）。
- **最严重问题不在单个接口，而在「项目归属校验语义已分叉成三套」**：`verify_project_access`（仅 admin+owner）、
  `verify_project_collaborator_access`（**只验角色、不验成员关系**）、`_verify_project_owner`（**仅 owner、无 admin**）。
  同一份「项目访问权」在三套语义下结论相反，直接导致 Critical 越权与管理员功能阻断同时存在。
- **供应链 B2B 链路在 API 层缺承载**：`order:read / quote:write / fulfillment:update / settlement:read` 四个权限码
  仅存在于 `app/rbac.py:228` 的声明，**无任何端点消费**；不存在供应商可见的采购需求池 / 询价池，
  故「业主下单 → 供应商接单」这条跨角色主链路在生产**当前不可达**。

---

## 1. 验证方法与安全纪律

### 1.1 三个智能体的角色与覆盖面

| 智能体 | 模拟角色（生产种子账号） | 覆盖范围 | 规模 |
|--------|------------------------|---------|------|
| **A** | 业主「张先生」13800138000 | 认证边界、项目管理、AI 设计/渲染降级链、预算算量、空间资产台账状态机、适老改造+补贴预检、智能家居/设备/传感器、AI 对话（含 SSE）、越权边界；webapp 浏览器实走 | 56 端点 / ~130 用例 / ~175 请求 |
| **B** | 平台管理员 13500135000 | 管理员鉴权边界（用业主令牌反测 admin 端点）、治理审计 OWASP+ATH、AI 服务商能力档案、Token 计量、FDE 现场记录、商业运营 Agent、自进化/可观测性、Robot-Ready、LCC2、缓存隔离、错误转译；控制台 71 路由全量遍历 | 46 端点 / ~190 请求 / 71 页面 |
| **C** | 供应商 13700137000（+ 监理 13600136000 备用） | 采购链路（以销定产/BOM 驱动）、供应商档案与商品、交付订单、结算托管、施工质检验收、跨角色可见性；console 14 页实走 | ~150 请求 / 14 页面 |

### 1.2 安全纪律（生产写入）

因授权为「生产环境完整验证（含写入）」，开工前固化 `/tmp/ihome-qa-20260924/GUARDRAILS.md` 并强制遵守：
只操作 5 个种子演示账号；**所有新建实体名称强制含标记 `QA-VERIFY-20260924-<A|B|C>`**；
禁止删改任何无标记的既有生产数据（3 个演示项目仅只读）；**禁止触发任何真实资金变动**；
禁止改配置/feature flag、禁止设备真实配对、禁止对外发送通知；单端点重复 ≤5 次、禁止压测；不修改代码仓库。

### 1.3 主代理复核（关键，防子代理误判）

按项目历史教训（子代理在安全/归属类判定上误判率极高），**全部 7 条 Critical/High 均由主代理亲自复现或读源码二次核验**，
并明确排除工具伪影（本项目历史有「导航风暴」「导航不可点」两条假阳性，分别源于并发子代理干扰与移动端抽屉断点）。
复核结论见第 2 节每条的「核验方式」列。

---

## 2. 发现的问题

### Critical

#### C-01 跨租户越权读取项目数据（含预算逐项单价与结算金额）

| Field | Value |
|-------|-------|
| **Severity** | Critical |
| **Category** | 安全（越权 / 跨租户数据泄漏） |
| **核验方式** | ✅ 主代理生产实测复现 + 读源码确认根因 |
| **端点** | `GET /api/feed/{project_id}` 及另外 8 个 API 模块 |

**现象**：用**供应商令牌**（13700137000，与目标项目无任何关联、无任何成员关系）读取业主「翠湖名邸 · 原木奶油风」
（`781bead8-b750-4806-b0ed-839be07eca02`），返回 200 且包含：

- `budget_breakdown`：逐项材料**单价与金额**（实木多层地板 65㎡ × 328 元 = 21320；无纺布墙布 200㎡ × 168 元 = 33600 …）
- `settlement_summary`：`total=106214 / paid=57294 / balance=48920`
- `design_plan`（完整户型与房间面积）、`construction_progress`、`material_card`

另实测「滇池湖畔 · 现代简约」（59829/25960）、「云栖雅苑 · 智能整装」同样可被该供应商读取。

**根因**：`app/rbac.py:114-144` `verify_project_collaborator_access` 在 admin / owner 之外，
**只要角色属于 `{"designer","contractor","supplier"}` 就直接放行，完全不校验该用户与该项目是否存在成员关系**：

```
# app/rbac.py:135-139（问题代码）
# F40 三方协作：允许协作角色（designer/contractor/supplier）查看项目
allowed_roles = {"designer", "contractor", "supplier"}
if current_user.role in allowed_roles:
    return project          # ← 无任何「该项目是否分配给此用户」的校验
```

代码库中**不存在**项目成员表（`project_members` / 参与方实体均无），即「F40 三方协作」的设计前提
（协作方被指派到具体项目）在数据层从未落地，函数因而等价于「任何协作角色可访问全平台任意项目」。

**影响面**：9 个 API 模块复用该函数 —— `feed.py` / `chat.py` / `files.py` / `floorplans.py` /
`construction_drawing.py` / `construction_snapshot.py` / `hard_decoration.py` / `gaussian_recon.py` / `vr_panorama.py`。
凡携带项目 ID 的请求均可跨租户读取，故泄漏面不限于 feed（同根因波及 IM 读写、文件附件、施工图、硬装方案、3DGS 重建）。

**为何长期未被自动化审计发现（重要）**：`app/eval/ihome_eval.py:564-571` 的 IDOR 覆盖检测
明确把 `verify_project_collaborator_access` 与 `verify_project_access` **视为同一语义**并计入「已覆盖」，
注释写「不再误计为越权缺口」。结果是评估器给该缺口持续打「已覆盖」，漂移检测/治理审计天然失明。

---

### High

#### H-01 项目周报六段确定性数据实际只产出两段

| Field | Value |
|-------|-------|
| **Severity** | High |
| **核验方式** | ✅ 主代理读源码确认跨文件属性名不一致 |
| **端点** | `GET /agents/projects/{id}/weekly-briefing`（及 FC 批量口径端点） |

`app/agents/orchestrator.py:508` 读取 `budget_row.total_amount`，而 `app/models/budget.py:17-18` 定义的字段是
`total_estimated` / `total_actual` —— **`Budget` 模型不存在 `total_amount` 属性**，必然抛 `AttributeError`。
该异常落在**单个大 try 块**内被吞掉，导致 `budget` / `procurement` / `inspections` / `milestones` **四段整体丢失**，
仅 `tasks`、`design` 两段正常返回。批量端点仍报 `succeeded=2 / failed=0`，故**监控完全不可见**。

**连带效应**：AI 建议段被喂入空值，对实际有 8.8 万预算的项目输出「预算：暂无数据」——
（已用 `GET /api/budgets/project/781bead8` 反证该项目确有预算）。这属「声称有而实际无」，触及诚实降级红线。

**单测漏网根因**：`tests/test_frontier_v1157.py` 的 fixture **不创建 Budget 记录**，
`budget_row` 恒为 `None`，恰好绕过出错分支，故测试长期为绿。

#### H-02 `scene_type` 受限枚举在三层均无兜底，非法值 201 落库

| Field | Value |
|-------|-------|
| **Severity** | High |
| **核验方式** | ✅ 主代理读三层源码 + 生产实测落库确认 |
| **端点** | `POST /api/scene-automation/scenes`、`PATCH /api/scene-automation/scenes/{id}` |

实测 `scene_type=wakeup` / `sleep` / `QA_GARBAGE_XYZ` 全部返回 **201 并持久化**（读回确认），PATCH 同样 200。

三层全缺：

1. **Schema**：`app/schemas/scene_automation.py:25` 为裸 `str = "manual"`，合法值只写在注释里
   （对比**同文件** `EcosystemName` 已正确使用 `Literal`，说明是遗漏而非有意设计）；
2. **Model**：`app/models/scene_automation.py:11-43` 的 `SceneAutomation` **完全没有 `__table_args__`**
   （无任何 `CheckConstraint`）；
3. **迁移**：`alembic/versions/b8c8d9e0f1a2_backfill_model_check_constraints.py:10` 中
   `scene_automations` **仅出现在 docstring 注释**列举，并未纳入 166 条回填清单。

与 CLAUDE.md「`scene_type` 合法值为 `manual/scheduled/triggered/geo`」及 v1.17.4
「生产实测 32 → 198 条约束，越界枚举被拒」的结论**直接冲突**——该表是 CHECK 回填的漏网表。

**缓解现状**：三端客户端仅发送合法值，生产暂未观察到 App 产生的脏数据（狐探数据为我方标记产物，见第 5 节清理清单）。

#### H-03 健康监测 `device_id` 外键与穿戴 BLE 上报契约互斥，链路恒 422

| Field | Value |
|-------|-------|
| **Severity** | High |
| **核验方式** | ✅ 主代理生产实测复现（422）+ 读源码确认 |
| **端点** | `POST /api/health-monitor/records` |

实测 `device_id="AA:BB:CC:DD:EE:FF"` → `422 引用的关联记录不存在（health_monitors_device_id_fkey）`；
传真实 `smart_devices` UUID 才 201。

**根因**：`app/models/health_monitor.py:26` 定义为 `ForeignKey("smart_devices.id")`，
而 `flutter_app/lib/pages/wearable_devices_page.dart:98` 直接传 `_ble.device?.remoteId.str`（BLE MAC / 平台侧非注册 UUID），
CLAUDE.md 亦明确「device_id=BLE MAC」。**三处口径互斥**，导致**适老/穿戴康养链路的「心率等真实上报」在生产不可用**——
这正是项目对外主张的康养运营核心能力之一。

#### H-04 供应商发布商品必然 422（回退空字符串违反外键）

| Field | Value |
|-------|-------|
| **Severity** | High |
| **核验方式** | ✅ 主代理读源码 + 生产数据核对 |
| **端点** | `POST /api/products` |

`app/api/products.py:81-84`：

```
stmt = select(Supplier).where(Supplier.phone == current_user.phone)
supplier = result.scalar_one_or_none()
supplier_id = supplier.id if supplier else ""     # ← 回退空字符串
```

生产 `suppliers` 表 12 条真实档案手机号均为 `139xxxx` 段，**不含 13700137000**（供应商角色演示账号无对应档案），
故反查恒失败 → `supplier_id=""` → `products_supplier_id_fkey` 违反 → 422。

**验证闭环**（C 智能体完成，已复核其证据）：先创建 phone=13700137000 的供应商档案后，
同一请求立即 200 且 `supplier_id` 正确填充。

**性质**：这是「**授权门槛已过（角色校验通过）但数据前置缺失**」的静默失败——用户无法自行诊断，
且错误文案只暴露外键名不指向根因。

#### H-05 BOM→自动采购订单的供应商匹配因口径错误恒失败

| Field | Value |
|-------|-------|
| **Severity** | High |
| **核验方式** | ✅ 主代理读源码 + 生产 `suppliers` 实际取值核对 |
| **位置** | `app/services/procurement_service.py:256` |

```
cat_name = item.material.category.name if ... else "未分类"   # 取「地面材料」这类中文名
...
.where(Supplier.category == cat_name, ...)                     # 与供应商品类比对
```

而生产 `suppliers.category` 实际存储的是**代码**（实测：`flooring` / `appliances` / `wall` / `kitchen_bath` /
`custom_furniture` / `doors_windows` / `mep`）。中文名与代码**永不相等** → 同品类匹配恒失败 →
**全品类一律落到「任意活跃供应商」兜底**（实测落至「大金空调」，评分 4.9）。

**对照证据**：同仓库 `app/services/procurement_enhanced_service.py:138` 使用的是 `category.code`（正确写法），
说明 `procurement_service` 是遗漏点。

**业务影响**：以销定产（`procurement_demand_driven_enabled` 默认 True）的采购建议**供应商选择维度实质失效**——
优先级档位仍由 BOM 驱动，但「料 → 商」匹配退化为随机兜底，直接削弱采购准确性与成本控制能力。

#### H-06 管理员角色在项目维度整体不可用（三套归属校验语义分叉）

| Field | Value |
|-------|-------|
| **Severity** | High（主代理由 B 智能体原判 Medium 上调） |
| **核验方式** | ✅ 主代理读源码 + 生产实测 403 |
| **端点** | `GET /api/projects`、`GET /api/dashboard/overview`、`GET /api/procurement/orders/detail/{id}` 等 |

**实测现象**：管理员令牌 `GET /api/projects` 返回 **0 个项目**（业主返回 4、设计师 1、供应商 0）；
`GET /api/dashboard/overview` 项目总数为 0，而 `/api/admin/stats` 显示「项目总数 5」——**同一系统内自相矛盾**；
`GET /api/procurement/orders/detail/{id}` 对**管理员返回 403**（业主 200 / 供应商 403 / 匿名 401）。

**根因**：项目访问校验语义已分叉为三套，对 admin 的处置互不一致：

| 校验函数 | 位置 | admin 是否放行 |
|---------|------|---------------|
| `verify_project_access` | `app/rbac.py` | ✅ 放行（CLAUDE.md 既定设计） |
| `verify_project_collaborator_access` | `app/rbac.py:114` | ✅ 放行（但**不验成员关系** → 见 C-01） |
| `_verify_project_owner` | `app/api/procurement.py:36-43` | ❌ **仅 `owner_id == user.id`，无 admin 分支** |
| `get_user_projects` | 项目列表服务 | ❌ **纯 owner 口径，无 admin 分支** |

**影响**：控制台侧采购/质检/适老/生态/智能家居/场景/局部焕新等 **20+ 页全部停在「请先选择项目」**；
管理员无法通过 UI 使用任何项目维度功能，只能依赖直接调 API。
主代理据此上调为 **High**：它同时构成**功能性阻断**（20+ 页不可用）与**角色模型不一致**（后端口径与 CLAUDE.md 冲突）。

---

### Medium

| ID | 发现 | 核验 | 位置 / 证据 |
|----|------|------|------------|
| **M-01** | `check-accessibility` 无实测数据即判 `score=100 / compliance=pass` —— 空 `rooms=[]` 或无任一实测值返回「无障碍通过（100 分）」，而同一响应的 `escape_route` 对缺失数据 5 项全标 `warning/未提供实测数据`。**业主不填数据即看到合规结论，违反诚实降级红线** | ✅ 读源码 | `app/services/elderly_adaptation_service.py:246` `if total_checks else 100` |
| **M-02** | **供应链 B2B 跨角色链路在 API 层无承载**：`order:read / quote:write / fulfillment:update / settlement:read` 四个权限码**仅存在于 `app/rbac.py:228` 声明，无任何端点消费**；不存在供应商可见的采购需求池 / 询价池。故 C 智能体对 A 所造采购需求（`a025c999`）轮询 4 轮 × 40s **恒 0 命中** | ✅ 读源码（grep 全仓仅 1 处）+ 生产实测（`GET /api/procurement/orders` → 405，列表端点不存在） | `app/rbac.py:228`；路由清单实证 |
| **M-03** | 比价端点无入参校验：`composite=372`、`saving=200%`、**推荐负价报价**均被接受 | 子代理实测（已复核响应留痕） | `POST /api/procurement-enhanced/comparisons` |
| **M-04** | 未发布（draft）商品及价格对**任意角色可读**；供应商档案端点无角色门控；`price_tier` 无枚举约束（实测 `luxury_unlimited` **201 入库**） | 子代理实测（已复核） | `GET /api/procurement/suppliers`、`POST /api/procurement/suppliers` |
| **M-05** | 结算负额 / 超额付款被 `max(0, …)` **静默夹取为 0**（掩盖错误而非报错），资金侧异常不可观测 | 子代理实测 | 结算相关服务 |

---

### Low / Observe

| 级别 | 发现 |
|------|------|
| Low | `history` schema 上限 20 条，与 CLAUDE.md `chat_context_max_turns=24` 的压缩口径不一致（A 实测 25 条 → 422） |
| Low | 422 响应回露 DB 约束名（如 `health_monitors_device_id_fkey`），属信息暴露面 |
| Observe | `POST /api/sensors/snapshot` 响应不含落库 ID（仅 `received/timestamp/sensors_count`），无法关联后续查证 |
| Observe | 多 worker 下限流为进程内存储，不共享（属已知 best-effort 设计，一致于 CLAUDE.md） |
| Observe | AI 对话 `/api/agents/chat` 实测 63.4s 返回（无超时保护观察项） |
| Observe | **`agent_traces` 近 30 天无新行；历史 10 行 token 全为 0**；`/api/harness/metrics` `total_runs=0`。即 Agent 成本与自进化可观测性**数据层空转**（与 CLAUDE.md 记载的 FC 空转同源），非接口故障 |
| Observe | CLAUDE.md 记「21 个执行型 Agent」，**该数字无法从任一注册表复现**：`agent_orchestration_service._agent_registry()` 实为 **19 个**（编排可调度子集），B 智能体经 `/api/harness/metrics` 探到 `registered_agents=27`（全量 harness 注册）。三者口径不同，**主代理未能确认「执行型」的权威定义**，故未擅改文档——需维护者明确该分类口径后再校准 |
| Observe | 控制台供应链页空态经三角验证确认为 `GET /api/projects` 返回 `[]` 所致（**非前端崩溃**） |

---

## 3. 跨角色交叉验证矩阵（本次核心）

| 核验项 | 业主 | 供应商 | 管理员 | 匿名 | 结论 |
|--------|------|--------|--------|------|------|
| `GET /api/projects`（各自可见） | 4（仅自己的） | 0 | **0** ❌ | 401 | 业主 owner 隔离**正确**；管理员口径**错误**（H-06） |
| `GET /api/procurement/orders/detail/{A 所造订单}` | 200 | 403 | **403** ❌ | 401 | 归属隔离正确，但管理员应放行（H-06） |
| `GET /api/feed/{翠湖名邸}`（供应商非成员） | — | **200 泄漏财务明细** ❌ | 200 | 401 | **Critical 越权**（C-01） |
| `GET /api/procurement/orders`（列表端点） | 405 | 405 | 405 | 405 | **端点不存在** → 供应商无需求池（M-02） |
| 业主所造采购需求能否流转至供应商 | 201 创建成功 | **不可见**（4 轮轮询 0 命中） | 不可见 | — | **跨角色链路无承载**（M-02） |
| 供应商所建档案 / 商品可见性 | 可见（手机号已脱敏） | 可见 | 可见 | 401 | 平台级共享数据，符合设计；但 draft 商品越权可读（M-04） |
| 越权访问他人项目（8 例） | 全部 404 | 404 | — | 401 | ✅ 隔离正确（`verify_project_access` 路径） |
| `summary?all_owners=true`（非 admin） | 403 | — | 200 | 401 | ✅ 正确 |

**数据准确性核验（首尾一致）**：A 所造项目自动生成空预算（`total_estimated=0.0`、`lines=[]`，**无伪造数值**）；
补贴预检给出 `total_subsidy=2520 / net_payable=14280`（套餐原价 16800）与 `600 / 3900` 两组，
加总关系自洽且恒带 `is_estimate=true` + `disclaimer` + 3~4 条 `warnings`，`max_subsidy_per_unit=null`
（**未内置地方目录，符合诚实红线**）。

---

## 4. 已守住的硬约束（正向核验结论）

以下为 CLAUDE.md 红线项，经三角色实测**确认行为达标**，无造假：

| 类别 | 实测结论 |
|------|---------|
| **轻资产约束** | 空间资产注入 `platform_role=owner` 被**忽略**，恒为 `service_provider`；API 层不接受该字段写入 |
| **状态机不可跳跃** | `assessed → operating` 严格返回 409，必须经 `in_renovation → delivered` |
| **就绪度评分** | 四维评分无数据项计 0 分并在 breakdown 标注，**无虚增** |
| **治理审计** | OWASP Agentic Skills Top 10（`total=10 pass=10`）与 ATH 信任层（ATH1-5）**两章节独立、未合并**，与源码控制点逐项吻合 |
| **AI 服务商能力档案** | `evidence` **26/26 路径磁盘真实存在**；`maturity_level` 恒 `not_assessed`；`disclaimer` 齐备；治理证据复用同一实现未重复造轮子 |
| **Token 计量** | 恒带 `metering_only=True / billing_ready=False / billing_note`，**未对外宣称计费闭环**；owner 隔离与非授权 `project_id` 403/404 正确 |
| **Robot-Ready** | 数据全缺时 `fail=0`，如实判「数据不足」而非「不合格」 |
| **LCC2** | 明示**不产出 `.lcc2` 二进制**，仅语义映射 sidecar |
| **商业运营 Agent** | 数据源逐段标注（`agent_feedbacks` / `internal_tables`），**无 Stripe/Fake 冒充** |
| **补贴预检** | `is_estimate=true` + `disclaimer` + `warnings` 完备；不内置地方目录；个人资格不参与判定 |
| **适老套餐元数据** | `elderly_design` 四维**只声明适用维度**（`dialect` 仅全屋套餐声明，卫浴/卧室不硬凑） |
| **AI 渲染降级链** | 如实标注 `mock` / `level 2` / `reconstruction_available=false`；`require_real` 时返回 503 |
| **设备链路** | 传感器范围校验 6 组越界**全部 422**；限流 429 生效；`room_type` / `protocol` 非法值 422（对比 H-02 的 `scene_type` 漏网） |
| **鉴权收口** | 曾匿名可读的 `/api/scenes/parse`、`/api/matter/device-types` 现已 **401**；`matter/commission` 仍为 stub 501（未补假 UI） |
| **生态归因** | 无桥生态返回 `unsupported_ecosystem`，**未误归** `invalid_credentials` |
| **控制台健康度** | 71 条路由全量遍历：**前端错误 0、网络 4xx/5xx 0**；侧栏 15 组导航与路由表逐条对应、0 悬空 |

---

## 5. 改进建议

### 5.1 立即（阻断级）

1. **统一项目归属校验语义（治本，一次性覆盖 C-01 + H-06）**
   - 确立**单一入口**：`verify_project_access(project_id, user, db, mode=...)`，`mode` 取值
     `owner_only | collaborator | admin_or_owner`，各端点显式声明所需语义，**禁止再新增自定义 `_verify_project_*` 辅助函数**。
   - 对 `collaborator` 语义，**必须补成员校验**：新增 `project_members`（或复用既有承接实体）并落库
     「用户 ↔ 项目 ↔ 角色」关系；在成员表落地前，**临时收严** `verify_project_collaborator_access` 为
     `admin ∪ owner ∪（显式指派）`，宁可让协作功能短暂不可用，也不可保持跨租户可读。
   - 阶段一可先对**财务敏感段**（feed 的 `budget_breakdown` / `settlement_summary`、文件、施工图）
     单独走 `admin_or_owner`，把泄漏面收敛到最小。
2. **修正评估器盲区**：`app/eval/ihome_eval.py:564-571` 将上述两个函数判为「同语义已覆盖」的等价规则**必须撤除**，
   否则修复后仍会被判定为「已覆盖」，且未来同类分叉继续隐身。建议评估器改为**校验「是否存在成员关系查询」**而非函数名白名单。
3. **H-01 一行修复 + 回归补测**：`orchestrator.py:508` 改为 `total_estimated`（或按语义取 `total_estimated`/`total_actual` 二者）；
   同时**补 Budget fixture** 到 `tests/test_frontier_v1157.py`，使单测真正走进出错分支；并把「六段齐备」写成断言。
4. **H-02 补三层兜底**：`scene_type` 改 `Literal["manual","scheduled","triggered","geo"]`
   （对齐 CLAUDE.md 与同文件 `EcosystemName` 写法）+ 模型补 `CheckConstraint` + **新增迁移**回填该表约束
   （`b8c8d9e0f1a2` 漏网表需单独补迁移，并同步 `scripts/check_schema_drift.py` 比对）。
   ⚠️ 补约束前须先清理第 6 节列出的非法枚举行，否则迁移会被脏数据阻塞。

### 5.2 短期

5. **H-03 二选一定契约**：或让 `/api/health-monitor/records` 接受 BLE 标识
   （`device_id` 去掉 FK，另设 `smart_device_id` 可空外键 + `external_device_id`），
   或让 Flutter 端先完成 BLE 设备注册再上报 UUID。**须同步 Flutter 上传字段与模型定义**（改 schema 两侧同改）。
6. **H-04 让失败可诊断**：`products.py` 反查失败时**显式 422 并说明「当前账号未绑定供应商档案」**，
   而非回退空串撞外键；并考虑为供应商角色注册流程自动建档。
7. **H-05 口径对齐**：`procurement_service.py:256` 改用 `category.code`，与
   `procurement_enhanced_service.py:138` 统一；补一条「BOM 品类 → 供应商品类」映射的单测。
8. **M-01 诚实降级**：`elderly_adaptation_service.py:246` 在无实测数据时应返回
   `score=null / compliance="insufficient_data"` 并标注缺失项，参照同响应 `escape_route` 的既有写法。
9. **M-05 取消静默夹取**：结算负额/超额应显式 422/409，不得 `max(0, …)` 吞掉。

### 5.3 中期（架构级）

10. **补上供应链 B2B 的 API 承载（M-02）**：为已声明的四个权限码落地端点——
    供应商侧「需求池 / 询价单 / 履约状态 / 结算视图」。否则「以销定产 + 供应链」仅为数据模型，
    三方协作链路（业主下单 → 供应商接单 → 监理验收）在生产不可闭环。
11. **把 `agent_traces` 空转纳入可观测性告警**：当前 `/admin/ai-usage/tokens`、`/api/harness/metrics`
    恒为空但无告警，导致 H-01 这类「批量报 succeeded/failed 均正常」的静默失败无法被发现。
    建议对 `weekly-briefing` 增加**段数断言**（期望 6 段、实得 N 段即告警），而非只看 HTTP 状态码。
12. **建立「受限枚举三端一致性」自动门禁**：H-02 的根因是「schema / model / 迁移」三层靠人工同步。
    建议扩展 `scripts/check_schema_drift.py`，对**声明了枚举注释但无 Constraint/Literal 的字段**直接报错，
    把口径漂移拦在 CI。
13. **文档口径待校准（需维护者定定义）**：CLAUDE.md「21 个执行型 Agent」无法从任一注册表复现（编排注册表 19 / harness 27）；`chat_context_max_turns`（24）与 chat schema 上限（20）的差异需统一。**主代理未擅自改动这些数字**，因缺乏权威分类定义。

---

## 6. 生产数据影响与清理（已执行完成）

本次验证按纪律仅创建**带 `QA-VERIFY-20260924-*` 标记**的实体，**未删改**任何既有演示数据，
**未触发任何资金变动**（资金类端点对供应商一律 403；未调用 `escrow/{id}/pay`、`refund` 等），
**未修改**任何配置 / feature flag / 凭据 / 代码仓库。3 个既有演示项目仅只读浏览。

### 6.0 清理结果（2026-09-24 执行）

**全量清理已完成**，生产已恢复验证前状态。分两阶段执行：

1. **API 阶段**（24 条走各自 DELETE 端点，多为 `204`）：场景 ×4（含 4 条故意非法枚举）、
   智能设备 ×2、智能家居方案 ×3、采购订单 ×1、空间资产 ×1、适老方案 ×1、FDE 记录 ×2、Agent 会话 ×3、QA 项目 ×1。
   期间 2 次 `422` 为外键阻塞（设备被健康记录引用、方案被子实体引用），随上层实体删除一并回收。
2. **数据库阶段**（5 条无 DELETE 端点，走事务精确删除）：商品 ×1、供应商档案 ×2、B2B 交付单 ×2。
   语句以 **ID + 标记名双条件**限定，`BEGIN/COMMIT` 事务内执行，删前删后各计一次数。

**清理后核验（全角色 API + DB 双向确认）**：

| 核验项 | 结果 |
|--------|------|
| 业主项目列表 | 3（← 恢复为 3 个演示项目，且 `status/phase` 与验证前逐字一致：`draft/design`、`active/procurement`、`in_progress/construction`） |
| 供应商档案总数 | **12**（← 恢复原始条数） |
| 商品目录 / B2B 交付单 / 空间资产 / FDE 记录 | 全部 `0` |
| 全库 `scene_automations` 非法枚举行 | **0**（← H-02 的迁移阻塞已解除） |
| 带 `QA-VERIFY-20260924` 标记的残留行 | 全表 `0` |

> 遗留说明：三个智能体中，A 未自行清理其非法枚举探测记录（已由本次统一清理），
> B 已自行删除 3 条自有探测记录，C 已剔除 2 个路径拼写导致的 404 假阳性。

### 6.1 标记产物清单（已全部清理，保留备查）

| 类型 | ID | 原因 |
|------|-----|------|
| scene ×4 | `37720cba`（已 PATCH 为 `wakeup`）、`a088231e`（`wakeup`）、`343a21ff`（`sleep`）、`6e2954c0`（`QA_GARBAGE_XYZ`） | **非法枚举落库**，补 CHECK 约束前必须先清 |
| supplier ×2 | `QA-VERIFY-20260924-C 供应商验证档案`、`QA-VERIFY-20260924-C price_tier 越界` | 后者 `price_tier=luxury_unlimited` 为非法值；且供应商列表**对任意角色可见**（12 条真实 → 14 条被污染） |
| product ×1 | `0bea5069`（published） | 业主端可见的测试商品 |

### 6.2 其余标记产物（集中在 A 的自建 QA 项目中，`82998c29-515e-428c-abc6-a0724be714fa`）

项目 ×1、空间资产 ×1（`3e87e1c5`）、适老方案 ×1（`6b06aba5`）、智能家居方案 ×2（`98281ac9` / `e0cbc03b`）、
智能设备 ×2（`9595b08b` / `c74089dd`）、健康记录 ×3（`73f0b771` / `cefdd892` / `e23a4a10`）、
AI 会话 ×3、采购订单 ×1（`a025c999`，`total_amount=0.0`）、FDE 记录 ×2（`47b1667a` / `7924d51f`）、
B2B 交付单 ×2（`65ce9975` / `48aab069`）、供应商档案 ×2。自动副作用：空预算 ×1（`b3d8a708`）。
**以上均已清理**（见 6.0）。

完整清单见 `/tmp/ihome-qa-20260924/{A,B,C}/created-entities.json`。

### 6.3 过程纪律说明

- A 智能体创建了 4 条**非法枚举场景**（含 1 条将合法值 PATCH 为 `wakeup`）——已如实登记，并由本次统一清理。
- B 智能体已自行删除 3 条自有标记探测记录（FDE 可弃记录 + 非法/合法场景各 1）。
- C 智能体已剔除 2 个因路径拼写错误导致的 404 假阳性，并对浏览器空态做了三角验证（归因 `GET /api/projects` 返回 `[]`）。
- 三个智能体均**未修改代码仓库**；工作树中 `CLAUDE.md` 的既有未提交改动为验证开始前状态，原样保留。

---

## 7. 原始证据索引

| 智能体 | 交付物 |
|--------|--------|
| A（业主） | `/tmp/ihome-qa-20260924/A/report.md`、`created-entities.json`、`evidence/`（40 份：31 curl 留痕 + 9 截图） |
| B（管理员） | `/tmp/ihome-qa-20260924/B/report.md`、`created-entities.json`、`evidence/`（40 份，含可复跑脚本） |
| C（供应商） | `/tmp/ihome-qa-20260924/C/report.md`、`created-entities.json`、`evidence/`（197 份，含 `browser/` 14 页截图） |

覆盖率缺口（诚实声明）：`UNIQUE → 409` 未在生产实测（候选唯一约束均涉资金/upsert，由
`tests/test_integrity_error_translation.py` 覆盖）；`POST /api/agents/memory` 的 `scope=org` 写入鉴权
因首测报文体缺参未取得有效 403 证据；因全仓无端点使用 `@cached`，缓存隔离仅能经用户态端点行为侧证。

---

## 8. 修复记录（本轮已实施，未提交）

按用户选择的方向修复：Critical 越权走**新建项目成员表根治**，穿戴 BLE 走**后端放开外键**。

### 8.1 C-01 + H-06：项目成员表 + 三套归属语义统一

| 变更 | 内容 |
|------|------|
| 新增模型 | `app/models/project_member.py` — `project_members` 表；`MEMBER_ROLES` 为协作角色单源；`UniqueConstraint(project_id,user_id)`（一人一条）+ `CheckConstraint(role IN (...))` |
| 新增迁移 | `a4b5c6d7e8f9_add_project_members.py`（幂等建表 + 2 索引，downgrade 可逆） |
| 核心修复 | `app/rbac.py:verify_project_collaborator_access` 改为 **admin ∪ owner ∪ 已授权成员**（角色与成员关系缺一不可）；新增 `is_project_member(db, project_id, user_id)` |
| 成员管理 | `GET/POST /api/projects/{id}/members`、`DELETE /api/projects/{id}/members/{user_id}`（仅 owner/admin）+ `app/services/project_member_service.py` |
| admin 口径 | `get_user_projects(is_admin=)`、`/api/dashboard/overview`、`app/api/procurement.py:_verify_project_owner` 三处放行 admin |
| 测试 | 新增 `tests/test_project_members.py` **18 用例**（含「非成员必须 403」直接反证、成员授权/撤销、越项目不越权、owner/admin 不回归、成员端点鉴权、重复添加更新角色等） |

**行为变更提示（预期，非回归）**：`project_members` 为空时，非 owner / 非 admin 访问 9 个协作类模块一律 403。
协作前须先经成员管理端点授权。这是有意的安全收严。

### 8.2 H-02：scene_type 三层兜底

- `app/schemas/scene_automation.py` 新增 `SceneType` Literal（Create + Update 均收窄）
- `app/models/scene_automation.py` 新增 `__table_args__` + `chk_scene_automation_scene_type`
- 迁移 `b5c6d7e8f9a0_scene_type_check_constraint.py`（幂等、SQLite batch / PG 原生、downgrade 可逆）
- 测试：非法值 4 例 422、4 个合法值仍 201、PATCH 非法值 422

### 8.3 H-03：health_monitors 设备两列分离

- `device_id` **去外键**（外部设备标识 / BLE MAC），新增 `smart_device_id`（平台内设备，保留外键）
- 关系显式绑定：`device = relationship("SmartDevice", foreign_keys=[smart_device_id])`
- `app/schemas/health_monitor.py` 增 `smart_device_id` 字段；health API 走 `model_dump()` 全量透传，无需改动
- 迁移 `c6d7e8f9a0b1_health_monitor_device_id_fk_relax.py`
- 测试：BLE MAC `device_id` 可 201 落库；两列职责分离的模型级断言（方言无关）

### 8.4 H-01 / H-04 / H-05（并行子代理实施，主代理已逐条核验代码）

- **H-01**：`orchestrator.py` 预算字段改 `total_estimated`/`total_actual`；六段聚合抽为 `_collect_weekly_sections`
  并**逐段 try**，失败段诚实标注 `{"available": false, ...}` 而非静默丢失。测试补建 Budget fixture（此前的漏网根因）+ 新增「单段失败不影响其余五段」用例。
- **H-04**：`app/api/products.py` 反查失败改**显式 422 可诊断**（文案指向「未绑定供应商档案」），不再回退空串撞外键；
  同失败模式的 `app/api/camera_scan.py` 一并最小修复。
- **H-05**：`procurement_service.generate_from_bom` 分组键改用 `MaterialCategory.code`（对齐 `procurement_enhanced_service`），
  中文名仅用于订单 note；回落兜底保留并新增 `logger.warning` 标注「非同类匹配，需人工确认」。

### 8.5 门禁验证结果

| 门禁 | 结果 |
|------|------|
| flake8（全部改动文件，max-line-length=120 / max-complexity=15） | **exit 0** |
| mypy（改动后端源码） | **Success: no issues found** |
| 新增测试 `tests/test_project_members.py` | **18 passed** |
| 受影响模块回归（projects/dashboard/feed/chat/files/floorplans/scene_automation/health/smart_home_idor） | **112 passed** |
| 子代理覆盖回归（frontier_v1157/v1158/products/supplier_rbac/procurement_service/camera_scan/lifecycle_chain） | **78 passed**（另有 115 passed / 39 passed 两批） |
| 迁移可逆（新 SQLite 库 `upgrade head` → `downgrade -3`） | **三向均干净回滚** |
| `scripts/check_schema_drift.py`（迁移建库 vs 模型） | **✅ 0 表/列/CHECK 缺失** |
| 子代理缺陷反证（stash 掉修复后跑新用例） | **4 failed**（逐条复现缺陷，证明测试有效） |

### 8.6 未做事项（诚实声明）

- **未提交**（git 工作树保留改动，见 `git status`）
- **全量 pytest 基线已跑通**：`2864 passed, 2 skipped, 4 xfailed, 0 failed`（`-n 4`，12 分 50 秒）。
  基线 2842 + 本轮新增 22 用例（成员授权 18 + 周报/商品/采购口径 4）= **2864**，精确吻合，**无回归**。
  执行时机说明：核查时发现**有 pytest 进程在跑**（PID 42035 → 43975 → 47540，非本会话发起），
  按项目纪律（负载 < ncpu/2 且无外部测试进程方可采信）**先等待至负载降至 2.49/8** 才启动，
  并以 `-n 4`（而非 `-n auto`）限制争用。事后追溯 cwd（见 §9）确认那些进程 **cwd 在
  `suoke_life/*` 兄弟仓库**，仅争用 CPU、**不触及本仓工作树**，故本条不影响结果可信度。
  `scripts/test_baseline.json` 已 `--update` 校准为 2864，
  CLAUDE.md 基线数字同步（collect 2870 = 2864 + 2 skipped + 4 xfailed）。
- **未做版本号 bump**（触及 config/.env/CHANGELOG 等 14 处，属发版动作，待用户确认）
- **未改** `app/eval/ihome_eval.py` 的 IDOR 白名单（属「审计盲区」修复，用户本轮选择先修 Critical/High）
- **未修** M-01~M-05 与供应链 B2B 端点缺失（M-02 需新建 4 类端点，属架构级中期项）
- **未改** Flutter 端：`wearable_devices_page.dart` 现传 BLE MAC 到 `device_id` 已可正常工作，
  无需改动（后端放开外键后契约自洽）；若后续要关联平台设备，再改用 `smart_device_id`

---

## 9. 外部会话进程排查（2026-09-24 22:50，未提交风险核查）

### 9.1 结论

**没有任何外部会话在 `i-home.life` 仓库内执行命令；本次未提交改动未被触碰。**

### 9.2 进程全貌

| 进程 | PID | cwd | 判定 |
|------|-----|-----|------|
| `pytest tests -q`（privacy-service） | 47540（父 47539） | `suoke_life/functionai_services/node-general-services/privacy-service` | **兄弟仓库**，仅争 CPU |
| `pytest tests/ -q -k "a2a or eco"`（agents-service） | 47333（父 47332） | `suoke_life/functionai_services/node-ai-inference/agents-service` | **兄弟仓库**，仅争 CPU |
| `gateway/dev_server.py` | 46580（ppid=1） | `suoke_club/backend` | **兄弟仓库**，孤儿守护进程 |
| `blender-mcp` ×4 | 18827/19159/19319/86811 | — | MCP 服务常驻（2 天+），idle |
| 驻留 shell 包装壳 | 64140（09-23 07:35）/ 64719（09-23 07:45） | `i-home.life` | **只读**：`while pgrep …; do sleep N; done; tail -6/14 /tmp/pytest_full.log` |
| IDE 交互终端 | 17421（`zsh -i`）/ 30737（`zsh -il`） | `i-home.life` | idle 无作业 |
| `sourcery lsp` | 19529 | `i-home.life` | 只读代码分析（不经用户确认不改文件） |

### 9.3 关键澄清：此前的「外部 pytest」误判来源

先前据 `pgrep -f "pytest tests"` 判定的「外部会话在跑本仓全量测试」**部分为误读**：

1. 那些 `pytest`（42035 → 43975 → 47540）**cwd 在 `suoke_life/*`**，不涉及本仓。
2. 两个 09-23 的驻留包装壳（64140/64719）命令行**文本里就含 `pytest tests/`**（其 `pgrep` 参数），
   因此任何据此模式的存在性检查**必然命中它们**，造成「外部测试一直在跑」的假象。
3. 更关键：这两壳的退出条件是「`pgrep -f "pytest tests/"` 无匹配」，而**我自己的 pytest 命令**
   （`.venv/bin/python -m pytest tests/...`）恰好匹配该模式 → **是我在给它俩续命**，它们因此永驻
   （父进程均为 toolhost 15972，来自 09-23 的旧 i-home.life 会话作业 `job-a196d85c…` / `job-88ee40371…`，
   `output.log` 均为 0 字节）。

### 9.4 仓库完整性证据

| 检查项 | 结果 |
|--------|------|
| `.git/*.lock` | 无 → 无进程持有仓库 |
| `git log -1` | 仍为 `7507878`，**未被外部提交/回退** |
| `git status --short` | 28 项改动完好（21 修改 + 7 新增） |
| 本仓内正在执行的命令 | **0**（唯一 `status=Running` 且 cwd 属本仓的两个作业即上述只读包装壳） |

### 9.5 清理结果（2026-09-24 22:49 已执行）

经用户确认「清记录 + 终止壳（彻底）」后执行：

| 步骤 | 操作 | 结果 |
|------|------|------|
| 1 | 归档 `state.json` + 进程快照至 `/tmp/ihome-qa-20260924/parked-shells-archive/` | 3 份文件（2 个 state.json + process-snapshot.txt） |
| 2 | 按**进程组**终止（两者均为各自 PGID 组长）：`kill -TERM -64140` / `kill -TERM -64719` | 两壳及其 `sleep` 子进程全部退出 |
| 3 | 移除两个僵尸作业目录 `job-a196d85c…` / `job-88ee40371…` | 作业目录 3515 → **3513** |

**清理后核查**：

- `pgrep -f "pytest tests/"` 命中数 **0**（自匹配诊断污染已消除，此前该模式恒真）
- `cwd` 属本仓的剩余进程仅为：`sourcery lsp`（只读分析）、2 个 Trae IDE 渲染进程、2 个 idle 交互终端
  —— **无任何测试/命令执行进程**
- 仓库完整性：`.git` 无 lock、`HEAD` 仍为 `7507878`、28 项改动完好
- 系统负载回落至 2.32/8（另一项目 `suoke_life/privacy-service` 的 pytest 属其自身活跃工作，未干预）

**根因与后续建议**：这两个壳的写法 `while pgrep -f "pytest tests/" >/dev/null; do sleep N; done` 存在
**自匹配死循环**——其命令行文本本身含 `pytest tests/`，故条件恒真、永不退出（且会被任何同模式的
进程检查误判为「测试在跑」）。后续判断测试是否在跑应改用 `pgrep -f "[p]ython -m pytest"` 并**校验 cwd**，
避免再次产生此类驻留壳。

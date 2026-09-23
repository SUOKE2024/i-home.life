# 合作方加盟实现方案 — 技术检查与评估报告

> 评估日期：2026-09-22 ｜ 评估对象版本：i-home.life v1.17.0（最后提交 `815e5fe`，2026-09-12）
> 评估范围：① 3DGS（3D 高斯泼溅）虚拟看房系统；② 智能家居集成方案
> 证据纪律：**本文所有"实现现状"结论均由主代理逐行 Read 源码核验**，标注 `文件:行号`。
> 标注「需实测」的条目指代码路径已具备但缺真实硬件/账号/设备验证，不构成"已实现"结论。
> 涉及 2026 外部标准/规范的前沿对标条目标注「需外部复核」，不以本文为最终结论。

---

## 一、结论先行

| 评估对象 | 判定 | 一句话结论 |
|---|---|---|
| **合作方加盟（业务实体）** | 🔴 **未实现** | 全仓零代码落点，无 `franchise/加盟/合作方` 实体、角色、端点、页面；仅有若干**可复用的既有资产**（供应商生态 / 空间资产台账 / ATH 握手 / 结算托管） |
| **3DGS 虚拟看房** | 🟡 **资产托管与渲染就绪，内容生产链缺失** | 上传/托管/双轨渲染（WebGPU 原生 + Spark 回退）/漫游/设备热点联动**已真实落地**；但"从户型或照片生成 3DGS"能力为 **0**（后端 mock + 云端重建默认关闭），移动端交互与兼容性验证缺位 |
| **智能家居集成** | 🔴 **控制链路存在 P0 断链，真机能力不可达** | 5 个生态桥仅米家真机化，但**设备命令/场景执行路径未传任何凭据**，米家真机代码恒不可达 → 所有动作恒 `pending`；Matter 配网端点恒 501；传感器触发到执行断链 |

**最重要的一条**：智能家居不是"接入不足"，而是**已写好的米家真机代码在两条生产路径上都无法被调用**（[scene_automation_service.py](file:///Users/netsong/Developer/i-home.life/app/services/scene_automation_service.py#L1026) 与 [:1166](file:///Users/netsong/Developer/i-home.life/app/services/scene_automation_service.py#L1166) 调 `pool.get(ecosystem)` 不带凭据）。诚实降级做得好（标注 pending 而非伪装成功），但**业务能力等于零**，且 `docs/reports/device-link-hardening-20260827.md` 中"米家真机化"的表述会误导读者以为控制链路已通。

---

## 二、合作方加盟模块现状判定

### 2.1 现状：零实现（已核验）

全仓检索 `加盟|franchise|合作方|经销商|招商`，仅 3 处命中且**全部为非代码**：

- `CHANGELOG.md`（历史叙事，提及"尚无云南本地合作方"）
- `CODE_WIKI.md`（文档描述）
- `goai-agent-infra/house-design-platform-prd.html`（外部 PRD 物料）

**不存在**：加盟实体模型 / 加盟申请表 / 分润与结算规则 / 加盟方专属角色 / 加盟商控制台页面 / 加盟方数据隔离策略。

角色体系亦无对应位置——[rbac.py](file:///Users/netsong/Developer/i-home.life/app/rbac.py#L30-L33) 固定为 `homeowner / designer / contractor / supplier / admin` 五类。

### 2.2 可直接复用的既有资产（评估方案时应优先复用，勿另造）

| 资产 | 落点 | 对加盟场景的复用价值 |
|---|---|---|
| 供应商生态 | `app/models/procurement.py:10` `suppliers` 表；`supplier_daily_briefing`（v1.15.6） | 加盟方若含"供货/施工"属性，可复用供应商主体 + 每日经营简报 |
| 空间资产台账 | [space_asset.py](file:///Users/netsong/Developer/i-home.life/app/models/space_asset.py) + `space_asset_service` + `app/api/space_assets.py` | 加盟方持有/代管的存量空间，天然是 `space_assets.owner_id` 的归属主体；`asset_holder`/`holder_type` 已支持外部主体 |
| 轻资产红线机制 | `platform_role` 恒 `service_provider`（schema→service→model 三层强制） | 加盟模式可直接继承该约束，防加盟方被表述为"平台持有资产" |
| 项目级协作与隔离 | `verify_project_access` / `verify_project_collaborator_access` / `owner_id` 隔离 | 加盟方数据隔离可复用现成模式（非 admin 仅见自己） |
| ATH / Agent 握手凭证 | `app/api/agent_handshake.py`、`agent_identity.py` | 加盟方 Agent 接入平台的身份互信底座 |
| 结算与托管 | `settlement_service`、`escrow_trustee`、`escrow_payments` | 加盟分润/账期可复用托管资金模型（注意：**当前仅验证不扣款，禁宣称支付闭环**） |
| 适老/套餐定价 | `QUICK_INSTALL_PACKAGES`（含 `PKG-ELDERLY-*`） | 加盟方可售 SKU 目录已有单源 |

### 2.3 建议的最小实现方向（不含代码）

1. **主体建模复用而非新建**：加盟方 = `suppliers` 扩展（`partner_type` 字段）+ 新增 `partner_agreements`（授权范围/区域/分润比例/有效期），避免再造一套主体。
2. **角色扩展**：`rbac.py` 增 `partner` 角色 + `DEFAULT_ROLE_PERMISSIONS` 条目，复用 `verify_project_collaborator_access` 的协作白名单模式。
3. **数据隔离**：加盟方仅见自己 `owner_id` 下的 `space_assets` / `projects`，沿用现成隔离范式（勿新造）。
4. **诚实边界**：分润/结算接 `escrow_trustee` 现状——**只做账目核算与意图记录，不得宣称已实际打款**。

---

## 三、模块一：3DGS 虚拟看房系统

### 3.1 实现现状（逐层核验）

| 层 | 落点 | 现状 |
|---|---|---|
| 资产上传 | [vr_panorama.py](file:///Users/netsong/Developer/i-home.life/app/api/vr_panorama.py#L83-L128) `POST /vr/panoramas/upload-splat` | ✅ 真实：`.spz/.ply/.glb`，[魔数校验](file:///Users/netsong/Developer/i-home.life/app/services/vr_panorama_service.py#L119-L137)（`NGSP`/`ply`/`glTF`）+ 64MB 上限，落 `file_service(category=gaussian_splat)`，`splat_url=/api/files/download/{id}` |
| 云端重建 | [gaussian_recon.py](file:///Users/netsong/Developer/i-home.life/app/api/gaussian_recon.py) + [gaussian_reconstruction_service.py](file:///Users/netsong/Developer/i-home.life/app/services/gaussian_reconstruction_service.py#L57-L63) | 🟡 契约就绪但**默认不可用**：`gaussian_recon_enabled=False`（config.py:685）、`gaussian_recon_backend_url=""`（:686）→ 生产恒 503（诚实报错） |
| 户型→全景渲染 | [vr_panorama_service.py](file:///Users/netsong/Developer/i-home.life/app/services/vr_panorama_service.py#L218-L252) `render_panorama` | 🔴 **mock**：返回 `render_status=not_configured` + `image_url=""`，无渲染集群 |
| 漫游渲染（前端） | [GaussianViewer.jsx](file:///Users/netsong/Developer/i-home.life/webapp/src/components/GaussianViewer.jsx#L284-L359) | ✅ 双轨：WebGPU 原生 `GaussianSplat`（three r186，SH1–SH3 + GPU 计数排序）优先，无 WebGPU 回退 `@sparkjsdev/spark`（WebGL2 GPU 排序） |
| 降级链 | GaussianViewer :362-367 / PanoramaViewer | ✅ WebGPU → WebGL2/Spark → 贴图全景 → 静态图；20s 加载超时兜底（加载器无 onError） |
| 性能优化 | GaussianViewer :121-130、:293-294 | ✅ 静止 600ms 停帧；低端设备 pixelRatio=1 + 关抗锯齿 |
| 三态内容标注 | [VirtualTour.jsx](file:///Users/netsong/Developer/i-home.life/webapp/src/pages/VirtualTour.jsx#L246-L255) | ✅ `actual/gaussian`（3D 实景）、`actual/equirectangular`（360°）、`effect`（2D 平面预览 + 显式标注"非实景"） |
| 热点与设备联动 | [vr_panorama.py](file:///Users/netsong/Developer/i-home.life/app/api/vr_panorama.py#L432-L523) `device-overlay` | ✅ `position → yaw/pitch` 球坐标换算 + 场景关联 + 最近真实传感器快照 |
| AI 换装 | `POST /vr/panoramas/{id}/restage` | ✅ 复用 ai_render 降级链，返回 `reconstruction_available=false` 诚实标注 |
| 依赖 | `webapp/package.json:13,18` | `three ^0.186.0` + `@sparkjsdev/spark ^2.1.0`（Spark 约 4.9MB，动态 import 不拖首屏） |

**已对齐的 2026 前沿**：SPZ 压缩格式、`KHR_gaussian_splatting` glTF 扩展、WebGPU 原生高斯泼溅、双轨回退、按需渲染省电。

### 3.2 与 2026 前沿的对标差距

| 前沿方向 | 本项目 | 差距 |
|---|---|---|
| 分块 LOD / 流式加载（大场景与移动端） | ❌ 整文件加载，无 LOD | 单房间 64MB 上限，多层/整栋场景不可用；弱网首屏不可控 |
| 3DGS + Mesh 混合（可碰撞/可量测） | ❌ 纯 splat | 无法做空间量测、家具摆放、施工比对 |
| 动态 4DGS / 可编辑场景 | ❌ | AI 换装仍是 2D 图，未回写 3D 场景 |
| WebXR / 头显与真 VR 沉浸 | ❌ 无 `immersive-vr`（已检索确认） | 仅平面屏拖拽，无法对接 VR 一体机 |
| 移动端手势（双指缩放/陀螺仪） | ❌ 仅滚轮改 FOV（:223-228） | **移动端无缩放手段**，触屏体验缺陷 |
| 语义标注与资产映射 | 🟡 `spatial_semantics_service` + LCC2 语义映射 sidecar（v1.15.7） | 已有侧车，但未与 3DGS 渲染层联动 |
| 真机兼容性矩阵 | ❌ 无 | 见 3.3-P1 |

### 3.3 存在问题

**P0-1｜"AI 生成看房"能力为零，但对外叙事存在落差**
`render_panorama` 为 mock（`image_url=""`），`publish_effect_render` 产物是 2D 平面图。设计 4.1「先看后装」在**实景 3DGS 之外**没有内容生产路径。前端已诚实标注（:342），但产品叙事若宣称"AI 生成 3D 看房"即违约。

**P1-1｜移动端交互缺失（影响 C 端体感）**
- 无双指 pinch 缩放，仅 `wheel`（桌面）；移动端只能改视角不能改 FOV。
- 无陀螺仪/DeviceOrientation 环视（ARScan.jsx 有 `DeviceOrientationEvent` 探测，但**未用于 3DGS 漫游**）。
- 拖拽用 `pointermove` 绑 window（:249-250），多指/手势冲突风险未处理。

**P1-2｜无真机兼容性矩阵与实测记录**
代码按 `navigator.gpu.requestAdapter()` 分流，但仓库内**无**任何 iOS Safari / Android Chrome / 鸿蒙浏览器 / 低端机型的实测结论与截图。WebGPU 在移动端与 Safari 的版本覆盖情况**需实测**（2026 各端支持度标注「需外部复核」）。`isLowEndDevice` 以 UA + `hardwareConcurrency/deviceMemory` 启发式判定，`deviceMemory` 在 Safari/Firefox 缺失（回退 8）→ 低端 iOS 会被误判为高端。

**P1-3｜前端零自动化测试**
`webapp/` 无 tests 目录；`GaussianViewer` / `PanoramaViewer` 无单测、无快照。Console 侧仅有 Playwright 视觉用例（`console-src/tests/visual/*`），不覆盖 WebApp 漫游。渲染双轨分流、降级链、超时兜底三个关键分支**全部无回归保护**。

**P2-1｜无 LOD/流式，无加载进度可见**
`onProgress` 仅触发重渲染（Spark 轨），UI 只显示"3D 场景加载中…"，无百分比；64MB 文件在弱网无体验保障。

**P2-2｜热点只能在 2D 全景上加**
`add_hotspot` 走 `panorama.hotspots` JSON；3D 漫游中热点仅**消费**不**生产**——无 3D 场景内拾取坐标写热点的工作流。

**P2-3｜`compute_scene_duration` 为 mock 估算**
`avg_hotspot_count = 2` 硬编码（`vr_panorama_service.py:405-407`），非真实热点统计，会误导叙事时长。

### 3.4 优化建议

| 优先级 | 建议 | 依据 |
|---|---|---|
| P0 | **口径修正**：对外统一为"实景 3DGS 托管 + 漫游渲染"，删除/降级一切"AI 生成 3D 看房"表述；户型生成路径明确标注"未配置渲染后端" | 诚实降级红线 |
| P1 | **移动端手势补齐**：双指 pinch → FOV；可选陀螺仪环视（iOS 需 `DeviceOrientationEvent.requestPermission`） | P1-1 |
| P1 | **真机兼容性矩阵**：iOS Safari / Android Chrome / 鸿蒙浏览器 × 高中低端，记录 WebGPU/WebGL2 分流结果、首帧耗时、内存峰值 | P1-2 |
| P1 | **前端回归**：为 GaussianViewer 补 Vitest 用例（桩 `navigator.gpu` 覆盖 4 条分支）+ Playwright 视觉用例 | P1-3 |
| P2 | **LOD/流式**：引入分块或分层 splat + 进度条；大场景按房间切块（与 `floorplan_id` 已有字段天然契合） | P2-1 |
| P2 | **3D 拾取写热点**：`Raycaster` 命中的世界坐标 → yaw/pitch 回写 `hotspots` | P2-2 |
| P2 | **时长统计去 mock**：改读真实 `hotspots` 数量 | P2-3 |

### 3.5 风险评估

| 风险 | 概率 | 影响 | 缓解 |
|---|---|---|---|
| 对外宣称"AI 生成看房"被客户/赛事质证 | 中 | 高（诚信红线） | 口径修正（P0）+ 前端标注已就位 |
| 移动端漫游不可用导致 C 端体验崩塌 | 高 | 高 | 手势补齐 + 兼容矩阵 |
| 云端重建（GPU）长期不立项 → 3DGS 只能靠外部工具 | 高 | 中 | 明确"外部采集导出"为正式路径（已有 upload-splat），重建立项另议 |
| WebGPU 分支在部分端崩溃且无回归保护 | 中 | 中 | 单测 + 超时兜底（已有）|
| Spark 4.9MB 依赖体积/许可变更 | 低 | 中 | WebGPU 原生轨已可脱离 Spark；保持双轨即可 |

### 3.6 改进措施与验收标准

| # | 措施 | 验收标准（可执行） |
|---|---|---|
| M1-1 | 全局检索并修正"AI 生成 3D/看房"表述 | `grep -ri "AI 生成.*3D\|AI 生成.*看房" webapp/ console-src/ assets/` 零命中；前端 effect 态标注文案保留 |
| M1-2 | 移动端 pinch 缩放 | 真机（iOS+Android）双指捏合 FOV 在 30°–110° 连续变化；Playwright 触摸事件用例通过 |
| M1-3 | 兼容性矩阵文档 | `docs/reports/` 新增矩阵表：≥6 组（iOS Safari / Android Chrome / 鸿蒙 / 桌面 Chrome / 桌面 Safari / 低端 Android）× 首帧耗时 + 分流轨 + 内存峰值 |
| M1-4 | 前端渲染分支回归 | 新增 GaussianViewer 单测 ≥4 例（无 WebGL2 → fallback；无 WebGPU → Spark；WebGPU 成功 → ready；加载超时 → fallback），`npm test` 通过 |
| M1-5 | 加载进度可见 | Spark 轨显示百分比；超时文案明确 |
| M1-6 | 时长去 mock | `compute_scene_duration` 单测断言随真实热点数线性变化 |

---

## 四、模块二：智能家居集成方案

### 4.1 实现现状（逐层核验）

| 层 | 落点 | 现状 |
|---|---|---|
| 生态桥（5 个） | [ecosystem_bridge.py](file:///Users/netsong/Developer/i-home.life/app/services/ecosystem_bridge.py) | 🟡 **仅米家真机化**（:174-415，云登录 + `python-miio` 清单/状态/控制）；HomeKit(:120-171)、鸿蒙(:418-467)、Matter(:470-614)、涂鸦(:617-677) **全 stub**（`NotImplementedError`） |
| 连接池 | `BridgeConnectionPool`（:733-775） | ✅ 场景级复用 + 并发建连互斥 + stub 桥静默归还 |
| 命令执行 | [execute_device_command](file:///Users/netsong/Developer/i-home.life/app/services/scene_automation_service.py#L956-L1084) | 🔴 **凭据断链**（见 P0-2）；超时 10s + 重试 1 次（:41-66）；成功才写 `state`（:1037-1047，诚实） |
| 场景执行 | `_plan_scene_actions`（:1087）+ `_run_scene_action`（:1144）+ `execute_scene_actions`（:1209） | 🟡 波次并行编排优秀；但 ecosystem 恒为 matter → 全 pending（见 P0-3） |
| 传感器触发 | [check_sensor_triggers](file:///Users/netsong/Developer/i-home.life/app/services/scene_automation_service.py#L716-L832) | 🔴 只写日志 + 恒 `pending`（:800-822），**不执行动作** |
| 异步命令 | `execute_async=True` + BackgroundTasks + WS 回填 | ✅ 已落地（:357-387） |
| 并发保护 | `_device_lock`（:74-85） | 🟡 进程内锁，多 worker 不共享（已诚实标注） |
| 数据校验 | `SensorSnapshotRequest` 范围约束 / `HealthMonitorCreate` 枚举 | ✅（2026-08-27 加固） |
| 凭据加密 | [device_credentials.py](file:///Users/netsong/Developer/i-home.life/app/services/device_credentials.py) AES-256-GCM | 🟡 **仅 Matter 凭据加密**（`smart_home.py:759-760`）；生态桥凭据明文（见 P1-4） |
| 限流 | `POST /sensors/snapshot` per-user 30/min | ✅ 进程内，多 worker 不共享（已标示） |
| 穿戴 BLE | `flutter_blue_plus` + `wearable_ble_service.dart` | 🟡 代码就绪，**需真机验证** |
| 可观测性 | `device_command_total/duration`、`scene_execute_*`、`sensor_snapshot_upload_total` | ✅ |

### 4.2 存在问题

**P0-2｜设备命令/场景执行路径无凭据注入 → 米家真机代码不可达**
[scene_automation_service.py:1025-1027](file:///Users/netsong/Developer/i-home.life/app/services/scene_automation_service.py#L1025-L1027) 与 [:1165-1167](file:///Users/netsong/Developer/i-home.life/app/services/scene_automation_service.py#L1165-L1167)：

```python
bridge = await asyncio.wait_for(pool.get(ecosystem), timeout=...)
```

`pool.get(ecosystem)` 第二参 `credentials` 缺省为 `None` → `bridge.connect({})` → 米家 [:216-222](file:///Users/netsong/Developer/i-home.life/app/services/ecosystem_bridge.py#L216-L222) 抛 `ValueError("米家连接需要 username 和 password")` → 被 [:1048-1054](file:///Users/netsong/Developer/i-home.life/app/services/scene_automation_service.py#L1048-L1054) 捕获 → `action_status="pending"`。

**全仓 grep 确认**：`pool.get(` 仅 2 处（:1026、:1166），**均不传凭据**；唯一传凭据的路径是 `sync_to_ecosystem`（[:553-555](file:///Users/netsong/Developer/i-home.life/app/services/scene_automation_service.py#L553-L555) 用 `eco.config`），而它只做 `sync_scenes`——米家 `sync_scenes` 本身也是 `NotImplementedError`（:409-415）。

⇒ **结论：v1.15.x/v1.16 声称的"米家真机化"在运行期不可达，设备控制业务能力实际为零。** 诚实标注到位（不伪装成功），但文档表述[device-link-hardening-20260827.md](file:///Users/netsong/Developer/i-home.life/docs/reports/device-link-hardening-20260827.md) 未披露该断链。

**P0-3｜场景执行 ecosystem 恒为 `matter`（stub）**
[:1160](file:///Users/netsong/Developer/i-home.life/app/services/scene_automation_service.py#L1160)：`ecosystem = getattr(scene, "ecosystem", None) or "matter"`。
而 `SceneAutomation` 模型（[models/scene_automation.py:12-39](file:///Users/netsong/Developer/i-home.life/app/models/scene_automation.py#L12-L39)）**无 `ecosystem` 列** → 恒走 Matter 桥 → 恒 `NotImplementedError` → 所有场景动作恒 `pending`。设备命令端点则由请求体 `data.ecosystem` 传入（可指定 mijia），两条路径行为不一致。

**P0-4｜传感器触发到执行断链**
`check_sensor_triggers` 命中后只写 `SceneBehaviorLog` + 返回 `action_status="pending"`（[:800-822](file:///Users/netsong/Developer/i-home.life/app/services/scene_automation_service.py#L800-L822)），**从不调用** `execute_scene_actions`。即"温度>30 开空调"这类核心卖点在代码层不成立。同时其 `action_note` 文案仍是"当前未配置 API key"（早于米家接入），与实际状态已脱节。

**P1-4｜生态桥凭据明文落库**
`EcosystemIntegration.config` 为 JSON 列（[models/scene_automation.py:55](file:///Users/netsong/Developer/i-home.life/app/models/scene_automation.py#L55)），经 `POST /scene-automation/ecosystems` 原样写入（[api/scene_automation.py:271](file:///Users/netsong/Developer/i-home.life/app/api/scene_automation.py#L271)），且直接作为 `bridge.connect(creds)` 的凭据。全仓 `encrypt_device_credentials` 仅 2 处调用（均 Matter）。⇒ 米家账号密码、涂鸦 AccessSecret 等**明文入库**，与 Matter 凭据加密策略不一致。

**P1-5｜Matter 配网端点恒 501，落库代码不可达**
[smart_home.py:723-739](file:///Users/netsong/Developer/i-home.life/app/api/smart_home.py#L723-L739)：`commission_device` 恒抛 `NotImplementedError` → 501；其后的 `MatterDevice` 落库（:741-764）与刚做好的凭据加密**永不执行**。`matter_enabled=True` 默认开启（config.py:612）会让用户以为可用。

**P1-6｜多 worker 一致性**
`_device_lock`、per-user 限流、WS 广播均为进程内（已诚实标注）。uvicorn 4 workers 下锁失效、WS 广播跨进程不可达。

**P2-4｜协议与设备类型覆盖**
`smart_devices.device_type` 16 类、`protocol` 白名单 5 值；Matter 设备类型表 24 项（`MATTER_DEVICE_TYPES`）——均为**静态知识层**，无真实协议栈。

### 4.3 优化建议

| 优先级 | 建议 | 依据 |
|---|---|---|
| P0 | **打通凭据通道**：`pool.get(ecosystem, credentials)` 从 `EcosystemIntegration`（解密后）取；`execute_device_command` / `_run_scene_action` 增加 ecosystem 解析来源 | P0-2 |
| P0 | **修场景 ecosystem 来源**：`SceneAutomation` 增 `ecosystem` 列（迁移同步）或在 `SmartHomeScheme` 层解析，去掉硬编码 `or "matter"` | P0-3 |
| P0 | **传感器触发接执行**：命中后复用 `execute_scene_actions`（含波次与锁），失败诚实标注；同步修正过时的 `action_note` 文案 | P0-4 |
| P1 | **凭据加密统一**：`EcosystemIntegration.config` 复用 `device_credentials`（AES-256-GCM），读取侧解密；迁移需处理存量明文 | P1-4 |
| P1 | **Matter 端点诚实化**：`matter_enabled=True` 但桥未实现时，端点返回 501 的同时在响应/文档标注"桥未就绪"，避免默认开启误导；或按 flag 与桥可用性联合判定 | P1-5 |
| P1 | **更新加固文档**：在 `device-link-hardening-20260827.md` 补齐"凭据断链"事实，避免读者误判能力已通 | 证据纪律 |
| P2 | **多 worker 一致性**：设备锁改 DB 乐观锁；WS 广播接 Redis pub/sub（不引入 K8s，Redis 属可用增量） | P1-6 |
| P2 | **真机验证清单**：米家（云清单+同网段控制）、BLE（Android/iOS）各出实测记录 | 需实测项 |

### 4.4 风险评估

| 风险 | 概率 | 影响 | 缓解 |
|---|---|---|---|
| 演示/交付时"控制设备"失败（pending） | **极高** | **高** | P0-2/P0-3 修复；未修前演示口径必须标注"未接真机" |
| 生态凭据明文入库泄露 | 中 | **高** | P1-4 加密 + 迁移 |
| Matter 默认开启诱导用户尝试 → 501 | 高 | 中 | P1-5 |
| 传感器触发不执行 → 核心卖点不成立 | **已发生** | 高 | P0-4 |
| 多 worker 状态错乱（并发命令） | 中 | 中 | P2 乐观锁 |
| 真机未验证即对外宣称支持某生态 | 中 | 高 | 仅米家可宣称，且标注"同网段"限制 |

### 4.5 改进措施与验收标准

| # | 措施 | 验收标准（可执行） |
|---|---|---|
| M2-1 | 命令/场景执行注入桥凭据 | 新增测试：mock `EcosystemIntegration(config={...})` → `execute_device_command` 断言 `bridge.connect` 收到凭据；无凭据时仍 `pending` 不崩溃 |
| M2-2 | 场景 ecosystem 显式化 | `SceneAutomation.ecosystem` 列 + 迁移；`_run_scene_action` 单测断言使用场景配置值而非 `"matter"`；`alembic upgrade head && downgrade -1 && upgrade head` 幂等 |
| M2-3 | 传感器触发执行闭环 | 新增测试：命中 sensor 场景 → 断言 `execute_scene_actions` 被调用、动作进入 plan；`action_status` 非硬编码 pending |
| M2-4 | 生态凭据加密 | `POST /ecosystems` 落库值为 `{"encrypted": b64}`；读取侧解密成功；存量明文迁移脚本（幂等）验证 |
| M2-5 | Matter 诚实化 | bridge 未就绪 + `matter_enabled=True` 时响应体含 `bridge_ready: false` 且文档同步；501 保持 |
| M2-6 | 文档同步 | `device-link-hardening-20260827.md` 与本文结论一致，无"米家控制已可用"式误导 |
| M2-7 | 真机验证 | 米家：云清单拉取成功 + 同网段 `turn_on` 返回 `success` 且有 `state` 回写；BLE：Android/iOS 各一次心率订阅成功截图/日志 |

---

## 五、跨模块共性风险

| # | 风险 | 事实 | 影响 |
|---|---|---|---|
| X1 | **121 项改动未提交**（v1.16.0 + v1.17.0 两个完整版本，最后提交 2026-09-12，已 10 天） | `git status --porcelain` = 121 | 任意外部 `checkout/stash/reset` 即抹除；评审/复现不可信 |
| X2 | **测试基线数字错误** | `scripts/test_baseline.json` 记 `passed=2768`，而 collect 仅 2766（物理不可能）；上一轮全量实测 2760 passed / 2 skipped / 4 xfailed | 门禁 `check_test_baseline.py` 未接入 CI，一旦接入会误报回退；数字不可信 |
| X3 | **前端零自动化测试**（webapp） | 无 tests 目录 | 3DGS 渲染分支与智能家居面板均无回归保护 |
| X4 | **诚实降级文档与代码不同步** | 加固文档未记 P0-2 断链 | 内部决策基于错误能力判断 |

> **状态更新（2026-09-23）**：X2 已于 2026-09-23 处理 —— `scripts/test_baseline.json` 校准至 2780（collect 2786），并已接入 CI `backend-test` 的 "Check pytest baseline" 步骤（`--from-output pytest-ci.log` 复用同一份全量日志，不重复跑）。
>
> **状态更新（2026-09-23，CI 补口）**：控制台视觉回归（`console-src/tests/visual/*`，248 用例）已接入 CI 新 job `console-visual`（ubuntu + Playwright chromium + `vite preview`）。因仓库基线仅含 `*-darwin.png`，job 暂设 `continue-on-error: true`（非阻塞），Linux 基线经 `gh workflow run ci.yml -f update_snapshots=true` 引导后转阻塞并纳入 `deploy.needs`。

---

## 六、优先级路线图

**P0（阻断交付口径，先做）**
1. X1 提交 121 项改动（按 v1.16.0 / v1.17.0 分两个 commit，保留可回溯）
2. X2 校准 `test_baseline.json` → 2760，并接入 CI 门禁
3. M2-1 / M2-2 / M2-3 智能家居凭据与触发闭环（含测试）
4. M1-1 3DGS 对外口径修正

**P1（能力可用性与安全）**
5. M2-4 生态凭据加密 + 存量迁移
6. M2-5 Matter 诚实化 + M2-6 文档同步
7. M1-2 移动端手势、M1-3 兼容性矩阵、M1-4 前端渲染回归

**P2（体验与深度）**
8. M1-5 加载进度、M1-6 时长去 mock、LOD/流式、3D 拾取写热点
9. M2-7 真机验证记录、M2 多 worker 一致性（DB 乐观锁 / Redis pub-sub）
10. 合作方加盟模块立项：复用 §2.2 资产，按 §2.3 最小实现落地

---

## 七、诚实边界声明

- 本报告未执行全量回归，测试结论引用上一轮实测（2760 passed）；P0 修复后须重跑全量并同步 `test_baseline.json`。
- 3DGS 真机渲染质量、交互流畅度（帧率/功耗）、设备兼容性**均未经实测**，本文仅确认代码路径存在与分支覆盖，不构成"体验达标"结论。
- 智能家居仅米家桥有真机代码；Matter/HomeKit/涂鸦/鸿蒙为 stub，**不得对外宣称支持**。
- 涉及 2026 外部标准（Matter 版本品类、WebGPU 各端支持度、SPZ/glTF 扩展演进）条目标注「需外部复核」，落地前须以外网最新规范为准。
- 平台**不做医疗诊断/疗效承诺**；康养/适老相关表述须过 `health_claim_compliance` 词表。
- 架构红线不变：不引入 K8s/Helm，鉴权 PASETO（非 JWT），禁止硬编码假数据伪装能力。

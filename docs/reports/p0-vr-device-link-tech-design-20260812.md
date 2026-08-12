# P0 路径技术实现方案：720° 漫游 × 设备热点联动（含 GS 开源调研 + 展厅模块研究）

> 日期：2026-08-12
> 依据：`docs/reports/glassesfree3d-vr-smarthome-feasibility-20260812.md`（P0 路径细化）
> 范围：前端组件改造 / 后端 API 设计 / 触发伪代码 / Gaussian Splatting 开源调研 / 效果图漫游与智能展厅

---

## 第 1 部分 · P0 技术实现方案（720° 漫游 × 设备热点联动）

### 1.1 现状与缺口

| 项 | 现状 | 缺口 |
|---|---|---|
| 全景漫游 | webapp `PanoramaViewer.jsx`（Three.js 360° + 热点 Sprite + 低配降级）+ `VirtualTour.jsx` + `/api/vr/*` | 热点仅支持房间跳转/外链，**不承载设备** |
| 智能设备 | `SmartDevice`（含 position_x/y/z）+ `/api/smart-home/*`（仅 CRUD + Matter 配网） | **无设备控制执行端点**（turn_on 等） |
| 场景自动化 | `/api/scene-automation/*`：create/parse/simulate/validate/sync | **无 execute 端点**（simulate 不实际触发） |
| 状态数据 | `SensorSnapshot` 真实落库（2026-08-12 已修复）+ `SceneBehaviorLog` | 无面向 3D 图层的聚合查询 |
| 实时推送 | `ws_manager.broadcast_to_project`（既有） | 无设备状态事件类型 |

### 1.2 前端组件改造（webapp）

新增 3 个组件 + 改造 1 个：

**① 改造 `PanoramaViewer.jsx` — 新增 `devices` prop**

```jsx
// 新增 props
devices: Array<{
  deviceId: string
  name: string
  type: string            // light/curtain/speaker/sensor/camera/lock...
  yaw: number, pitch: number   // 球面坐标（与现有 hotspot 一致）
  status: 'online' | 'offline'
  state?: { power?: boolean; brightness?: number; temperature?: number; ... }
  sceneIds: string[]      // 关联的 SceneAutomation id（点击可触发）
}>
onDeviceClick(device, action)   // action: 'toggle' | 'scene'
```

- 设备以 `THREE.Sprite` 渲染（复用热点机制），状态用颜色编码：在线常亮 / 离线灰 / 触发中闪烁
- 渲染时按 `status/state` 刷新（`WebSocket` 收到 `smart.device.state` 事件后局部更新）

**② 新增 `DeviceCommandPanel.jsx`** — 点击设备热点弹出控制面板：
- 设备信息卡 + 状态实时值（来自聚合层）
- 动作按钮（按 `DEVICE_ACTION_WHITELIST` 渲染：开关/调光/开合帘/音量…）
- 关联场景快捷触发（回家/观影/睡眠模式一键）

**③ 新增 `SceneTriggerOverlay.jsx`** — 场景状态在 3D 中的高亮层：
- 场景触发后，相关设备热点进入「联动高亮」动画
- 展示最近 `SceneBehaviorLog` 的 `action_status`（pending/success）

**④ 新增 `StateSyncHook.js`（React hook）** — WebSocket 订阅：

```js
// ws_manager 已存在，扩展事件类型即可
ws.on('smart.device.state', ({ deviceId, state }) => updateDeviceState(deviceId, state))
ws.on('scene.triggered',     ({ sceneId, actionStatus }) => highlightScene(sceneId, actionStatus))
```

降级纪律：WebSocket 不可用时退化为 `GET /device-overlay` 轮询（30s），与项目 4 级降级链一致。

### 1.3 后端 API 设计（新增 3 端点，均走现有鉴权/RBAC）

**① `POST /api/smart-home/devices/{device_id}/command` — 设备命令（3D 场景控制入口）**

```jsonc
// Request
{
  "action": "turn_on",               // 对齐 DEVICE_ACTION_WHITELIST
  "params": { "brightness": 80 },
  "source": "vr_overlay",            // 可观测性：vr_overlay / voice / app
  "scene_id": "可选，关联场景"          // 手动触发场景时携带
}
// Response 200
{
  "device_id": "...", "action": "turn_on", "accepted": true,
  "action_status": "pending",        // 诚实降级：生态桥未接真机前恒 pending
  "note": "设备动作执行依赖生态桥接（ecosystem_bridge），已记录触发意图"
}
```

- 实现：校验设备归属 → `validate_actions` 白名单校验（复用现有）→ 写 `SceneBehaviorLog(action_type="device_command", ambient_data=最近真实 SensorSnapshot)` → 生态桥执行（`EcosystemBridge`，未实现时 `action_status=pending` 诚实标注）→ WS 广播

**② `POST /api/scene-automation/scenes/{scene_id}/execute` — 场景执行**

```jsonc
// Request  { "trigger_source": "vr_overlay" | "voice" }
// Response 200
{
  "scene_id": "...", "executed": true,
  "actions": [{ "device_id": "...", "action": "turn_on", "action_status": "pending" }],
  "triggered_at": "2026-08-12T16:00:00+08:00"
}
```

- 实现：加载场景 → `validate_scene`（复用）→ 逐动作 `validate_actions` → 全部写 `SceneBehaviorLog(action_type="manual_trigger")` → 生态桥逐个执行 → WS 广播 `scene.triggered`
- 与传感器触发（`check_sensor_triggers`）共用同一执行管线，保证两入口行为一致

**③ `GET /api/vr/projects/{project_id}/device-overlay` — 3D 设备图层聚合**

```jsonc
// Response 200
{
  "panorama_id": "可选", 
  "devices": [{
    "device_id": "...", "name": "客厅灯", "type": "light",
    "yaw": 120.5, "pitch": -8.0,        // 由 SmartDevice.position 换算或配置
    "status": "online",
    "state": { "power": true, "brightness": 80 },
    "scene_ids": ["scene-1", "scene-2"]  // 关联可触发场景
  }],
  "latest_sensor": {                     // 最近真实 SensorSnapshot（供联动上下文）
    "snapshot_id": "...", "temperature": 30.5, "humidity": 55.0, "sampled_at": "..."
  }
}
```

- 实现：查询项目下 `SmartDevice`（position 非空者优先）→ 关联 `SceneAutomation` → 关联最近 `SensorSnapshot`；`position → yaw/pitch` 用球坐标换算（0=正北，与 PanoramaViewer hotspot 约定一致）

### 1.4 数据流（一次「漫游即控制」完整闭环）

```
VirtualTour(3D场景) → 点击设备热点(灯) → DeviceCommandPanel
  → POST /api/smart-home/devices/{id}/command {action:"turn_off", source:"vr_overlay"}
  → [后端] 校验归属/白名单 → SceneBehaviorLog(action_type=device_command)
  → [后端] EcosystemBridge.turn_off() → 未接真机 → action_status=pending（诚实）
  → WS 广播 smart.device.state → StateSyncHook → 3D 热点熄灭/置灰
```

---

## 第 2 部分 · 点击/语音触发场景自动化：伪代码流程

### 2.1 数据模型映射

| 3D 场景元素 | 映射到现有模型 |
|---|---|
| 设备热点 `{deviceId, yaw, pitch}` | `SmartDevice.id` + `position_x/y/z` |
| 热点上的「一键场景」 | `SceneAutomation`（scene_id 列表） |
| 触发时的环境上下文 | 最近 `SensorSnapshot`（真实落库数据） |
| 触发记录 | `SceneBehaviorLog`（action_type 区分来源） |

### 2.2 伪代码

```python
# ================= 前端（webapp）=================
# onDeviceClick(device, action)
async function onDeviceAction(device, action) {
  if (action == 'scene') {
    # 场景一键触发：携带当前 3D 视角上下文
    resp = POST `/api/scene-automation/scenes/${device.sceneIds[0]}/execute`
      { trigger_source: 'vr_overlay' }
  } else {
    # 单设备命令
    resp = POST `/api/smart-home/devices/${device.deviceId}/command`
      { action: action, params: params, source: 'vr_overlay' }
  }
  if (resp.ok):
    notify(3D overlay, resp.action_status)   # pending → 热点闪烁等待
  else:
    notify(3D overlay, '执行失败', resp.detail)
}

# ================= 后端（FastAPI）=================
# POST /api/scene-automation/scenes/{scene_id}/execute
async def execute_scene(scene_id, trigger_source, db, user):
    scene = load(SceneAutomation, scene_id)            # 归属校验 via RBAC
    check = await validate_scene(db, scene)            # 复用触发/动作白名单校验
    if not check.valid: return 422(check.errors)

    # 触发上下文：取用户最近真实 SensorSnapshot 作为 ambient_data（诚实数据）
    ambient = latest_sensor_snapshot(db, user_id)      # SensorSnapshot 真实落库
    ambient_ctx = { 'temperature': ambient.temperature,
                    'humidity':    ambient.humidity,
                    'light_lux':   ambient.light_lux } if ambient else {}

    results = []
    for act in scene.actions:                          # 逐动作执行
        log = SceneBehaviorLog(
            project_id=scene.project_id, user_id=user.id,
            action_type='manual_trigger',              # 来源：手动(3D/语音)
            scene_id=scene.id,
            device_id=act.get('device_id'),
            ambient_data=ambient_ctx)                  # 关联真实传感器数据
        db.add(log)

        bridge = EcosystemBridge.get(scene.ecosystem) # HomeKit/Matter/米家...
        try:
            await bridge.execute_device(act)           # 真机执行
            status = 'success'
        except NotImplementedError:
            status = 'pending'                          # 诚实降级，不伪装已执行
        results.append({**act, 'action_status': status})

    await db.commit()
    await ws.broadcast('scene.triggered', {scene_id, results})   # 3D 高亮
    return {'scene_id': scene_id, 'executed': True, 'actions': results}

# ================= 复用（零新增逻辑）=================
# _match_sensor_condition / check_sensor_triggers —— 传感器自动触发共用
# validate_actions / DEVICE_ACTION_WHITELIST —— 动作合法性校验共用
```

**关键设计**：手动触发（3D/语音）与传感器自动触发（`check_sensor_triggers`）**共用** `SceneBehaviorLog` + 生态桥执行 + 诚实 pending 标注，仅 `action_type`（`manual_trigger` vs `sensor_trigger`）与 `trigger_source` 不同——保证两条链路行为一致、可审计。

---

## 第 3 部分 · Gaussian Splatting 开源库调研（可集成 Three.js）

### 3.1 库对比

| 库 | 维护状态 | Three.js 集成 | 格式 | 关键特性 | 适用度 |
|---|---|---|---|---|---|
| **[Spark](https://github.com/sparkjsdev/spark)（World Labs 支持）** | ✅ 活跃（作者推荐） | **原生**（SplatMesh 继承 THREE.Object3D，drop-in） | .ply/.spz/.splat/.ksplat | 多对象渲染/正确排序、WebGL2（98% 设备）、LoD 系统、Dyno 可编程、WebXR/移动端优化 | ⭐ 首选 |
| **mkkellogg/GaussianSplats3D** | ⚠️ 已停止积极维护（官方推荐 Spark） | DropInViewer 模式（THREE.Group 子类） | .ply/.splat/.ksplat | 生态成熟、文档多、示例全 | 次选（存量复用） |
| gs3d-loader (wangyoumo) | 一般（2025-09 更新） | 基于 GaussianSplats3D 封装 | .splat/.ksplat | 行为盒子配置 | 辅助 |
| antimatter15/splat | 维护一般 | 独立 WebGL | .splat | 早期参考实现 | 参考 |
| cvlab-epfl/gaussian-splatting-web | 维护一般 | **WebGPU** | .ply | WebGPU 渲染管线 | 预研 |
| **Kairos-HomeWorld**（AI 全屋生成，2026-06 开源） | ✅ 活跃 | 独立（供仿真/训练） | 场景生成 | 单 prompt 全屋可交互 3D + 30 万真实户型 + 5 万交互资产 | AI 生成层 |

### 3.2 集成路径建议

1. **首选 Spark**：`SplatMesh` 直接 `scene.add()` 进现有 Three.js 场景，与 PanoramaViewer 的全景球体可共存（Spark 多对象渲染 + 正确遮挡排序），WebGL2 覆盖 98% 设备，与项目低配降级纪律兼容。
2. **双轨降级**：`Spark(WebGL2/GS) → PanoramaViewer(贴图全景) → 静态图`，延续项目 4 级降级链。
3. **采集与生成**：
   - 实景：手机/LiDAR 采集 → PLY → Spark 加载（或 INRI 官方 CUDA 管线离线上云，前端只消费 .splat/.spz）
   - AI 生成：接 Kairos-HomeWorld（自建推理）或托管 API（2D 效果图 → 3D 场景），生成结果转 .spz 进 Spark。
4. **设备锚点叠加**：Spark 场景中照常叠加 Three.js 设备 Sprite（与 P0 热点机制同一套坐标换算）。

### 3.3 技术预研更新（2026-08-12，Spark 2.1.0）

- **npm 包确认**：`@sparkjsdev/spark` v2.1.0（2026-04-18，World Labs 维护，MIT），`npm install @sparkjsdev/spark` 即用（自带 Rust→Wasm 核心）。
- **three 版本要求**：**r179+**。webapp 当前 `three ^0.185.1` 满足 ✓（与 PanoramaViewer 同一依赖，无冲突）。
- **⚠️ 2.0 breaking change（文档 3.2 示例 API 已过时，实施须按此）**：
  - 必须**显式创建 `SparkRenderer({ renderer })` 并 `scene.add(spark)`**——0.1 的自动注入已移除（曾导致场景内多个 renderer）。
  - 多视口用多个 `SparkRenderer` 实例（替代 `spark.newViewpoint()`）。
  - 新增 `.rad` 格式（列式存储 + 分块随机访问，支持渐进式流式加载超大场景）；格式支持扩至 .ply/.spz/.splat/.ksplat/.sog/.rad。
  - LoD 系统：`new SplatMesh({ lod: true })` + `SplatMesh.createLodSplats` / `enableLod`；`SplatPager` 虚拟分页预分配 GPU 缓冲；超大场景流式（`ReadableStream` 支持多 GB 文件）。
  - AR/VR：`SparkXr` 包装器（替代旧 `VRButton`）。
- **集成要点**：`SplatMesh({ url })` 即 THREE.Object3D 子类，可 `scene.add` 并与 P0 设备 Sprite（yaw/pitch 换算）共存；加载失败/无 WebGL2 时按 3.2 降级链回退 PanoramaViewer。
- **结论**：技术选型成立，M3 可立项（组件基石 = `GaussianViewer.jsx`：SparkRenderer + SplatMesh + WebGL2 检测 + 双轨降级 + 设备锚点叠加，待内容管线提供 .spz 资源）。

---

## 第 4 部分 · 效果图漫游体验 + 生态供应链/服务商智能展厅模块研究

### 4.1 效果图漫游体验（设计方案「先看后装」）

**目标**：把「AI 效果图」从静态图升级为可漫游 3D 空间，用户可在未施工前「走进去看」。

- **内容管线**：`ai_render`（ControlNet 效果图）→ 深度估计/AI 重建（DepthForge 类工具 2D→3D，或 Kairos 户型生成）→ `.spz` → Spark 渲染
- **漫游交互**：效果图房间间通过场景热点跳转（复用 `/api/vr/scenes` 组合）；家具/设备可点击查看规格、报价（关联 `Product`/`Materials`）
- **与智能家居联动**：效果图空间内即展示智能设备点位（`SmartDevice` 推荐点位），点击预演场景效果（回家/观影灯光氛围在效果图空间中的模拟）
- **前端落地**：复用 P0 的 `DeviceCommandPanel`/`SceneTriggerOverlay`，效果图漫游与实景漫游共享同一套组件（内容源不同而已）

### 4.2 生态供应链智能展厅（B2B 漫游体验）

**目标**：把「供应商/材料库」变成可漫游的 3D 展厅，赋能采购决策。

- **展厅空间**：材料展厅（瓷砖/地板/涂料/智能设备分类分区）以 3D 场景组织（`VRPanorama` 或 Spark 实景），展品即热点
- **展品联动**：点击展品热点 → 打开 `Product` 详情（价格/库存/环保认证 `MaterialEcoCert`）→ 一键加入 BOM（复用 `BOMItem`/`procurement` 链路）
- **与生态供应链联动**：
  - 供应商实景展厅（车间/样品间）→ 采购商线上漫游验厂，降低差旅
  - 智能设备展区与 `SmartDevice` 推荐联动——选中的设备直接进智能方案点位
- **数据诚实**：供应商入驻/认证状态（`Supplier.is_verified`）在展厅标注，未认证展厅显示 `pending` 水印

### 4.3 服务商智能展厅（装企/工程队作品集漫游）

**目标**：把「工程队/装企口碑」变成可漫游的作品集，赋能找队/接单。

- **作品集 3D 化**：已交付项目（含 `VRPanorama` 实景）组成装企展厅，按风格/户型/价格筛选
- **服务商联动**：展厅接入 `ConstructionCrew`/`ServiceWorker` 能力标签（资质/评分/案例数），用户漫游后直接发起接单（复用 `/api/crews/*` 匹配链路）
- **装修过程透明**：展厅展示项目施工进度（`ConstructionTask`）+ 质检（`QualityAssessment`）时间线，与 3D 场景阶段对应
- **商业模式**：服务商付费展厅（作品集置顶/VR 实拍权益），平台抽佣；复用现有 `content_publish`/`points` 体系

### 4.4 三个模块的复用矩阵

| 模块 | 复用 P0 组件 | 复用后端 API | 新增能力 |
|---|---|---|---|
| 效果图漫游 | PanoramaViewer + DeviceOverlay | /api/vr/* + /api/ai-render | 2D→3D 内容管线 |
| 供应链展厅 | PanoramaViewer + Hotspot(展品) | /api/products/* + /api/vr/* | 展品热点→BOM 闭环 |
| 服务商展厅 | PanoramaViewer + 场景组合 | /api/crews/* + /api/vr/* | 作品集→接单闭环 |

---

## 附：实施顺序建议（滚动交付）

1. **M1**：后端 3 端点（device-command / scene-execute / device-overlay）+ WS 事件 → 可独立测试
2. **M2**：前端 DeviceCommandPanel + StateSyncHook → 实景全景漫游「漫游即控制」可用
3. **M3**：Spark 集成（效果图/实景 GS 漫游，WebGL2 降级链）
4. **M4**：供应链/服务商展厅（复用 1-3 全部组件，内容与商业模式差异）

## 落地状态（2026-08-12 更新）

- ✅ **M1 已完成**：后端 3 端点全部实现（`smart_home.py` device-command / `scene_automation.py` scene-execute / `vr_panorama.py` device-overlay）+ `scene_automation_service` 执行管线（`execute_device_command` / `execute_scene_actions`，与传感器触发共用语义）+ WS 事件（`smart.device.state` / `scene.triggered`）+ 23 个集成测试（`tests/test_device_overlay.py`，含 WS 端到端闭环：connected → smart.device.state → scene.triggered，验证 1.4 数据流真实可达）
- ✅ **M2 已完成**：`PanoramaViewer` 新增 `devices` prop（设备 Sprite 状态色编码 + 点击回调，轮询刷新不重建场景）+ `DeviceCommandPanel`（动作按钮 + 一键场景 + pending 诚实提示）+ `useDeviceOverlay` hook（30s 轮询）+ `VirtualTour` 接入「漫游即控制」
- ✅ **state 补齐（2026-08-12 评估后）**：`SmartDevice` 新增 `state` JSON 列（迁移 `d1e2f3a4b5c6`）——生态桥真机执行成功（`send_command` 返回 ok）时写入（turn_on→power、set_brightness→brightness、open/close→position 等动作语义映射），pending 不写（诚实不伪造）；device-command 响应 / `smart.device.state` WS 事件 / device-overlay 均返回 `state`；`DeviceCommandPanel` 展示状态实时值。另修复 `useDeviceOverlay` 字段名不一致缺陷（后端 snake_case → 前端契约 camelCase，此前 `device.deviceId`/`sceneIds` 为 undefined，设备命令无法下发）
- ✅ **联动动画增强（2026-08-12）**：设备热点「触发中闪烁」+「场景联动高亮」已落地——`useDeviceOverlay` 管理激活/高亮状态（命令下发或场景触发后 2.5s 动画窗口），`PanoramaViewer` 设备 Sprite 激活橙色 + 脉冲放大动画（rAF 驱动，适配按需渲染省电路径）；新增 `SceneTriggerOverlay` 浮层展示最近场景执行结果（action_status 诚实标注 + 动作成功计数）
- ✅ **WS 推送接入（2026-08-12）**：`StateSyncHook` 落地为 `useProjectSocket`（`/ws/{project_id}?token=` PASETO 认证，心跳 ping/pong 保活，断线指数退避重连）+ `useDeviceOverlay` 订阅 `smart.device.state`（真机状态实时更新 + 热点闪烁）与 `scene.triggered`（联动高亮 + SceneTriggerOverlay 浮层）；**降级纪律**：WS 未连接时自动退回 30s 轮询兜底，推送恢复即停止轮询。Nginx `/ws/`（Upgrade 反代）与 Vite dev proxy 均已就绪
- ✅ **M3 组件基石（2026-08-12 落地）**：`GaussianViewer.jsx`——`@sparkjsdev/spark` v2.1.0（动态导入独立 chunk，gzip 1.75MB 按需加载）+ `SparkRenderer`/`SplatMesh` 渲染 .spz/.ply + WebGL2 检测 + **双轨降级**（无 WebGL2 / Spark 加载失败 / 资源 20s 超时 → `onFallback` 回退 PanoramaViewer 贴图全景）+ 设备 Sprite 锚点叠加（复用 P0 yaw/pitch 换算）+ **场景热点跳转**（★ Sprite，房间间漫游，复用 P0 热点机制）+ 按需渲染省电；`VirtualTour` 接入（`pano.splat_url` 存在即 GS 渲染）；后端 `VRPanorama.splat_url` 列（迁移 `a1b2c3d4e5f7`）为 3DGS 内容入口，`VRPanoramaCreate/Update/Response/ListItem` schema 透传。内容管线（实景采集/LiDAR→.spz、Kairos AI 生成）待后续立项
- ✅ **可观测性增强（2026-08-12）**：执行管线全状态流转日志——`device_command_received/rejected/context/bridge_dispatch/executed`、`scene_execute_start/devices/action_dispatch/action_skipped/action_rejected/action_bridge/action_result/done(含 status_summary)`，命令下发（connect→send_command→result）与 pending→success/failed 流转全程可排查
- ✅ **M4 智能展厅最小原型（2026-08-12 落地）**：`ShowroomPage.jsx`（路由 /showroom + Shell 导航）——展厅 = 项目 VRPanorama（复用 PanoramaViewer 漫游），**展品即热点**（`HotspotCreate/Spec` 新增 `material_id`，type=exhibit）；点击展品 → Material 详情（价格/品牌/规格 + 环保认证 `/api/eco-materials/certs`）→ **一键加入 BOM**（复用 `POST /api/materials/bom` 链路）。**诚实标注**：设计 4.2 的 `Supplier.is_verified` 认证状态未落地（`Supplier` 模型无该字段，不伪造，待模型落地后补）
- ⏳ **M4 余项**：供应商实景展厅（验厂漫游）、服务商作品集展厅（4.3）、`Supplier.is_verified` 认证状态模型
- ⏳ **M3 余项**：3DGS 内容管线（采集/AI 生成 → .spz，见第 4 部分 4.1 效果图漫游管线）

---

### 参考来源

- Spark — 专为 Three.js 的 3DGS 渲染器（World Labs，活跃维护）：https://github.com/sparkjsdev/spark
- mkkellogg/GaussianSplats3D（Three.js GS，官方推荐迁移 Spark）：https://github.com/mkkellogg/GaussianSplats3D
- gs3d-loader（Three.js GS 加载器）：https://github.com/wangyoumo/gs3d-loader
- Spark 深度解析（LoD/WebGL2/多对象）：https://blog.csdn.net/gitblog_01182/article/details/158017510
- GaussianSplats3D Drop-In 集成模式：https://blog.csdn.net/gitblog_07712/article/details/149011834
- 浏览器百万级 GS 渲染（性能/移动端优化）：https://blog.csdn.net/gitblog_00813/article/details/156784947
- Kairos-HomeWorld（AI 全屋可交互 3D 场景生成，2026-06 开源）：https://conven.org/laos/news/ace-robotics-open-sources-kairos-homeworld-enabling-fully-interactive-whole-home-3d-scene-generation-from-a-single-prompt/

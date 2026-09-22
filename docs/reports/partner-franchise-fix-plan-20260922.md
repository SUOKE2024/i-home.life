# 合作方加盟技术评估 → 修复实施方案（2026-09-22）

> 输入文档：[partner-franchise-tech-assessment-20260922.md](./partner-franchise-tech-assessment-20260922.md)
> 交付形态：**全部落地**（文档 + 3DGS 前端改动 + 后端 P0 断链修复 + 前端测试基建）
> 测试基建决策：**引入 Vitest（jsdom + @testing-library/react）**

## 0. 交付摘要

| 项 | 评估问题 | 本次交付 | 验证结果 |
|---|---|---|---|
| 3DGS 交互 | P1-2 触屏无缩放手段、无陀螺仪环视 | 双指捏合 FOV 缩放 + 陀螺仪相对式环视 + 3 个可单测纯函数 | Vitest 20/20 passed；`npm run build` 通过 |
| 3DGS 测试 | X3 前端零自动化测试 | Vitest 基建 + `GaussianViewer.test.jsx`（20 用例）+ CI 门禁接线 | `npm test` 20 passed |
| P0-1 凭据断链 | `pool.get(ecosystem)` 不透传凭据 → 真机桥恒抛 ValueError | 命令路径经 scheme 反查 project → 解密凭据注入 `pool.get(ecosystem, creds)` | 13 新用例 + 119 回归用例通过 |
| P0-2 场景生态 | 场景动作恒走默认 `matter`，与实际已配置生态不符 | `SceneAutomation.ecosystem` 列 + 三级解析（显式 → 项目首个已配凭据生态 → 兜底 matter） | 同上 |
| P0-3 传感器触发 | `check_sensor_triggers` 仅写日志不执行动作 | 命中后真实调用 `execute_scene_actions` 并回填 `action_status`/`action_note` | 同上 |
| P0-4 凭据明文 | `ecosystem_integrations.config` 明文落库 | AES-256-GCM 加密落库 + 存量迁移回填 + API 响应脱敏 + 旧明文兼容读 | 迁移 upgrade/downgrade/幂等三段实测通过 |

门禁：`flake8` 全绿、`mypy` 4 源文件 0 issue、后端相关子集 **119 passed**、前端 **20 passed**。

---

## 一、3DGS 虚拟看房修复方案（P1-2）

### 1.1 问题定位

`webapp/src/components/GaussianViewer.jsx` 交互仅覆盖桌面鼠标：
- `onWheel` 是唯一缩放入口 → 触屏设备（iOS/Android/鸿蒙）**无任何缩放手段**；
- 无 `DeviceOrientation` 支持 → 移动端「转动手机环视」这一 3DGS 看房核心体验缺失。

### 1.2 实现设计

1. **FOV 单源夹取**：缩放（滚轮 / 捏合）与全景查看器统一到 `[30°, 110°]`，防畸变与穿模。
2. **捏合基准式换算**：以「第二指落下瞬间的 FOV 与两指距离」为基准做比例换算，而非逐帧累加，避免误差累积与抖动。
3. **陀螺仪相对式环视**：以「开启后首帧姿态」为基准做增量，避免开启瞬间视角跳变；`beta` 夹取 ±90° 防相机翻转。
4. **诚实降级**：iOS `requestPermission` 被拒绝或抛异常 → 保持关闭，绝不伪称已开启。

### 1.3 代码改动

[GaussianViewer.jsx](../../webapp/src/components/GaussianViewer.jsx) 新增 3 个导出纯函数（导出以便单测直接断言，无需触 DOM）：

```js
const MIN_FOV = 30
const MAX_FOV = 110

/** FOV 夹取到 [30°, 110°]（与滚轮缩放同一区间，防畸变/穿模）。 */
export const clampFov = (fov) => Math.max(MIN_FOV, Math.min(MAX_FOV, fov))

/** 双指捏合 → FOV 换算（张开=拉近=FOV 变小，捏合=拉远=FOV 变大）。 */
export const fovFromPinch = (startFov, startDist, currentDist) => {
  if (!startDist || !currentDist || startDist <= 0 || currentDist <= 0) {
    return clampFov(startFov)
  }
  return clampFov(startFov * (startDist / currentDist))
}

/** 设备姿态 → 相机旋转增量（相对式，由调用方减去开启时的基准姿态）。 */
export const orientationToRotation = ({ alpha = 0, beta = 0 } = {}) => ({
  yaw: (-alpha * Math.PI) / 180,
  pitch: (Math.max(-90, Math.min(90, beta)) * Math.PI) / 180,
})
```

`bindInteraction` 内以「活动指针表」做手势分流（单指拖拽 / 多指捏合互斥）：

```js
const pointers = new Map()
let pinchStartDist = 0
let pinchStartFov = camera.fov
const pinchDistance = () => { /* 两指欧氏距离，<2 指返回 0 */ }

const onDown = (e) => {
  pointers.set(e.pointerId, { x: e.clientX, y: e.clientY })
  if (pointers.size === 1) { dragging = true; lastX = e.clientX; lastY = e.clientY }
  else if (pointers.size === 2) {
    // 进入捏合：停用拖拽，记录手势基准（FOV 与距离）
    dragging = false
    pinchStartDist = pinchDistance()
    pinchStartFov = camera.fov
  }
  scheduleRender()
}

const onMove = (e) => {
  if (!pointers.has(e.pointerId)) return
  pointers.set(e.pointerId, { x: e.clientX, y: e.clientY })
  if (pointers.size >= 2) {                    // 双指捏合（触屏唯一缩放手段）
    const dist = pinchDistance()
    if (pinchStartDist > 0 && dist > 0) {
      camera.fov = fovFromPinch(pinchStartFov, pinchStartDist, dist)
      camera.updateProjectionMatrix()
      scheduleRender()
    }
    return
  }
  /* ...单指拖拽环视（原逻辑）... */
}

const onUp = (e) => {
  pointers.delete(e.pointerId)
  if (pointers.size < 2) pinchStartDist = 0
  if (pointers.size === 1) {
    // 捏合结束仍有一指在屏 → 以该指针为基准恢复拖拽（否则缩放后视角操作会「死」住）
    const [p] = [...pointers.values()]
    dragging = true; lastX = p.x; lastY = p.y
  } else if (pointers.size === 0) { dragging = false }
}
```

陀螺仪（相对式 + 关闭即清基准）：

```js
let gyroBase = null
const onDeviceOrientation = (e) => {
  if (!gyroEnabledRef.current) { gyroBase = null; return }
  const { yaw, pitch } = orientationToRotation({ alpha: e.alpha ?? 0, beta: e.beta ?? 0 })
  if (!gyroBase) gyroBase = { yaw, pitch }      // 开启后首帧取基准 → 视角不跳变
  const limit = Math.PI / 2
  camera.rotation.order = 'YXZ'
  camera.rotation.y = -(yaw - gyroBase.yaw) + ((initialView?.heading ?? 0) * Math.PI) / 180
  camera.rotation.x = Math.max(-limit, Math.min(limit,
    pitch - gyroBase.pitch + ((initialView?.pitch ?? 0) * Math.PI) / 180))
  scheduleRender()
}
```

开关按钮（`gyroSupported && status === 'ready'` 才渲染，带 `data-gyro-toggle="on|off"` 供测试断言）内部处理 iOS 权限：

```js
const toggleGyro = async () => {
  if (gyroEnabledRef.current) { gyroEnabledRef.current = false; setGyroOn(false); return }
  try {
    const DOE = window.DeviceOrientationEvent
    if (DOE && typeof DOE.requestPermission === 'function') {
      const granted = await DOE.requestPermission()
      if (granted !== 'granted') return            // 拒绝 → 不开启，不伪称已开启
    }
    gyroEnabledRef.current = true; setGyroOn(true)
  } catch { gyroEnabledRef.current = false; setGyroOn(false) }  // 异常 → 诚实保持关闭
}
```

### 1.4 交互行为矩阵（交付后）

| 输入 | 桌面 | 触屏 | 结果 |
|---|---|---|---|
| 单指拖拽 / 鼠标拖拽 | ✓ | ✓ | 环视（`YXZ` 序，pitch 夹取 ±90°） |
| 滚轮 | ✓ | — | FOV `±deltaY × 0.05`，夹取 [30, 110] |
| 双指捏合 | — | ✓ | FOV `起始FOV × (起始距离/当前距离)`，夹取 [30, 110] |
| 双指期间拖拽 | — | 抑制 | 旋转量不变（防手势串扰） |
| 双指后抬一指 | — | ✓ | 以剩余指针为基准恢复拖拽（无跳变） |
| 陀螺仪 | 视设备 | ✓ | 相对基准增量环视；需用户显式开启 |
| 权限被拒/异常 | — | ✓ | 保持关闭，姿态事件不生效 |

### 1.5 本次未覆盖（诚实遗留，仍属 P2）

- 内容生产链（真实 SPZ 资产、`render_panorama` 仍为 mock）、WebXR/Vision Pro 入口；
- 陀螺仪与拖拽的**同时协同**（当前为独立通道，陀螺仪开启时拖拽仍可覆盖旋转，非叠加）。

---

## 二、3DGS 前端自动化测试（Vitest + jsdom）

### 2.1 基建

| 文件 | 改动 |
|---|---|
| `webapp/package.json` | devDeps 新增 `vitest@^3.2.7`、`jsdom@^26.1.0`、`@testing-library/react@^16.3.3`、`@testing-library/dom@^10.4.2`；scripts 新增 `"test": "vitest run"` |
| `webapp/vitest.config.js`（新增） | `environment: 'jsdom'`、`globals: true`（RTL 自动 cleanup 依赖全局 `afterEach`）、`include: ['src/**/*.test.{js,jsx}']` |
| `.github/workflows/ci.yml` `frontend-smoke` job | `npm ci` 后新增 `npm test` 步骤，**未过测试不进入构建** |

> 版本约束：`vitest@5` 要求 `vite ^6.4+`，本仓 webapp 为 `vite ^5.4.11`，故锁 `vitest@^3.2.7`（vite 5/6 均兼容）。生产构建仍走 `vite.config.js`，未被测试配置侵入。

### 2.2 打桩策略（jsdom 无 WebGL/WebGPU）

- `vi.mock('three', …)`：`Scene / Sprite / SpriteMaterial / CanvasTexture / PerspectiveCamera / WebGLRenderer / Raycaster / Vector2`。相机实例收集到 `globalThis.__gs3d.cameras`（`vi.mock` 工厂被提升，无法引用模块级变量，故挂 globalThis），暴露 `fov / rotation / projectionUpdateCount` 供断言。
- `vi.mock('@sparkjsdev/spark', …)`：`SplatMesh` 构造即回调 `onLoad()` → 组件进入 `status='ready'`，使陀螺仪按钮渲染条件（`ready`）可达。
- `HTMLCanvasElement.prototype.getContext`：`webgl2` 返回真值（放行 `supportsWebGL2`），`2d` 返回 no-op 上下文（覆盖 `paintDeviceSprite`）。
- 补齐 `ResizeObserver`；`PointerEvent` 用 `Event` + 属性注入（jsdom 未实现 PointerEvent）。

### 2.3 用例清单（`webapp/src/components/GaussianViewer.test.jsx`，20 用例）

**纯函数（5）** — `clampFov` 上下限夹取；`fovFromPinch` 张开拉近 / 捏合拉远并夹取 / 非法距离回退起始 FOV 不 NaN；`orientationToRotation` 取反与 ±90° 夹取 + 缺省/null 参数不抛错。

**双指缩放 DOM 手势（6）**
1. 两指张开 → FOV 75 → 37.5（`75 × 100/200`）且 `updateProjectionMatrix` 被调用；
2. 两指捏合超上限 → 夹取 110；
3. 捏合期间拖拽被抑制（`rotation` 不变、FOV 已变）；
4. 捏合后抬一指 → 单指继续拖拽 `rotation.y ≈ -0.05`（回归本次修复的恢复逻辑）；
5. 单指拖拽环视不受捏合逻辑影响（`rotation.y/x`、`rotation.order === 'YXZ'`）；
6. 滚轮与捏合共用同一区间（`-2000` → 30、`+4000` → 110）。

**陀螺仪（9）**
1. 不支持 `DeviceOrientationEvent` → 不渲染开关（诚实降级）；
2. 支持时开关默认 `off`；
3. 桌面（无 `requestPermission`）点击直接开启并驱动旋转（α 0→90 ⇒ `rotation.y = π/2`）；
4. 开启瞬间以当前姿态（α=180/β=30）为基准 → 视角不跳变，再转 90° 恰得 90°；
5. iOS `requestPermission` 返回 `'denied'` → 保持 `off` 且姿态事件不生效；
6. `requestPermission` 抛异常 → 保持 `off`（不伪称已开启）；
7. 关闭后姿态事件不再生效（保留关闭前旋转量）；
8. 与 `initialView` 叠加（heading 90 + 陀螺仪 90 ⇒ `π`）；
9. β=170° 被夹取到 `π/2`（防翻转）。

### 2.4 运行

```bash
cd webapp
npm test          # vitest run，当前 20 passed / 545ms
```

---

## 三、P0 断链修复实施步骤（智能家居）

### 3.1 P0-1 凭据注入通道（真机调用不可达的根因）

**根因**：`execute_device_command` 调 `pool.get(ecosystem)` 时不传凭据 → `MijiaBridge.connect({})` 抛 `ValueError("米家连接需要 username 和 password")` → 真机路径恒不可达。`SmartDevice` 无 `project_id` 列，需经 `SmartHomeScheme` 反查。

**步骤**（`app/services/scene_automation_service.py`）：

1. 新增 `_resolve_ecosystem_credentials(db, project_id, ecosystem)`：按 `project_id + ecosystem` 查 `EcosystemIntegration`，`config` 解密后返回（无记录返回 `{}`）。
2. 命令路径：`SmartDevice.scheme_id` → `SmartHomeScheme.project_id` → 凭据 → `pool.get(ecosystem, bridge_creds)`（**串行，持 db**）。

```python
_scheme = (await db.execute(
    select(SmartHomeScheme).where(SmartHomeScheme.id == device.scheme_id)
)).scalar_one_or_none()
bridge_creds = await _resolve_ecosystem_credentials(
    db, _scheme.project_id if _scheme else None, ecosystem,
)
bridge = await asyncio.wait_for(
    pool.get(ecosystem, bridge_creds), timeout=BRIDGE_COMMAND_TIMEOUT_SECONDS,
)
```

3. 场景路径：`_run_scene_action(pool, scene, item, ecosystem, credentials)` 由调用方在**并行波次之前**解析并传入。

> 硬约束遵守：凭据解析有 DB 访问，必须放在 `asyncio.gather` 并行波次**之外**（共享 AsyncSession 并行会触发 SQLAlchemy ISCE 冲突，致 DB 查询静默降级）。

### 3.2 P0-2 场景生态解析（`SceneAutomation.ecosystem`）

**步骤**：

1. 模型加列（`app/models/scene_automation.py`）：`ecosystem: Mapped[str | None] = mapped_column(String(50), nullable=True)`。
2. Schema（`app/schemas/scene_automation.py`）：`SceneAutomationCreate/Update/Response` 均加 `ecosystem: str | None`。
3. 服务新增 `_resolve_scene_ecosystem(db, scene)`，三级优先级：

```python
if scene.ecosystem:                       # ① 场景显式指定
    return scene.ecosystem, await _resolve_ecosystem_credentials(db, scene.project_id, scene.ecosystem)
if scene.project_id:                      # ② 项目下首个「已配置凭据」的生态（按 created_at）
    for eco in (...):
        creds = _decrypt_ecosystem_config(eco.config)
        if creds:
            return eco.ecosystem, creds
return _DEFAULT_SCENE_ECOSYSTEM, {}       # ③ 兜底 matter（无凭据 → 桥诚实抛错 → pending）
```

4. 迁移 `alembic/versions/k3c4d5e6f7a9_add_scene_ecosystem_and_encrypt.py`：`batch_alter_table` 加列（SQLite 兼容），`down_revision = "a3b4c5d6e7f8"`。

### 3.3 P0-3 传感器触发执行闭环

**根因**：`check_sensor_triggers` 命中后仅写 `SceneBehaviorLog`，动作从不执行。

**步骤**（`check_sensor_triggers` 命中分支）：

1. 先写触发日志并 `await db.commit()`（日志与执行解耦，执行异常不丢触发证据）。
2. 真实调用 `execute_scene_actions(db, scene, user_id, trigger_source="sensor", log_action_type="sensor_trigger")`（新增 `log_action_type` 参数，替代硬编码 `manual_trigger`）。
3. 按返回 `actions` 汇总 `statuses` → `action_status`：有 success → `success`；有 failed → `failed`；否则 `pending` 并写明「生态桥未接真机或未配置凭据，已记录触发意图未实际执行」。
4. 异常兜底 `action_status="failed"`，标注 `场景动作执行异常: {e}`，不阻断其余场景匹配。

### 3.4 P0-4 生态凭据加密 + 存量迁移 + 响应脱敏

**步骤**：

1. **加密落库**（写路径 fail-closed，拒绝明文）：

```python
def _encrypt_ecosystem_config(config: dict | None) -> dict | None:
    if not config:
        return None
    from app.services.device_credentials import encrypt_device_credentials
    encrypted = encrypt_device_credentials(config)   # AES-256-GCM，密钥 = SHA-256(paseto_secret_key)
    if encrypted is None:
        raise ValueError("生态凭据加密失败（PASETO 密钥不可用），已拒绝明文落库")
    return encrypted                                  # {"encrypted": "<b64(nonce+ct)>"}
```

`create_ecosystem` 中注入：`data["config"] = _encrypt_ecosystem_config(data.get("config"))`；API 层捕获 `ValueError` → **HTTP 422**。

2. **存量明文迁移**（迁移第二段，幂等）：
   - 逐行读 `ecosystem_integrations.config`，跳过已是密文（含 `encrypted` 键）的行；
   - 加密后 `UPDATE` 回写；单行失败打印告警并跳过（不阻断整表）；
   - `downgrade` 将密文解回明文 + `DROP COLUMN`（恢复变更前行为），并打印 `WARN: N 行生态凭据已回滚为明文存储`。

3. **旧明文兼容读**（迁移未覆盖时不中断功能）：

```python
def _decrypt_ecosystem_config(config: dict | None) -> dict | None:
    if not isinstance(config, dict) or not config:
        return None
    if "encrypted" not in config:
        return config                          # 历史明文行（未迁移）原样兼容
    from app.services.device_credentials import decrypt_device_credentials
    return decrypt_device_credentials(config)
```

4. **API 响应脱敏**（只回露字段名，绝不回露值）：`redact_ecosystem_config` → `{"redacted": True, "keys": ["password", "username"]}`，`create_ecosystem` / `list_ecosystems_by_project` 统一走 `_redacted_ecosystem_response`。
5. `sync_to_ecosystem` 读凭据改为 `_decrypt_ecosystem_config(eco.config) or {}`。

**迁移实测（`.venv` + sqlite）**：

```
alembic upgrade head     → encrypted: ecosystem_integrations.config rows=1
                           {"username":"mi-user","password":"mi-secret"} → {"encrypted":"G7d3PprkLRGAKgep+..."}
alembic downgrade -1     → WARN: 1 行生态凭据已回滚为明文存储
                           restored: [('{"username": "mi-user", "password": "mi-secret"}',)]
重跑 upgrade             → 幂等通过（密文行被跳过）
```

### 3.5 米家真机调用实施步骤（runbook）

> 前置事实（诚实标注）：`MijiaBridge` 云登录为真实 HTTP；设备清单走 `miio.cloud.CloudInterface`，**状态查询/控制走局域网 `MiotDevice`，要求服务端与设备同网段**，跨网段不可用。其余生态（Matter/HomeKit/涂鸦/鸿蒙）仍为 `NotImplementedError("TODO: need API key")`，接入真机前必须诚实 `pending`。

1. **落凭据**：`POST /api/scene-automation/projects/{project_id}/ecosystems`
   密文由服务端加密，请求体为明文（TLS 保护）：`{"ecosystem":"mijia","config":{"username":"<米家账号>","password":"<密码>"}}`；响应 `config` 只回 `{"redacted": true, "keys": [...]}`。
2. **校验落库形态**：`sqlite3`/`psql` 查 `ecosystem_integrations.config`，必须为 `{"encrypted": "..."}`（若出现明文说明迁移未执行或 `PASETO_SECRET_KEY` 不可用）。
3. **绑定场景生态**（可选，缺省走自动解析）：`PATCH /api/scene-automation/scenes/{scene_id}` body 带 `{"ecosystem": "mijia"}`。
4. **网络前提**：应用服务器与米家设备同网段（同 VLAN/同 AP），否则第 6 步必报 `RuntimeError("…需与设备同网段")`。
5. **平台设备 id 需与米家 did/mac 对齐**（关键前置，当前未自动化）：`MijiaBridge._find_device` 按 `did / mac / 云 id` 匹配，而 `execute_device_command` 传入的是平台 `SmartDevice.id`。真机联调时须将 `smart_devices.id` 置为米家 `did`（或 `mac`），否则桥报 `ValueError("米家设备未找到: …")`。
   > 遗留（P1）：新增「平台设备 ↔ 米家 did」映射列或设备发现导入端点，当前为手工约定。
6. **端到端验证**（观测 `action_status` 而非仅 HTTP 200）：

```bash
# 6.1 单设备命令：期望 action_status=success 且 device.state 被写入
curl -s -X POST $HOST/api/smart-home/devices/$DEVICE_ID/command \
  -H "Authorization: Bearer $TOKEN" -H 'Content-Type: application/json' \
  -d '{"action":"turn_off","params":{},"source":"app"}'

# 6.2 场景执行：期望 actions[].action_status=success
curl -s -X POST $HOST/api/scene-automation/scenes/$SCENE_ID/execute \
  -H "Authorization: Bearer $TOKEN" -H 'Content-Type: application/json' -d '{"trigger_source":"app"}'
```

7. **失败态的诚实预期**（不得视为 bug）：
   - 凭据缺失/错误 → `pending` + `bridge_not_configured: 米家连接需要 username 和 password`；
   - 跨网段 → `pending` + `bridge_not_configured: 米家设备状态查询失败（需与设备同网段）…`；
   - 云清单不可达 → `RuntimeError("米家云设备清单拉取失败: …")`（日志 `MijiaBridge.get_devices cloud failed`）。
8. **回滚**：`python scripts/rollback.sh` 无关（本次无 flag 变更）；如需回退凭据加密，执行 `alembic downgrade -1`（**会把凭据还原为明文**，仅在受控环境执行）并移除 `_encrypt_ecosystem_config` 注入。

---

## 四、验收标准（达成情况）

| # | 标准 | 结果 |
|---|---|---|
| A1 | 触屏双指可缩放，FOV 落在 [30, 110]，两指期间不误改旋转 | ✓ 用例 1–3 |
| A2 | 缩放后仍可单指环视（无「死住」） | ✓ 用例 4 |
| A3 | 陀螺仪需用户显式开启；拒绝/异常保持关闭且姿态事件不生效 | ✓ 用例 5–6 |
| A4 | 开启瞬间视角不跳变，姿态按相对基准生效 | ✓ 用例 4（陀螺仪组） |
| A5 | 前端测试可在 CI 执行且失败即阻断 | ✓ `frontend-smoke` 新增 `npm test` |
| A6 | 命令/场景路径真机桥可拿到解密凭据 | ✓ `test_device_command_injects_ecosystem_credentials` 等 13 用例 |
| A7 | 传感器命中后动作真实执行，状态如实回填 | ✓ `test_sensor_trigger_actually_executes_actions` |
| A8 | 凭据加密落库、响应脱敏、旧明文兼容、迁移可回滚 | ✓ 迁移三段实测 + 4 用例 |
| A9 | 无回退：相关后端子集 + 静态检查全绿 | ✓ 119 passed / flake8 0 / mypy 0 |

## 五、遗留与风险（诚实边界）

1. **P1**：平台设备与米家 `did` 无映射表 → 真机联调需手工对齐 `smart_devices.id`（3.5 步骤 5）。
2. **P1**：`execute_device_command` 的 `ecosystem` 仍由调用方（API 层）传入默认值，未按设备品牌/项目凭据自动推导（场景路径已自动，命令路径未自动）。
3. **P1**：非米家生态（Matter/HomeKit/涂鸦/鸿蒙）仍为 stub，token 一致校验等真机能力未接入。
4. **P2**：3DGS 内容生产链（真实 SPZ 资产、非 mock 全景渲染、WebXR）不在本次范围。
5. **跨模块**：本仓仍有 129 项未提交改动（含两个完整版本）与 `scripts/test_baseline.json` 记录 `2768` vs 实测 `2760` 的漂移，建议在本次改动提交前一并处理（评估文档 X1/X2）。
6. **版本号**：本次改动注释标记为 v1.17.1，`app/config.py` 仍为 `1.17.0`；正式发版须按 `.claude/templates/version-bump.md` 全链路同步（含 `webapp/package.json` 现为 `1.15.10` 的历史漂移）。
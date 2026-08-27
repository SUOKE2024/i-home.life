# 设备链路加固 — 穿戴设备及智能家居外部设备接入评估与修复记录

> 日期：2026-08-27 ｜ 范围：穿戴/智能家居（外部设备）接入系统 ｜ 状态：评估 + P0/P1 修复落地，P2 遗留明确标注

## 一、评估结论摘要

对「穿戴设备及智能家居外部设备接入系统」七个维度全面检查（源码逐行核验 + 测试覆盖盘点）：

| 维度 | 结论 | 亮点 / 短板 |
|---|---|---|
| 设备连接稳定性 | 中等 | WS 心跳+指数退避重连扎实；**生态桥 5 生态全 stub（仅米家云登录为真实 HTTP），真机链路未验证** |
| 数据传输安全性 | 认证/授权强，完整性弱 | PASETO+归属校验+IDOR 回归齐全；**传感器/健康数据无数值结构校验、Matter 凭据明文落库、限流按 IP 与设备场景错配** |
| 协议兼容性 | 设计完备，实现 stub | 协议白名单 + CheckConstraint + Matter 2.0 知识层完备；**零真实协议栈、无 BLE** |
| 功耗管理 | 有意识无策略 | 60Hz 仅缓存、页开一次上传；**无自适应采样、无后台低功耗上报** |
| 多设备并发 | 执行管线优秀 | 两阶段并行 + 连接池 + 波次规划优秀；**触发扫描 O(N)、state 并发无保护、无快照并发测试** |
| 异常处理 | 诚实降级一流 | pending/failed 分类 + 503 flag 诚实；**无超时、无重试、命令同步内联执行** |
| 用户体验 | 实时推送有、同步靠轮询 | WS 设备状态事件已推送；**智能家居页未订阅、无命令进度反馈** |

## 二、已落地修复（P0/P1，2026-08-27）

### 1. 数据完整性校验（P0）
- `app/schemas/sensor_snapshot.py`：`GpsReadout` 纬度 ±90 / 经度 ±180 / accuracy ≥0；`SensorSnapshotRequest` 温度 -40~80 / 湿度 0~100 / 光照 0~200000 lux，越界 422。
- `app/schemas/health_monitor.py`：`monitor_type` 收窄为 Literal 枚举；`value` 必需键校验（heart_rate→bpm、spo2→spo2、sleep_quality→sleep_score、fall_detection→fall_detected、activity_tracking→steps；air_quality 兼容历史键不强制）。

### 2. 桥命令超时与重试（P0）
- `app/services/scene_automation_service.py`：新增 `_bridge_send_command`（统一超时 `BRIDGE_COMMAND_TIMEOUT_SECONDS=10s` + 瞬时错误重试 1 次共 2 次；确定性失败 NotImplementedError/ValueError 不重试），`execute_device_command` 与 `_run_scene_action` 共用；`pool.get` 建连同样限时。防第三方桥挂起拖垮请求/场景。

### 3. 触发扫描索引化（P1）
- `scene_automations.trigger_type` 冗余派生列（从 `trigger_condition.type` 派生，写路径统一：`create_scene`/`update_scene`/`accept_prediction`）+ 索引。
- 迁移 `alembic/versions/c2d3e4f5a6b7_add_scene_trigger_type.py`（幂等 + 存量回填，SQLite/PostgreSQL 双方言）。
- `check_sensor_triggers` SQL 层按 `trigger_type == "sensor"` 预过滤，避免每次快照上传全量扫描。

### 4. Matter 凭据加密（P1）
- `app/services/device_credentials.py`：SHA-256(paseto_secret_key) 派生 AES-256-GCM 密钥；加密 `wifi_credentials`/`thread_credentials` 落库（JSON 存 `{"encrypted": b64}`），解密失败诚实返回 None。
- `POST /api/smart-home/matter/commission` 落库前加密。

### 5. 传感器快照 per-user 限流（P1）
- `POST /api/sensors/snapshot` 按用户滑动窗口限流（`sensor_snapshot_rate_limit_per_minute` 默认 30/min，0/负值不限流），补通用 IP 限流与设备高频上报场景的错配；进程内存储多 worker 不共享（best-effort，与 rate_limit 中间件同局限）。

### 6. 可观测性指标（P1）
- `app/metrics.py` 新增：`device_command_total{duration}` / `device_command_duration_seconds`、`scene_execute_total{trigger_source}` / `scene_execute_duration_seconds`、`sensor_snapshot_upload_total{platform}`。

## 三、测试验证

- 新增 `tests/test_device_link_hardening.py`（18 用例）：范围校验 8 例、健康枚举/结构 3 例、限流 2 例、桥超时/重试 4 例、凭据加密 3 例、trigger_type 派生 4 例。
- 既有回归：`test_sensor_snapshot`（+2 场景直构补 trigger_type）、`test_scene_automation`（+1）、`test_device_overlay`（桥错误 send_calls 1→2 对齐重试语义）。
- 迁移验证：`alembic upgrade head` → `downgrade -1` → `upgrade head` 全链路幂等通过（对齐 CI migration-test）。
- 门禁：flake8（0 issue）、mypy（0 issue）、全量 pytest 基线见 `scripts/test_baseline.json`。

## 四、遗留风险与后续建议（P2，第一批未实施，第二批已修复部分）

| 项 | 说明 |
|---|---|
| 命令异步化 | ~~设备命令/场景执行仍在 HTTP 请求内同步内联~~ → 已修复：`execute_async=True` 后台执行 + WS 回填 |
| BLE 穿戴接入 | ~~无 flutter_blue 依赖~~ → 已接入：flutter_blue_plus 扫描/连接/心率订阅 + 穿戴设备页 |
| WS 设备状态订阅 | ~~智能家居页未订阅~~ → 已修复：`smart.device.state`/`scene.triggered` 订阅刷新 |
| device.state 并发保护 | ~~last-write-wins~~ → 已修复：per-device asyncio.Lock 串行化 + 锁内 refresh |
| 生态桥真机契约 | ~~5 生态桥 stub~~ → 米家已真机化（python-miio）；Matter/HomeKit/涂鸦/鸿蒙仍 stub |
| GB 50311 helper | ~~未接线~~ → 已接入 plan_wiring（weak_current_box/safety 字段） |
| Flutter 自适应采样 | ~~60Hz 固定~~ → 已修复：静止降频 10Hz（SensorService） |

## 五、第二批落地（2026-08-27 P2 遗留修复 + 穿戴/智能家居接入）

### 遗留修复（后端）
- **device.state 并发保护**：`scene_automation_service` 新增 `_device_lock(device_id)`（进程内 asyncio.Lock，best-effort 跨 worker），`execute_device_command` 整段桥执行与 `execute_scene_actions` 状态应用均串行化，锁内 `db.refresh` 防独立 session 快照覆盖。
- **命令/场景异步化**：`DeviceCommandRequest`/`SceneExecuteRequest` 新增 `execute_async` 参数；`execute_async=True` 时请求立即返回 `queued`，FastAPI BackgroundTasks 独立 session 执行，完成后 WS 推送 `smart.device.state`/`scene.triggered`（`async: true`）。
- **GB 50311 布线合规接入**：`plan_wiring` 输出新增 `weak_current_box`（弱电箱推荐尺寸/容量/网线等级）与 `safety`（涉水区 IP 防护/燃气认证）字段（schema 可选字段，向后兼容）。

### 穿戴设备接入（Flutter，flutter analyze 0 issue + 单测通过）
- `flutter_blue_plus ^2.3.12` 依赖（`License.nonprofit` 免费档；鸿蒙平台能力探测降级）。
- `lib/services/wearable_ble_service.dart`：扫描/连接/服务发现/心率（0x180D/0x2A37）与电量（0x180F/0x2A19）订阅，心率标准格式解析（8/16-bit）。
- `lib/pages/wearable_devices_page.dart`：扫描列表/连接状态/实时心率/一键上报健康监测（device_id=BLE MAC）。
- `SensorService` 自适应采样：静止降频 10Hz / 运动升频 60Hz（加速度模长变化阈值 + 2s 防抖）。
- `smart_home_page`：AppBar 穿戴设备入口 + WS 设备状态订阅（收到状态事件刷新设备）+ 传感器快照 30s 周期上报。

### 智能家居（米家）真机接入（后端）
- `python-miio >=0.5.12` 依赖。
- `MijiaBridge` 真机化：`get_devices`（`miio.cloud.CloudInterface.get_devices` 云清单）、`get_device_state`（`MiotDevice.info()` 局域网）、`send_command`（`MiotDevice.set_property`，动作映射 turn_on/turn_off/set_brightness 等 + params 传 siid/piid/value 直连）。
- 诚实降级：云接口未初始化 → `NotImplementedError`；云/局域网调用失败 → `RuntimeError` 如实报错。局限诚实标注：控制要求服务端与设备同网段。
- `test_mijia_bridge_login_success` 断言更新（云接口未初始化时 NotImplementedError）+ 6 个新米家桥测试。

## 六、文档同步

- `CLAUDE.md`：新增「设备链路加固」章节 + 基线数字同步。
- `scripts/test_baseline.json`：passed 计数同步。

### 第二批遗留（需真实硬件/账号验证，代码路径已就绪）
| 项 | 说明 |
|---|---|
| BLE 真机验证 | BLE 扫描/连接/心率订阅需 Android/iOS 真机验证；厂商私有特征（血氧/跌倒）需扩展 |
| 米家真机验证 | 需小米账号 + 局域网设备验证云清单/控制；跨网段控制不可用 |
| Matter/HomeKit/涂鸦/鸿蒙 | 仍 stub（需对应 SDK 与生态账号） |
| 多 worker WS 广播 | uvicorn 4 workers 下 WS 广播仅同进程连接可达；严格一致需 Redis pub/sub（后续项） |

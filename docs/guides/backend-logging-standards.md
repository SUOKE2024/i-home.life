# 后端日志埋点规范（场景执行与传感器链路）

> 版本：v1.0（2026-08-12）
> 适用范围：后端团队，尤其智能家居（smart-home / scene-automation / sensor / vr）链路
> 来源：设备链路诊断修复（传感器快照 + 场景触发 + P0 设备热点联动）落地的日志埋点方案

---

## 1. 目标与原则

日志用于**问题排查**与**链路可观测**，遵循四原则：

1. **状态流转可复现**：一条业务链路从「请求进入」到「终态」的事件序列，可完整重放
2. **诚实标注**：降级/未接入必须明示（`action_status=pending` + `bridge_not_configured`），禁止伪装成功
3. **结构化字段**：所有事件用 `key=value` 或 JSON 结构化输出，便于 grep/采集
4. **PII 最小化**：不记录明文手机号/口令；user_id 用内部 UUID

## 2. 命名规范

事件名用 `snake_case`，格式：`<模块>_<动作>_<状态>`，全小写。

| 前缀 | 模块 |
|---|---|
| `sensor_snapshot_*` | 传感器快照上传 |
| `sensor_trigger_*` | 场景传感器触发 |
| `sensor_condition_*` | 条件匹配明细（debug） |
| `device_command_*` | 设备命令执行管线 |
| `scene_execute_*` | 场景执行管线 |

## 3. 日志分级规范

| 级别 | 适用 |
|---|---|
| `logger.info` | 业务事件主链路（received / dispatched / executed / done） |
| `logger.debug` | 明细数据（原始读数、逐键匹配、上下文、设备清单） |
| `logger.warning` | 可恢复异常（bridge_error、动作 rejected、白名单拦截） |
| `logger.exception` | 致命异常（DB 失败、不可恢复） |

> 纪律：主链路 info 每条业务请求 ≤ 6 条；明细一律 debug，生产默认不输出。

## 4. 埋点清单（已落地）

### 4.1 传感器快照上传（`app/api/sensor_snapshot.py`）

| 事件 | 级别 | 关键字段 |
|---|---|---|
| `sensor_snapshot_received` | info | user_id / platform / timestamp / 各传感器 available |
| `sensor_snapshot_raw` | debug | user_id / device_id / accel{x,y,z} / gyro / mag / gps 原始读数 |
| `sensor_snapshot_persisted` | info | snapshot_id / user_id / platform / temp / humidity / lux / sampled_at |
| `sensor_trigger_check_start` | info | snapshot_id / ambient_data（仅真实上报数据） |
| `sensor_trigger_check_done` | info | snapshot_id / triggered 数 |
| `sensor_trigger_check_skipped` | info | snapshot_id / 跳过原因（无环境/GPS 数据） |
| `sensor_trigger_check_failed` | exception | snapshot_id / error |

### 4.2 场景传感器触发（`app/services/scene_automation_service.py`）

| 事件 | 级别 | 关键字段 |
|---|---|---|
| `sensor_trigger_scan` | info | user_id / candidate_scenes / ambient_data |
| `sensor_trigger_match` | info | user_id / scene / scene_name / condition / ambient_data / matched |
| `sensor_trigger_hit` | info | user_id / scene / scene_name / actions / action_status |
| `sensor_triggers_executed` | info | user_id / triggered_count |
| `sensor_condition_key_missing` | debug | key / expected |
| `sensor_condition_pass/fail` | debug | key / actual / expected（或比较符） |
| `sensor_condition_result` | debug | matched_keys / total_keys / matched |

### 4.3 设备命令执行管线（`execute_device_command`）

| 事件 | 级别 | 关键字段 |
|---|---|---|
| `device_command_received` | info | user_id / device / name / type / action / params / source / ecosystem / scene_id |
| `device_command_rejected` | warning | device / type / action / allowed |
| `device_command_context` | debug | device / ambient_data |
| `device_command_bridge_dispatch` | info | device / action / ecosystem / 阶段（→ connect / → send_command / → result） |
| `device_command_bridge_not_configured` | info | device / action / ecosystem / error |
| `device_command_bridge_error` | warning | device / action / ecosystem / error |
| `device_command_executed` | info | user_id / device / action / status / source / note |

### 4.4 场景执行管线（`execute_scene_actions`）

| 事件 | 级别 | 关键字段 |
|---|---|---|
| `scene_execute_start` | info | user_id / scene / name / trigger_source / scheme_id / actions_count |
| `scene_execute_devices` | debug | scene / matched_devices |
| `scene_execute_action_dispatch` | info | scene / index / device / action / params |
| `scene_execute_action_skipped` | info | scene / index / device_id / 原因 |
| `scene_execute_action_rejected` | info | scene / index / device / action / allowed |
| `scene_execute_action_bridge` | info | scene / device / action / 阶段（→ connect / → send_command / → result） |
| `scene_execute_action_bridge_not_configured` | info | scene / device / action / error |
| `scene_execute_action_result` | info | scene / device / action / status |
| `scene_execute_done` | info | user_id / scene / name / actions_count / **status_summary**（各状态计数） |

## 5. 新埋点开发规范（checklist）

新增日志时逐项对照：

- [ ] 事件名符合 `<模块>_<动作>_<状态>` snake_case
- [ ] 含关联键（user_id / scene_id / device_id / snapshot_id），可跨事件串联
- [ ] 终态事件含结果摘要（如 `status_summary` / `status` / `note`）
- [ ] 降级/未接入路径有诚实标注（`action_status=pending` + 原因）
- [ ] 无 PII（明文手机号/口令/地址），一律用内部 UUID
- [ ] 主链路 info ≤ 6 条/请求，明细进 debug
- [ ] 异常用 warning/exception，含业务上下文（对象 id + error）

## 6. 排查示例（如何用日志定位问题）

**场景 A：设备命令没生效**
```
grep device_command_ <日志> | tail
→ 看 received(参数) → bridge_dispatch(是否走到 send_command) → executed(终态 status)
→ status=pending + bridge_not_configured → 桥未接真机（预期行为，非故障）
→ status=failed + bridge_error → 桥调用异常，看 error 字段
```

**场景 B：传感器快照未触发场景**
```
grep sensor_trigger_ <日志> | tail
→ check_start(ambient_data) → scan(candidate_scenes) → match(condition vs ambient_data)
→ matched=false + sensor_condition_key_missing → 键缺失（诚实不触发，符合设计）
```

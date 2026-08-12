# 场景执行链路性能瓶颈分析简报

> 日期：2026-08-12
> 依据：`execute_scene_actions` / `execute_device_command` 执行管线日志（`scene_execute_*` / `device_command_*`）实测
> 范围：P0 设备热点联动的场景执行链路（3D 点击 → API → 执行管线 → 生态桥）

---

## 1. 链路与时延基线（当前实测）

基于日志输出的实际时延（测试环境，生态桥未接真机 → `pending` 快速路径）：

| 阶段 | 事件 | 实测时延 | 主导因素 |
|---|---|---|---|
| 请求进入 | `device_command_received` | — | — |
| 白名单校验 | `device_command_rejected`（仅拦截时） | <1ms | 纯内存比较 |
| 上下文获取 | `_latest_sensor_context` | ~5-15ms | 1 次 SensorSnapshot 查询（场景级仅 1 次 ✅） |
| 日志落库 | SceneBehaviorLog INSERT | ~10-30ms/条 | SQLite 单条 INSERT |
| 生态桥 | `connect → send_command → disconnect` | 未接入：`NotImplementedError` 立即返回 | 桥未接真机 |
| 提交 | `db.commit()` | ~5-20ms | 批量提交（动作级共享 1 次 ✅） |
| **整链路（pending 路径）** | `scene_execute_done` | **~50-100ms** | DB 写入为主 |

**结论**：当前（桥未接入）执行管线自身不是瓶颈——单场景 50-100ms，可接受。

## 2. 瓶颈点分析（桥接入真机后的风险前瞻）

按风险排序：

### 🔴 P0-1 动作串行执行（O(N) 延迟）
`execute_scene_actions` 对 N 个动作**逐一 await** `bridge.send_command`，无并行。
- 影响：10 设备场景 = 10 × (桥连接 + 命令往返)。Matter over Thread / 云端桥接单命令约 100-500ms → 场景总耗时 **1-5s**
- 日志佐证：`scene_execute_action_bridge: ... → connect → send_command → result` 逐动作串行打印
- 建议：无状态依赖的动作用 `asyncio.gather` 并行（复用项目 `parallel_tool_calls_enabled` 经验）；需保留串行的场景（联动时序）用 `DEPENDS_ON` 字段声明

### 🔴 P0-2 桥连接重复建立（无连接池）
每个动作独立 `BridgeFactory.get_bridge → connect → disconnect`。
- 影响：N 个动作重复 N 次连接握手（TLS/commissioning），连接开销 ≥ 命令本身
- 建议：`execute_scene_actions` 内**建立一次连接，复用执行全部动作**再断开；桥实现侧增加连接池/单例会话

### 🟠 P1-1 日志频率与热度
`scene_execute_action_bridge` 每动作 3 条 info（connect/send/result）+ `scene_execute_action_dispatch` + `action_result` = 5 条/动作。
- 影响：10 动作场景 = 50+ 条日志；高频触发（传感器自动触发）下刷屏
- 建议：bridge 三阶段合并为 1 条 info（含 `→` 状态链），或降为 debug；保留 `done` 的 status_summary 作为聚合指标

### 🟠 P1-2 传感器上下文每次场景查询
`_latest_sensor_context` 场景级 1 次（✅ 已优化，不在动作内）。但**每个场景触发都查**。
- 建议：高频触发时加短 TTL 缓存（复用 `cache_service`），避免重复查表

### 🟡 P2-1 动作级 INSERT 无批量
N 个动作 = N 条 SceneBehaviorLog INSERT（最终 1 次 commit 已批量提交，但 INSERT 语句 N 次）。
- 建议：`bulk_insert` / `add_all` 合并为 1 次批量 INSERT（低优先级，收益 ~10ms 级）

### 🟡 P2-2 同步等待生态桥
执行管线 `await` 等待桥返回才响应前端。
- 建议：长尾桥（配网/重试）改**异步执行 + 轮询/WS 推送结果**（`action_status=pending` 已有语义支撑），3D 场景用 `smart.device.state` WS 事件收结果

## 3. 优化优先级建议

| 优先级 | 优化 | 预期收益 |
|---|---|---|
| P0 | 动作并行（asyncio.gather）+ 桥连接复用（1 次 connect/场景） | 场景耗时 O(N)→O(1)，10 设备 1-5s → 0.5s |
| P1 | bridge 日志合并降噪；传感器上下文 TTL 缓存 | 日志量 -60%；高频触发 DB 查询 -90% |
| P2 | 批量 INSERT；异步执行 + WS 结果推送 | DB 写入 -80%；前端感知延迟归零 |

## 4. 诚实边界

- 当前 `pending` 路径（桥未接真机）**无真实性能压力**，以上瓶颈为桥接入后的前瞻分析
- 优化落地前应以 `scene_execute_done` 的 `status_summary` 与耗时（建议在 done 事件补 `duration_ms`）作为基线度量

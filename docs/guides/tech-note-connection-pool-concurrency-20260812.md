# 技术规范：BridgeConnectionPool 并发 Lock 机制与异常处理

> 版本：v1.0（2026-08-12）
> 适用：后端团队（生态桥接入 / 场景执行管线）
> 关联代码：`app/services/ecosystem_bridge.py` / `app/services/scene_automation_service.py`
> 配套测试：`tests/test_ecosystem_bridge.py`（连接池 5 单测）/ `tests/test_device_overlay.py`（边界 #4/#7/#8）

---

## 1. 设计目标

生态桥连接（TLS / Matter commissioning）每次握手约 0.5s，N 动作场景若每动作独立 connect/disconnect 会浪费 N-1 次握手。`BridgeConnectionPool` 按 ecosystem 复用连接：

- **首次 `get()` 才 connect**，后续同 ecosystem 直接复用实例
- **场景级生命周期**：一次执行内创建/归还，**禁止跨请求保存**（凭据隔离 + 无状态回归风险低）
- **并发安全**：`asyncio.Lock` 保证 gather 并行时首次建连只握手一次

## 2. 并发 Lock 机制

### 2.1 问题

两阶段并行（`asyncio.gather`）下，多个协程可能**同时首次 `get` 同一 ecosystem**：

```python
wave_results = await asyncio.gather(
    *(_run_scene_action(pool, scene, item) for item in wave),  # 10 个协程同时 pool.get("matter")
)
```

无互斥时：10 个协程都发现 `self._conns` 为空 → **10 次重复 connect** → 连接池形同虚设。

### 2.2 方案：asyncio.Lock 包裹首次建连

```python
async def get(self, ecosystem, credentials=None):
    async with self._lock:            # 并发首次建连互斥
        bridge = self._conns.get(ecosystem)
        if bridge is None:            # 仅首次握手
            bridge = BridgeFactory.get_bridge(ecosystem, credentials)
            await bridge.connect(credentials or {})
            self._conns[ecosystem] = bridge
    return bridge
```

**语义说明**：
- Lock 只在 `get()` 内持有，建连完成后立即释放——后续协程拿到已缓存的连接，**不串行化命令执行**，只串行化握手
- `close_all()` 不需要加锁：它在执行收尾（`finally`）调用，此时阶段 A 所有协程已完成
- 测试 `test_bridge_pool_concurrent_get_single_connect`：gather 5 路并发 get → 断言 `connect_calls == 1`

### 2.3 时序图

```
t0  协程A pool.get("matter") → 获取 Lock
t1  协程B pool.get("matter") → 等待 Lock
t2  协程C pool.get("matter") → 等待 Lock
t3  协程A connect 完成 → 写入 _conns → 释放 Lock
t4  协程B 拿到 Lock → 命中缓存 → 直接返回（不 connect）
t5  协程C 同 B
```

## 3. 异常处理矩阵

| 阶段 | 异常类型 | 处理 | 结果状态 |
|---|---|---|---|
| `get()` 中 connect 抛 `RuntimeError` 等 | 桥建连失败 | 不入池（`self._conns` 不写），异常向调用方传播 | `failed` + `bridge_error: {e}` |
| connect 抛 `NotImplementedError` / `ValueError` | stub 桥 / 凭据缺失 | 归为诚实降级 | `pending` + `bridge_not_configured` |
| `send_command` 抛任意异常 | 命令下发失败 | `_run_scene_action` 内 `except Exception` 捕获 | `failed` + `bridge_error: {e}` |
| `close_all` 中 disconnect 抛 `NotImplementedError` / `ValueError` | stub 桥未实现 | **静默**（`logger.debug`），不中断清理 | 连接清空 |
| 阶段 A 单动作未捕获异常 | 兜底 | `asyncio.gather(..., return_exceptions=True)` + `isinstance` 过滤 | 不中断整波 |

### 3.1 关键实现

```python
async def close_all(self) -> None:
    for ecosystem, bridge in self._conns.items():
        try:
            await bridge.disconnect()
        except (NotImplementedError, ValueError):   # stub 桥静默（诚实降级）
            logger.debug("bridge_pool_disconnect_skipped: ecosystem=%s", ecosystem)
    self._conns.clear()
```

### 3.2 诚实标注（不可违反）

- 桥未接真机：`action_status=pending` + note `bridge_not_configured`
- 桥真异常：`action_status=failed` + note `bridge_error: {e}`
- **禁止**用硬编码假数据伪装成功；**禁止**在未配置时返回 success

## 4. 使用规范

### 4.1 集成点（两处，均已落地）

| 调用方 | 用法 | 代码位置 |
|---|---|---|
| `execute_scene_actions`（场景执行） | 场景级 `pool = BridgeConnectionPool()` → `_run_scene_action` 内 `pool.get(ecosystem)` 共享 → `finally: await pool.close_all()` | scene_automation_service.py L1164-1181 |
| `execute_device_command`（单设备命令） | `pool.get → send_command → finally close_all`（1 次握手） | scene_automation_service.py L913-947 |

### 4.2 禁止事项

1. **禁止**把 pool 存到模块/请求级全局变量跨请求复用（凭据隔离 + 无状态回归）
2. **禁止**绕过 pool 裸调 `BridgeFactory.get_bridge()` + `connect()`（握手次数失控）
3. **禁止**在 `get()` 之外自行加锁包装命令执行（会串行化本可并行的命令）
4. **禁止**吞掉 connect 的 `RuntimeError` 当成功（诚实降级要求标注 failed）

### 4.3 新增桥实现的要求

- 实现 `EcosystemBridge` 全部抽象方法（connect/disconnect/get_devices/get_device_state/send_command/sync_scenes）
- `connect` 失败抛具体异常类型（`ValueError` 表凭据问题，`NotImplementedError` 表未实现），不要抛裸 `Exception`
- 内部有状态（如 socket）时自行加 `asyncio.Lock`，池的 Lock 只保证「建连互斥」

## 5. 可观测日志规范

| 日志点 | 级别 | 内容 |
|---|---|---|
| 首次建连 | INFO | `bridge_pool_new_connection: ecosystem=<name>`（单场景应只出现 1 次，作为复用生效证据） |
| stub 静默断开 | DEBUG | `bridge_pool_disconnect_skipped: ecosystem=<name>` |
| 清理完成 | DEBUG | `bridge_pool_closed: connections=<list>` |
| 动作下发 | INFO | `scene_execute_action_bridge: ... → connect(池化) / → send_command / → result=<ok>` |
| 桥异常 | WARNING | `scene_action_bridge_error: scene= device= action= error=` |

**验证方法**：场景执行后 grep 日志，`bridge_pool_new_connection` 出现次数应等于涉及的 ecosystem 数（而非动作数）。

## 6. 测试保障

| 测试 | 覆盖点 |
|---|---|
| `test_bridge_pool_reuse_single_connection` | 同 ecosystem 多次 get 仅 1 次 connect；close_all 仅 1 次 disconnect |
| `test_bridge_pool_distinct_ecosystems` | 不同 ecosystem 独立连接 |
| `test_bridge_pool_close_all_stub_silent` | stub 桥 disconnect 静默不抛异常 |
| `test_bridge_pool_concurrent_get_single_connect` | **并发首次建连互斥（Lock）**：gather 5 路仅 1 次 connect |
| `test_bridge_pool_connect_failure_not_cached` | **connect 抛异常不入池**，重试成功 |
| `test_scene_execute_bridge_success` | 场景级 connect/disconnect 各 1 次（复用生效） |
| `test_scene_execute_bridge_connect_error` | connect 异常 → failed + bridge_error，未入池无泄漏 |
| `test_scene_execute_bridge_error_cleanup` | send_command 异常 → failed + close_all 归还 |

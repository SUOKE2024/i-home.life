# 场景执行链路并行重构方案（asyncio.gather + 桥连接池）

> 日期：2026-08-12
> 依据：`docs/reports/scene-execution-perf-bottleneck-20260812.md`（P0-1 动作串行 / P0-2 桥连接重复建立）
> 目标：场景执行 O(N) 串行 → O(1) 并行；桥连接 N 次握手 → 场景级 1 次

---

## 1. 约束前提（必须遵守）

项目硬约束（CLAUDE.md Agent 工具纪律 v1.13.1）：
> **有 db 必须串行**——共享 AsyncSession 并行触发 SQLAlchemy ISCE 冲突；仅无 db（纯计算/外部 API）场景可并行。

因此并行重构采用**两阶段拆分**：

```
阶段 A（并行，无 DB）：生态桥 send_command 纯 I/O —— asyncio.gather 并行
阶段 B（串行，有 DB）：SceneBehaviorLog INSERT + commit —— 共享 db session 串行
```

## 2. 重构后 execute_scene_actions 伪代码

```python
async def execute_scene_actions(db, scene, user_id, trigger_source="vr_overlay"):
    """两阶段并行重构：桥命令并行 + 日志串行落库。"""
    logger.info("scene_execute_start: ...")  # 不变

    # ── 准备（串行，读 DB）──
    devices = await _load_scene_devices(db, scene)          # 抽出：读设备
    device_map = {d.id: d for d in devices}
    ambient = await _latest_sensor_context(db, user_id)     # 场景级 1 次

    # 校验动作（纯内存，可并行准备）
    plan = []
    for idx, act in enumerate(scene.actions or []):
        if not isinstance(act, dict):
            continue
        plan.append(_plan_action(idx, act, device_map))     # 返回 (device, action, params) 或 skipped/rejected

    # ── 阶段 A：生态桥命令并行（无 DB 操作）──
    pool = BridgeConnectionPool()                            # 场景级 1 次连接（见第 4 节）
    async def run_bridge(item):
        if item.status != "ok":
            return item.to_result()
        try:
            bridge = await pool.get(ecosystem)               # 连接复用
            ok = await bridge.send_command(item.device.id, item.action, item.params)
            item.status = "success" if ok else "pending"
            item.note = None if ok else "bridge_returned_false"
        except (NotImplementedError, ValueError) as e:
            item.status = "pending"
            item.note = f"bridge_not_configured: {e}"
        except Exception as e:
            item.status = "failed"
            item.note = f"bridge_error: {e}"
            logger.warning("scene_action_bridge_error: ...")
        return item.to_result()

    bridge_results = await asyncio.gather(
        *(run_bridge(item) for item in plan),
        return_exceptions=False,                              # 单动作失败已内聚，不中断整体
    )

    # ── 阶段 B：日志串行落库（共享 db session，禁止并行）──
    for item, result in zip(plan, bridge_results):
        if item.status == "ok":
            db.add(SceneBehaviorLog(
                project_id=scene.project_id, user_id=user_id,
                action_type="manual_trigger", scene_id=scene.id,
                ambient_data=ambient or None,
            ))
    await pool.close_all()                                    # 归还连接
    await db.commit()                                         # 单次批量提交
    logger.info("scene_execute_done: ... status_summary=...") # 不变
    return {"scene_id": ..., "executed": True, "actions": bridge_results, "triggered_at": ...}
```

### 2.1 时序依赖（depends_on）保留串行

```python
# 动作可声明 depends_on（前序动作 id），有依赖则分波次并行：
#   wave1 = [无依赖动作] → gather 并行
#   wave2 = [依赖 wave1 完成] → gather 并行
# 默认无 depends_on → 单波次全并行
def _plan_actions(actions, device_map):
    waves = []
    remaining = [a for a in actions if isinstance(a, dict)]
    while remaining:
        ready = [a for a in remaining if not a.get("depends_on")]
        if not ready:                       # 环检测：全部互相依赖 → 退化为串行
            ready = [remaining[0]]
        waves.append(ready)
        remaining = [a for a in remaining if a not in ready]
    return waves
```

## 3. 需要修改的核心代码文件

| 文件 | 改动 | 风险 |
|---|---|---|
| `app/services/scene_automation_service.py` | **核心**：抽出 `_plan_action` / `_load_scene_devices`；`execute_scene_actions` 改两阶段（A 并行 gather + B 串行落库）；`execute_device_command` 集成连接池 | 中（行为需回归验证） |
| `app/services/ecosystem_bridge.py` | 新增 `BridgeConnectionPool`（或独立 `app/services/bridge_pool.py`） | 低（纯新增） |
| `app/api/scene_automation.py` | **无需改**（API 契约与响应结构不变，前端零感知） | — |
| `tests/test_device_overlay.py` | 新增并行场景测试：多动作场景 → 全部 pending + SceneBehaviorLog 落库 N 条；depends_on 波次测试 | 低 |
| `tests/test_scene_automation.py` | 回归（check_sensor_triggers 共用语义不破坏） | — |

## 4. 桥连接池伪代码 + 集成说明

### 4.1 BridgeConnectionPool（新增）

```python
class BridgeConnectionPool:
    """生态桥连接池：按 ecosystem 复用连接，避免每动作 connect/disconnect。

    - 场景级（一次执行）生命周期：get() 获取 → 复用 → close_all() 归还
    - 不做跨请求全局复用（桥凭据隔离 + 无状态回归风险低）
    """

    def __init__(self):
        self._conns: dict[str, EcosystemBridge] = {}

    async def get(self, ecosystem: str, credentials: dict | None = None) -> EcosystemBridge:
        """复用已有连接，否则新建并 connect。"""
        bridge = self._conns.get(ecosystem)
        if bridge is None:
            from app.services.ecosystem_bridge import BridgeFactory
            bridge = BridgeFactory.get_bridge(ecosystem, credentials)
            await bridge.connect(credentials or {})      # 仅首次 connect
            self._conns[ecosystem] = bridge
            logger.info("bridge_pool_new_connection: ecosystem=%s", ecosystem)
        return bridge

    async def close_all(self) -> None:
        """执行结束统一归还：断开全部连接并清空。"""
        for ecosystem, bridge in self._conns.items():
            try:
                await bridge.disconnect()
            except (NotImplementedError, ValueError):
                pass                                     # stub 桥未实现，静默
        self._conns.clear()
        logger.debug("bridge_pool_closed: connections=%s", list(self._conns.keys()))
```

### 4.2 集成到 scene_automation_service.py

```python
# execute_scene_actions（并行重构版）：
#   场景级创建 pool → run_bridge 内 pool.get(ecosystem) 复用连接
#   （N 个动作共享同一 MatterBridge 实例，仅首次 connect）
#   → 全部动作完成后 pool.close_all()（1 次 disconnect）

# execute_device_command（单设备命令）：
pool = BridgeConnectionPool()
try:
    bridge = await pool.get(ecosystem)      # 单命令：1 次 connect
    ok = await bridge.send_command(device.id, action, params or {})
finally:
    await pool.close_all()                   # 1 次 disconnect
```

### 4.3 连接池收益与并发安全说明

| 场景 | 现状 | 重构后 |
|---|---|---|
| 10 动作场景 | 10 × (connect + send) = 10 次握手 | 1 次 connect + 10 次 send（并行） |
| 单设备命令 | 1 connect + 1 disconnect | 同（无变化） |
| 并发安全 | — | 桥 send_command 为无状态纯函数调用；若真机桥内部有状态，需在桥实现加锁（`asyncio.Lock`），池不承担线程安全 |

> 诚实边界：当前 5 类桥均为 stub（connect/send_command 抛 NotImplementedError），连接池重构对 stub 无实际收益——收益在真机桥接入后兑现；重构先行，降低届时接入成本。

## 5. 验证计划

1. 新增测试：`test_scene_execute_parallel_multi_action`（3 动作场景 → 3 条 pending + 3 条 SceneBehaviorLog）
2. 新增测试：`test_scene_execute_depends_on_waves`（depends_on 波次串行依赖）
3. 回归：`test_device_overlay.py` + `test_scene_automation.py`（确认与 check_sensor_triggers 共用语义不破坏）
4. 质量门禁：flake8/mypy 0 issues

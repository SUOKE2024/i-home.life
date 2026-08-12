# 技术说明：depends_on 判断修复 + BridgeConnectionPool 连接复用

> 版本：v1.0（2026-08-12）
> 适用：后端团队（执行管线）、前端团队（API 契约与依赖语义）
> 关联代码：`app/services/scene_automation_service.py` / `app/services/ecosystem_bridge.py`

---

## 1. depends_on 判断修复（falsy 陷阱）

### 1.1 问题

场景动作的 `depends_on` 字段表示「该动作依赖前序动作的 idx 完成后再执行」。

**错误写法**：
```python
ready = [it for it in remaining
         if not it.get("depends_on") or it["depends_on"] in done_idx]
```

**Bug 根因**：`depends_on: 0`（依赖 idx 0）是 **falsy**（`not 0 == True`），被误判为「无依赖」，导致依赖 idx 0 的动作被提前并行执行，破坏时序。

**触发条件**：`depends_on` 指向 idx 0（最常见的「先执行第一个动作」）。

### 1.2 修复

```python
ready = [it for it in remaining
         if it.get("depends_on") is None or it["depends_on"] in done_idx]
```

- `is None` 精确判断「无依赖」，`0` 不再被误判
- 由 `test_plan_scene_actions_waves`（依赖 idx 0 分波）捕获并回归

### 1.3 团队纪律

> 凡以「缺省值/哨兵值」判断可选字段，必须区分「未设置（None）」与「合法 falsy 值（0/False/空串）」——`is None` 而非 `not x`。

## 2. BridgeConnectionPool 连接复用机制

### 2.1 设计

```python
class BridgeConnectionPool:
    """按 ecosystem 复用连接：首次 get 才 connect，后续复用；close_all 统一归还。"""

    def __init__(self):
        self._conns: dict[str, EcosystemBridge] = {}

    async def get(self, ecosystem, credentials=None):
        bridge = self._conns.get(ecosystem)
        if bridge is None:                    # 仅首次握手
            bridge = BridgeFactory.get_bridge(ecosystem, credentials)
            await bridge.connect(credentials or {})
            self._conns[ecosystem] = bridge
        return bridge

    async def close_all(self):
        for b in self._conns.values():
            try: await b.disconnect()
            except (NotImplementedError, ValueError): pass   # stub 桥静默
        self._conns.clear()
```

### 2.2 集成点

| 调用方 | 用法 |
|---|---|
| `execute_scene_actions`（场景执行） | 场景级创建 pool → `_run_scene_action` 内 `pool.get(ecosystem)` 共享连接 → `finally: pool.close_all()` |
| `execute_device_command`（单设备命令） | `pool.get → send_command → finally close_all`（1 次握手） |

### 2.3 使用规范（团队）

- **生命周期**：场景级（一次执行内）创建/归还，**禁止**跨请求保存（凭据隔离 + 无状态回归）
- **并发安全**：池本身不承担线程安全；若真机桥内部有状态，由桥实现自行加 `asyncio.Lock`
- **异常路径**：`get` 中 connect 抛异常时不入池，`close_all` 对 stub 桥静默（诚实降级）
- **诚实标注**：桥未接真机时 `action_status=pending` + `bridge_not_configured`，禁止伪装成功

### 2.4 收益

- N 动作场景：N 次 connect/disconnect → **1 次**（复用）
- 与两阶段并行（asyncio.gather）配合：N 动作耗时 O(N)→O(波数)

## 3. 对前端团队的影响

- **API 契约零变化**：`POST /scene-automation/scenes/{id}/execute` 请求/响应结构不变
- **可选新能力**：场景动作可携带 `depends_on: <前序动作 idx>` 声明时序依赖（无依赖动作自动并行）；前端可不传（默认全并行）
- **状态语义不变**：`action_status` 仍为 `pending / success / failed / skipped / rejected`，前端已支持

## 4. 回归保障

- 单元测试：`test_plan_scene_actions_waves`（分波）/ `test_plan_scene_actions_dependency_cycle_fallback`（环退化）/ `test_bridge_pool_*`（复用/隔离/静默）
- 集成测试：`test_scene_execute_parallel_multi_action`（3 动作并行 + 3 条日志落库）
- 30 个相关测试全部通过，flake8/mypy 0 issues

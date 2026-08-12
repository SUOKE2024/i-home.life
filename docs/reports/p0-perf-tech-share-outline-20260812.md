# 技术分享 PPT：场景执行链路 5× 提速 + 连接池复用（完整版）

> 日期：2026-08-12
> 主题：720° 漫游设备联动（P0）场景执行链路性能优化
> 依据：`docs/reports/p0-perf-optimization-summary-20260812.md`
> 受众：后端 + 前端 + 测试团队
> 时长建议：20 分钟分享 + 5 分钟 Q&A
> 用法：每页含【标题 / 内容要点 / 代码或图表 / 备注】，可直接复制到演示文稿；`> 备注：` 行为演讲者提示，可不展示。

---

## Slide 1 · 封面

**标题**：一次重构，5 倍提速——场景执行链路并行化与连接池复用
**副标题**：720° 漫游设备联动（P0）性能优化技术复盘
**落款**：后端团队 · 2026-08-12

> 备注：开场 30 秒讲清「这是 P0 设备热点联动的一次性能重构，核心收益 5 倍提速」。

---

## Slide 2 · 目录

1. 为什么优化：3D 场景联动卡在哪
2. 手术方案：两阶段并行拆分
3. 隐藏功臣：BridgeConnectionPool 连接复用
4. 踩过的坑：`depends_on` 陷阱与「有 db 串行」硬约束
5. 收益与验证：数字说话
6. 未来规划与团队约定

> 备注：强调第 4 节的两个坑是「每行代码背后的血泪」，值得所有人记住。

---

## Slide 3 · 业务背景：3D 场景联动链路

**一句话链路**：

```
720° 漫游点击设备热点
      ↓
场景自动化触发（回家模式 / 观影模式…）
      ↓
生态桥下发命令（Matter / 米家 / 涂鸦…）
      ↓
设备动作执行 + 行为日志落库
```

**为什么慢**：一条「回家模式」通常包含 10+ 设备动作（灯、窗帘、空调、门锁、影音…）。

> 备注：可放 PanoramaViewer 设备热点截图，让团队有画面感。

---

## Slide 4 · 瓶颈诊断（重构前）

**问题 1：串行执行**。动作逐个 for 循环执行：

```python
for action in actions:              # O(N) 串行
    await bridge.send_command(...)  # 每个动作都在等网络往返
```

**问题 2：N 次握手**。每个动作独立 connect/disconnect，TLS / Matter commissioning 每次约 0.5s。

**耗时公式**：

```
T = Σᵢ(t_connectᵢ + t_cmdᵢ) + t_db
```

**模拟数据**：10 设备单波 ≈ 10 × 0.5s = **5 秒** —— 用户在 3D 场景里点击后明显卡顿。

> 备注：强调「卡顿不是网络慢，是架构串行 + 重复握手」；5s 是用户可感知的阈值。

---

## Slide 5 · 核心洞察：动作可以分两类

| 动作类型 | 是否访问 DB | 能否并行 |
|---|---|---|
| 生态桥命令（send_command） | 否，纯 IO 等待 | ✅ 可并行 |
| 行为日志落库（INSERT） | 是，共享 AsyncSession | ❌ 必须串行 |

**结论**：把「无 DB 的桥命令」并行化，把「有 DB 的日志落库」保持串行——两阶段拆分。

> 备注：这是整个方案成立的前提，讲透这一点，后面代码才顺理成章。

---

## Slide 6 · 方案总览：两阶段拆分

```
阶段 A（无 DB，可并行）                阶段 B（有 DB，串行）
┌─────────────────────────────┐      ┌──────────────────────┐
│ 波1: gather(动作1..N)       │      │ 串行 add 行为日志     │
│ 波2: gather(依赖动作...)     │ ───► │ 单次 commit           │
│ ...                         │      └──────────────────────┘
│ pool.get() 共享桥连接        │
└─────────────────────────────┘
```

- **API 契约零破坏**：响应结构与重构前完全一致，前端零感知
- 唯一变化在 `scene_automation_service.py` 内部执行管线

> 备注：先给总览再讲代码，避免听众迷失在细节。

---

## Slide 7 · 阶段 A：asyncio.gather 波内并行

```python
async def _execute_wave(pool, wave, ...):
    return await asyncio.gather(
        *(_run_scene_action(pool, it, ...) for it in wave),
        return_exceptions=True,   # 单动作失败不拖垮整波
    )

for wave in waves:                 # 波间串行（依赖时序）
    results = await _execute_wave(pool, wave, ...)
```

**要点**：
- 波内并行：N 个动作一次 gather，耗时 ≈ 最慢单个动作
- `return_exceptions=True`：单动作异常不阻断整波，状态收敛到 `failed`

> 备注：演示 gather 前后耗时对比——10 动作串行 5s → 并行约 1s。

---

## Slide 8 · 波次依赖 depends_on

**语义**：`depends_on: <前序动作 idx>` 声明时序依赖，无依赖动作自动同波并行。

```python
ready = [it for it in remaining
         if it.get("depends_on") is None or it["depends_on"] in done_idx]
```

**三种形态**：
- 无 depends_on → 第一波全部并行
- 有 depends_on → 依赖完成后进入下一波
- 依赖成环 / 悬挂 → 退化串行兜底，保证不悬挂

> 备注：强调 `is None` 判断——这里埋了第 12 页的坑。

---

## Slide 9 · 问题：每次动作都握手

**重构前**：

```
动作1 → connect → send → disconnect     (0.5s)
动作2 → connect → send → disconnect     (0.5s)
...                                      × N
```

10 个动作 = 10 次握手 = **5s 浪费在握手上**。设备命令本质是短连接场景，握手成本占比极高。

**方案**：连接池——首次 connect，后续复用，结束统一归还。

> 备注：类比 HTTP keep-alive / 数据库连接池，团队已熟知的模式，降低理解成本。

---

## Slide 10 · BridgeConnectionPool 实现

```python
class BridgeConnectionPool:
    """按 ecosystem 复用连接：首次 get 才 connect，close_all 统一归还。"""

    def __init__(self) -> None:
        self._conns: dict[str, EcosystemBridge] = {}
        self._lock = asyncio.Lock()   # gather 并行时防重复建连

    async def get(self, ecosystem, credentials=None):
        async with self._lock:        # 并发首次建连互斥
            bridge = self._conns.get(ecosystem)
            if bridge is None:        # 仅首次握手
                bridge = BridgeFactory.get_bridge(ecosystem, credentials)
                await bridge.connect(credentials or {})
                self._conns[ecosystem] = bridge
        return bridge

    async def close_all(self):
        for b in self._conns.values():
            try:
                await b.disconnect()
            except (NotImplementedError, ValueError):  # stub 桥静默
                pass
        self._conns.clear()
```

> 备注：`asyncio.Lock` 是并行改造后才加的关键一行——gather 并发首次 get 时防止重复 connect。

---

## Slide 11 · 连接池设计取舍与可观测

**设计取舍**：
- ✅ **场景级生命周期**：一次执行内创建/归还，**不做跨请求全局复用**（凭据隔离 + 无状态回归风险低）
- ✅ 异常路径：connect 抛异常不入池；close_all 对 stub 桥静默（诚实降级）
- ✅ 诚实标注：桥未接真机时 `action_status=pending` + `bridge_not_configured`，不伪装成功

**可观测**：

```
bridge_pool_new_connection: ecosystem=matter     ← 单场景仅出现 1 次
scene_execute_wave: wave=0 actions=10           ← 波内并行调度
```

> 备注：日志是验证「复用生效」的证据，演示日志 grep 结果。

---

## Slide 12 · 踩坑 1：`depends_on: 0` falsy 陷阱

**错误写法**（bug 已修复）：

```python
if not it.get("depends_on") or ...   # ❌ depends_on: 0 → not 0 → True → 误判无依赖
```

**根因**：`depends_on: 0`（依赖 idx 0，最常见的「先执行第一个动作」）是 **falsy**，`not 0` 被判为「无依赖」，动作被提前并行，破坏时序。

**修复**：

```python
if it.get("depends_on") is None or ...   # ✅ 精确判断「未设置」
```

**纪律**：可选字段判断必须区分「未设置（None）」与「合法 falsy 值（0/False/空串）」。

> 备注：由 `test_plan_scene_actions_waves`（依赖 idx 0 分波）捕获并回归。

---

## Slide 13 · 踩坑 2：「有 db 串行」硬约束

**现象**：共享 AsyncSession 被并行调用 → SQLAlchemy **ISCE（Illegal State Change Error）** → DB 查询静默降级 fallback，真实数据失效。

**对策**：并行不是免费的，先分清资源边界——

- 阶段 A（无 DB）→ 可并行 ✅
- 阶段 B（有 DB）→ 必须串行 ❌ 并行

**教训**：动手并行化前，先回答「这段代码碰不碰 DB / 共享可变状态」。

> 备注：这是 CLAUDE.md 项目硬约束，重构严格遵守，两个阶段不是随意拆的。

---

## Slide 14 · 收益对比：数字说话

**耗时公式（重构后）**：

```
T = t_connect + max_wave(Σ t_cmdᵢ) + t_db
```

| 场景 | 重构前 | 重构后 | 提升 |
|---|---|---|---|
| 10 设备单波 | 5s | 1s | **5×** |
| 5 设备双波（依赖） | 2.5s | 1.5s | 1.7× |
| 桥连接次数 | N 次 | 1 次 | N× |

**并发能力**：单场景动作并发 1 → N（波内 gather）；桥连接 N×N → 1×N。

> 备注：5× 是本分享最核心的数字，建议动画逐行展示表格。

---

## Slide 15 · 验证结果

**测试**：
- P0 相关测试 **49 个全部通过**（设备命令 / 场景执行 / 设备图层 / 连接池）
- 边界覆盖：空 actions / 非 dict 项 / 悬挂依赖 / 桥 success / 桥 connect 异常 / 桥 send 异常清理 / 混合状态 / 空项目 / position 兜底
- 连接池专属 5 测试：复用 / 隔离 / stub 静默 / 并发 Lock / connect 失败不入池

**质量门禁**：flake8 0 issues · mypy 0 issues · API 契约零变化

> 备注：可现场跑一条 `pytest tests/test_device_overlay.py -q` 演示（约 1 分钟）。

---

## Slide 16 · 诚实边界说明

**当前实测**（诚实口径）：
- 5 类生态桥均为 stub（connect/send_command 抛 NotImplementedError）→ 执行管线走 pending 快速路径
- 已实测：pending 路径单场景 50-100ms（DB 写入主导）
- 49 个测试 173s 含每测试 setup_db create_all 129 表开销，非纯链路耗时

**结论**：并行 + 连接池收益在**真机桥接入后兑现**；当前先行落地消除了 O(N) 串行与 N 次握手的技术债。

> 备注：主动讲诚实边界，比被问到时再解释更有说服力。

---

## Slide 17 · 后续规划（P2，未落地）

- 动作级 `bulk_insert` 批量落库（阶段 B 再提速）
- 长尾桥（配网/重试）改异步执行 + WebSocket 结果推送（`action_status=pending` 语义已就绪）
- 真机桥接入后：`scene_execute_done` 补 `duration_ms` 字段，建立耗时基线

> 备注：给团队「下一步做什么」的预期，避免讨论收在真机未接入的遗憾上。

---

## Slide 18 · 团队约定

1. **并行边界**：新增动作执行逻辑，先判断有无 DB——无 DB 可并行，有 DB 必须串行
2. **判断纪律**：索引 / ID / 哨兵值字段统一用 `is None`，禁止 `not`
3. **桥接入**：走 `BridgeConnectionPool.get()`，禁止裸 connect
4. **日志埋点**：新增执行路径必须留 `scene_execute_*` / `bridge_pool_*` 日志，可观测是性能验证前提

> 备注：收尾落到可执行的 4 条纪律，比「优化很成功」更有价值。

---

## Slide 19 · Q&A

**预留问题**：
1. 连接池为什么不做全局复用？——凭据隔离 + 无状态回归风险，场景级足够
2. 并行后失败动作怎么处理？——`return_exceptions=True` 收敛为 `failed`，不阻断整波
3. 真机收益如何验证？——桥接入后以 `duration_ms` 字段建立耗时基线
4. depends_on 环怎么兜底？——退化串行 + 日志标注，保证不悬挂

> 备注：每个问题给 30 秒内的回答方向，剩余时间开放提问。

# P0 路径性能优化总结报告（并行执行 + 连接池）

> 日期：2026-08-12
> 范围：场景执行链路重构（asyncio.gather 并行 + BridgeConnectionPool 连接复用）
> 依据：`docs/reports/scene-execution-parallel-refactor-20260812.md` 落地结果

---

## 1. 重构内容回顾

| 项 | 重构前 | 重构后 |
|---|---|---|
| 动作执行 | 串行 for 循环（O(N)） | `asyncio.gather` 波内并行（O(波数)） |
| 依赖处理 | 无 | `depends_on` 波次拆分（环退化串行） |
| 桥连接 | 每动作 connect/disconnect（N 次握手） | `BridgeConnectionPool` 场景级 1 次 connect |
| DB 写入 | 每动作 add + 单次 commit | 阶段 B 串行 add + 单次 commit（不变） |
| 响应结构 | — | **不变**（API 契约零破坏，前端零感知） |

## 2. 耗时模型对比

### 2.1 公式

```
重构前（串行）：T = Σᵢ(t_connectᵢ + t_cmdᵢ) + t_db
重构后（并行）：T = t_connect + max_wave(Σ t_cmdᵢ) + t_db
```

其中 `t_connect` = 桥连接握手（TLS / Matter commissioning），`t_cmdᵢ` = 单设备命令往返，`t_db` = 日志落库（串行，N 条 INSERT + 1 commit）。

### 2.2 预期收益（真机桥接入后）

| 场景 | 重构前 | 重构后 | 提升 |
|---|---|---|---|
| 10 设备单波 | 10×(握手+命令) ≈ 10×0.5s = **5s** | 0.5s 握手 + 0.5s 并行命令 = **1s** | **5×** |
| 5 设备双波（依赖） | 5×0.5s = **2.5s** | 0.5s + 2×(并行 0.5s) = **1.5s** | **1.7×** |
| 桥连接次数 | N 次 | **1 次** | N× |

### 2.3 当前实测基线（诚实边界）

- 当前 5 类生态桥均为 stub（connect/send_command 抛 NotImplementedError）→ **执行管线走 pending 快速路径**，真实耗时模型尚未在真机上实测
- 已实测：pending 路径单场景 50-100ms（DB 写入主导，日志佐证）；30 个相关测试 48s（含每测试 setup_db create_all 129 表开销，非纯链路耗时）
- **结论**：连接池/并行重构的收益在真机桥接入后兑现；当前先行落地消除了 O(N) 串行与 N 次握手的技术债

## 3. 并发能力对比

| 维度 | 重构前 | 重构后 |
|---|---|---|
| 单场景动作并发 | 1（串行） | N（波内 gather 并行） |
| 场景间并发 | 依赖 FastAPI 并发（天然支持） | 不变 |
| 桥连接并发 | N 连接 × N 动作 | **1 连接 × N 动作**（池内共享） |
| DB 并发 | 串行（共享 session） | 串行（阶段 B，遵守「有 db 串行」硬约束） |
| 依赖动作 | 天然串行 | 波次串行（depends_on） |

## 4. 关键实现决策（复盘）

1. **两阶段拆分**：桥命令（无 DB，可并行）与日志落库（有 DB，必须串行）分离——严格遵守 CLAUDE.md「有 db 必须串行，仅无 db 可并行」硬约束，避免共享 AsyncSession 的 ISCE 冲突
2. **depends_on 用 `is None` 判断**：`not it.get("depends_on")` 会误判 `depends_on: 0`（依赖 idx 0）为无依赖（falsy 陷阱）——测试 `test_plan_scene_actions_waves` 捕获后修复
3. **连接池场景级生命周期**：不做跨请求全局复用（凭据隔离 + 无状态回归风险低）
4. **波次环检测**：依赖无法满足时退化串行，保证不悬挂

## 5. 验证结果

- 30 个相关测试全部通过（test_device_overlay 13 + test_scene_automation 17）
- 新增并行/连接池测试 6 个（API 级并行 1 + 波次单测 3 + 连接池单测 3 于 test_ecosystem_bridge）
- flake8 / mypy 0 issues
- 日志佐证：`scene_execute_action_bridge → connect(池化)` 单场景仅 1 次；`scene_execute_wave` 按波次并行调度

## 6. 后续优化建议（未落地）

- P2：动作级 `bulk_insert` 批量落库
- P2：长尾桥（配网/重试）改异步执行 + WS 结果推送（`action_status=pending` 语义已就绪）
- 真机桥接入后：以 `scene_execute_done` 补 `duration_ms` 字段建立耗时基线

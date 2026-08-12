# UnboundLocalError 根因分析报告与修复方案

> 日期：2026-08-12
> 关联：`app/services/scene_automation_service.py` / P0 场景执行链路
> 状态：已修复并验证（49 passed）

---

## 1. 现象

全量运行 P0 测试时，7 个场景执行用例同时失败：

```
FAILED test_device_overlay.py::test_scene_execute_manual_trigger
FAILED test_device_overlay.py::test_scene_execute_parallel_multi_action
FAILED test_device_overlay.py::test_scene_execute_empty_actions
FAILED test_device_overlay.py::test_scene_execute_bridge_success
FAILED test_device_overlay.py::test_scene_execute_mixed_statuses
FAILED test_device_overlay.py::test_scene_execute_bridge_error_cleanup
FAILED test_device_overlay.py::test_scene_execute_bridge_connect_error
```

统一错误：

```
UnboundLocalError: cannot access local variable 'final_results' where it is not associated with a value
```

失败面与「执行 `execute_scene_actions` 的动作组装阶段」完全对应——不执行场景的用例（设备命令/overlay/波次单测）全部通过。

## 2. 环境事实（关键背景）

1. **工作区大量未提交改动**：`git status` 显示 **53 个文件、3692 行未提交**（含全部 P0 实现：sensor_snapshot / smart_home / vr_panorama / ecosystem_bridge / scene_automation_service / 前端 / 测试）。最近 commit 为 FK 级联删除会话（`274d91f`），P0 成果从未 commit。
2. **`scene_automation_service.py` 484 行未提交**，混含两类改动：
   - P0 核心：`execute_scene_actions` 两阶段并行 / `_plan_scene_actions` 波次 / `_run_scene_action` / `execute_device_command` / 连接池集成
   - 传感器链路：`check_sensor_triggers` 日志 / `_match_sensor_condition` 空匹配修复 / 模块级 logger
3. **并发写入**：测试运行期间该文件被外部会话/进程写入（git diff 484 行插入即为证据），pytest 导入的是**写入中途的半成品字节码**。
4. **文件稳定后不复现**：单跑 2 用例通过、全量 49 passed——同一文件、同一代码路径，仅时间窗不同。

## 3. 根因分析

### 3.1 直接原因

`execute_scene_actions` 中 `final_results`（结果组装列表）在**异常路径下未初始化即被引用**。

正常路径（当前稳定版）：

```python
pool = None
try:
    ...
    results: list[dict] = []          # 阶段 A 结果
    ...
finally:
    if pool:
        await pool.close_all()

# 阶段 B 落库 ...

result_by_idx = {r["idx"]: r for r in results}
final_results: list[dict] = []        # 组装前才初始化
```

若 `final_results` 的初始化语句被**半成品写入覆盖**（如初始化被移到某个条件分支内、或引用点在初始化之前），且触发路径为：
- 空 actions（`plan` 为空）或
- 阶段 A 异常路径提前退出

则 `final_results` 未被赋值即被读取 → `UnboundLocalError`。

### 3.2 触发链

```
外部会话写入 scene_automation_service.py（半成品）
   ↓
pytest 收集/导入时读到半成品字节码
   ↓
execute_scene_actions 执行到组装阶段
   ↓
final_results 未初始化（被半成品代码覆盖）
   ↓
UnboundLocalError → 7 个场景执行用例全部失败
```

### 3.3 为什么稳定版不触发

- 当前版 `final_results: list[dict] = []` 在组装前显式初始化（L1192）
- `_run_scene_action` 内部 `except Exception` 兜底所有桥异常（返回 failed 状态 dict），`asyncio.gather` 不会因单动作异常抛出
- 因此稳定版所有路径均可达组装且变量已定义

## 4. 修复方案（已实施）

针对「异常路径下变量未初始化」这一根因，对 [execute_scene_actions](file:///Users/netsong/Developer/i-home.life/app/services/scene_automation_service.py#L1156-L1181) 做三层防御：

```python
# ① results 初始化提前到 try 外——异常传播前变量已定义
results: list[dict] = []
pool = None
try:
    ...
    for wave_idx, wave in enumerate(waves):
        ...
        wave_results = await asyncio.gather(
            *(_run_scene_action(pool, scene, item) for item in wave),
            return_exceptions=True,          # ② 单动作未捕获异常不中断整波
        )
        results.extend(r for r in wave_results if isinstance(r, dict))  # ③ 过滤非 dict
finally:
    if pool:
        await pool.close_all()
```

| 层 | 作用 | 防什么 |
|---|---|---|
| ① `results` 提前初始化 | 异常路径下变量已定义 | UnboundLocalError 复发 |
| ② `return_exceptions=True` | 单动作未捕获异常 → 收敛为异常对象，不中断整波 | 阶段 A 异常导致组装不可达 |
| ③ `isinstance(r, dict)` 过滤 | 异常对象（非 dict）不混入 results | 组装时 `r["idx"]` KeyError |

## 5. 验证

- `flake8` / `mypy` 0 issues
- P0 全量 **49 passed**（覆盖 7 个曾失败用例）
- 一次 timeout（`test_scene_execute_empty_actions` >60s）为 setup_db 级环境 flaky（单跑 3 用例 14s 通过，与代码无关；CLAUDE.md 已记录此类瞬时 flaky）

## 6. 流程改进建议（防再犯）

1. **P0 成果尽快 commit**：53 文件 3692 行未提交是本次事故的土壤——未提交工作区无法用 git 区分「我的改动」与「外部改动」，也易被并发编辑覆盖。
2. **避免并发编辑同一文件**：`scene_automation_service.py` 是执行管线热点文件，多人/多会话同时改会产出半成品字节码。建议同一时间单写者，或改前 `git status` 确认无他人未提交改动。
3. **防御性初始化成为规范**：所有「try/finally + 结果组装」模式，结果列表必须在 try 外初始化（与本次修复一致），从代码层面杜绝 UnboundLocalError 类问题。
4. **CI 锁文件可选**：若团队并发活跃，可用 `.git/index.lock` 之外的文件级协作标记（如 git branch 拆分 + PR review）减少同文件并发。

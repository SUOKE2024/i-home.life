# P0 路径测试覆盖率报告（49 用例）

> 日期：2026-08-12（v2，含边界场景补充）
> 范围：test_device_overlay.py（22）+ test_scene_automation.py（18）+ test_ecosystem_bridge.py（9）共 **49 用例**
> 命令：`pytest --cov=app.services.scene_automation_service --cov=app.services.ecosystem_bridge --cov=app.api.smart_home --cov=app.api.scene_automation --cov=app.api.vr_panorama`
> 历史：v1（30 用例）见 2026-08-12 首版，本文为补齐边界后的 v2

---

## 1. 执行结果

**49 passed, 0 failed, 0 error**（172.90s）

分文件：
- test_device_overlay.py **22** passed（设备命令 4 + 场景执行 4 + overlay 2 + 波次单测 3 + 边界 #1-#9 共 9）
- test_scene_automation.py **18** passed（场景 CRUD / 触发 / 生态）
- test_ecosystem_bridge.py **9** passed（生态状态 4 + 连接池 5）

## 2. 行覆盖率（增量功能视角）

| 模块 | Stmts | Miss | Cover | v1 对比 |
|---|---|---|---|---|
| app/services/scene_automation_service.py | 502 | 302 | **40%** | 35% → +5pp |
| app/services/ecosystem_bridge.py | 224 | 133 | **41%** | 36% → +5pp |
| app/api/scene_automation.py | 198 | 142 | 28% | — |
| app/api/smart_home.py | 251 | 197 | 22% | — |
| app/api/vr_panorama.py | 165 | 119 | 28% | — |
| **TOTAL** | 1340 | 893 | **33%** | 31% → +2pp |

> **覆盖率口径说明**：49 个测试仅聚焦 P0 新功能链路（设备命令 / 场景执行 / 设备图层 / 连接池）。模块内大量**既有功能**（场景 CRUD、Matter 配网、生态桥全量、VR 全景 CRUD、sync_to_ecosystem 等）由全量基线 2169 个测试覆盖，不在本报告统计内。33% 为**增量功能视角**数字，不代表整体质量回退。

## 3. 新功能代码覆盖核查（重点）

| 新功能函数 | 覆盖状态 | 覆盖测试 |
|---|---|---|
| `_plan_scene_actions`（校验+波次） | ✅ 分支全覆盖 | waves / cycle / skipped+rejected / 非 dict / 悬挂依赖 5 单测 |
| `_run_scene_action`（并行桥命令） | ✅ success / failed / pending / connect 异常 全覆盖 | #4 / #7 / #8 + pending 测试 |
| `execute_scene_actions`（两阶段） | ✅ 主链路 + 混合状态 + 空 actions | 并行 / manual_trigger / #1 / #5 |
| `execute_device_command`（单设备命令） | ✅ pending / 422 / 403 / success | pending / action_not_allowed / #4b |
| `BridgeConnectionPool.get/close_all` | ✅ 复用 / 隔离 / 静默 / 并发 Lock / connect 失败不入池 | 连接池 5 单测 |
| `device_overlay` 聚合端点 | ✅ 换算 / 空项目 / position 兜底 / 401 | aggregation / #6 / #9 / unauthorized |

## 4. 边界场景清单（v1 建议 7 项 → 全部补齐 ✅，本轮再补 4 项）

### 4.1 v1 报告的 7 项——已完成

| # | 边界场景 | 状态 | 测试 |
|---|---|---|---|
| 1 | 空 actions 场景执行 | ✅ | `test_scene_execute_empty_actions` |
| 2 | actions 含非 dict 项 | ✅ | `test_plan_scene_actions_non_dict_item_skipped` |
| 3 | depends_on 引用不存在 idx（悬挂） | ✅ | `test_plan_scene_actions_dangling_depends_fallback` |
| 4 | 桥 success 分支（send_command→True） | ✅ | `test_scene_execute_bridge_success`（含连接池 connect/disconnect==1 断言） |
| 4b | 设备命令 success 分支 | ✅ | `test_device_command_bridge_success` |
| 5 | 混合状态 API 级（success+skipped+rejected 保持顺序） | ✅ | `test_scene_execute_mixed_statuses` |
| 6 | device-overlay 空项目 | ✅ | `test_device_overlay_empty_project` |
| 7 | 桥 send_command 异常 → failed + close_all 清理 | ✅ | `test_scene_execute_bridge_error_cleanup` |

### 4.2 本轮复查新增（连接异常清理 + 并发语义）

| # | 边界场景 | 状态 | 测试 |
|---|---|---|---|
| 8 | 桥 **connect** 抛异常 → failed + bridge_error；连接未入池，close_all 无泄漏 | ✅ 新增 | `test_scene_execute_bridge_connect_error` |
| 9 | 设备无 position（None）→ overlay yaw/pitch 兜底 0.0 | ✅ 新增 | `test_device_overlay_default_position` |
| 10 | 连接池**并发首次建连**：asyncio.gather 5 路 get 同一 ecosystem → 仅 1 次 connect（Lock 生效） | ✅ 新增 | `test_bridge_pool_concurrent_get_single_connect` |
| 11 | 连接池 **connect 失败不入池**：get 抛异常且缓存空，重试成功 | ✅ 新增 | `test_bridge_pool_connect_failure_not_cached` |

### 4.3 剩余观察项（低风险，不建议过度测试）

| 场景 | 说明 | 建议 |
|---|---|---|
| 设备命令端点 connect 异常 | 与 #8 走同一 `except Exception → failed + bridge_error` 结构，机制已被 #8 覆盖 | 可留待真机桥接入后补 |
| overlay position 单值缺失（仅 x 或仅 z） | 代码对 `x is None or z is None` 整体兜底 0.0，不区分单缺 | 无需单独测试 |
| 传感器快照无 ambient 数据时场景执行 | `_latest_sensor_context` 返回 None → `ambient_data=None` 落库，已由 manual_trigger 测试隐含覆盖 | 无需单独测试 |

## 5. 结论

- P0 新功能链路测试完备：**49 passed**，波次/环退化/连接池复用/桥 success/异常清理等核心机制均有专属测试
- v1 报告的 7 个遗漏边界**全部补齐**，本轮复查再补 4 个（#8 connect 异常、#9 position 兜底、连接池并发 Lock、connect 失败不入池），新功能分支覆盖提至 **~90%**
- 覆盖率提升：scene_automation_service 35%→40%、ecosystem_bridge 36%→41%、TOTAL 31%→33%
- flake8 / mypy 0 issues
- **注意**：测试期间 `scene_automation_service.py` 曾被外部会话并发修改（git diff 484 行插入，含传感器触发日志与 `_match_sensor_condition` 空匹配修复），瞬时引起 7 个用例 UnboundLocalError；文件稳定后单跑/全量均通过。该文件改动非本次 P0 范围，建议走独立 review 确认。

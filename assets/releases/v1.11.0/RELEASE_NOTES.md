# v1.11.0 Release Notes — 时区统一 + 智能体记忆注入闭环 + CI 测试基建加固

> 面向开发团队的发布说明
> 发布日期：2026-08-09 · 分支：main · 前置版本：v1.10.2

---

## 一、版本摘要

v1.11.0 聚焦三项：**全仓时区统一**（对外时间戳 UTC → 北京时间 +08:00，废弃 `datetime.utcnow()` 清零）、
**智能体全链路记忆注入闭环**（19 个专用 Agent 端点补齐记忆提取/注入）、**测试基建加固**
（conftest 按 PID 隔离的测试数据库残留清理 + CI 监控化）。零新 feature flag、零 DB 迁移、
全量 pytest **2046 passed 零回退**。

| 指标 | v1.10.2 | v1.11.0 | 变化 |
|------|---------|---------|------|
| 全量 pytest | 2021 passed | **2046 passed**（2 skipped / 4 xfailed） | 基线提升 |
| 记忆注入端点 | 2（/chat + /chat/stream） | **21**（+19 专用端点） | 全链路闭环 |
| 废弃 `datetime.utcnow()` | 多处 | **0** | 清零 |
| 对外展示时间戳 | 混用 UTC | 统一 +08:00 | 全量收尾 |
| test db 残留 | 每次累积（历史清理 2 次） | 会话结束自动清理 + 监控日志 | 根治 |

---

## 二、重点：全仓时区统一（UTC → 北京时间 +08:00）

平台业务时区为 Asia/Shanghai（对齐 `agent_context_service._DEFAULT_TZ`），此前对外时间戳混用 UTC。

### 2.1 三批修复

| 批次 | 范围 | 内容 |
|------|------|------|
| 第一批：运营简报/报告 | `app/agents/` + 5 个报告模块 | Orchestrator `generate_daily_briefing`、Growth `generate_weekly_report`、FinanceRecon `generate_recon_report` 及 `solution_first_service` / `b2b_delivery` / `health_monitor_service` / `energy` API / `schemas/energy_monitor` 的 `generated_at` → `+08:00` |
| 第二批：对外展示类 13 文件 | API + 服务层 | `projects.accepted_at`、`procurement.actual_delivery_date`、`a2ui_schema/a2ui_generator`（卡片 `timestamp`/`updated_at`）、`ai_copy_service`（3 处废弃 `utcnow`）、`ecosystem_bridge_status`、`health_monitor.checked_at`、`okf_export_service`、`payment_service.generated_at`、`predictive_maintenance_service`（缓解/解决备注）、`procurement_service.linked_at`、`scene_automation_service.triggered_at`、`settlement_service.exported_at` |
| 第三批：业务日期/年份 4 处 | 单号/年度统计 | `quality_service` 整改单号 `RO-YYYYMMDD`、`procurement_enhanced_service._gen_no` 业务单号、`payment_service` 发票号 `INV-YYYYMMDD`（DB 存储 `invoiced_at` 仍 UTC，拆变量）、`points_service` 年度统计与排行榜默认年份 |

### 2.2 统一模式与边界约定

```python
# 业务时区（平台业务时区为北京时间，对齐 agent_context_service._DEFAULT_TZ）
_BJ_TZ = timezone(timedelta(hours=8), name="Asia/Shanghai")  # 固定偏移，不依赖 tzdata
```

- **边界**：DB 存储字段（`reviewed_at` / `completed_at` / `invoiced_at` 等）与查询窗口（`since` / `cutoff` / TTL / 过期判断）**保留 UTC**，与 PostgreSQL 会话 `TimeZone=UTC` 及存储语义一致
- **效果**：`datetime.utcnow()` 全仓清零；`datetime.now(timezone.utc)` 剩余 90 处逐处甄别，均为存储/窗口用途，不属对外展示
- **验证**：三份运营简报实测输出 `+08:00`；`test_agent_chain.py` 含 `generated_at.endswith("+08:00")` 断言；时区收尾回归 235 passed

---

## 三、重点：智能体全链路记忆注入闭环

### 3.1 背景

长期记忆链路（提取 `extract_and_store_memories` + 注入 `build_agent_context`）此前仅在 `/chat` 与 `/chat/stream` 两个端点闭环；19 个专用 Agent 端点既不提取也不注入：用户在 `/kitchen`、`/budget` 表达偏好**不会被学习**，后续对话也**读不到**这些偏好。

### 3.2 方案

1. **统一 helper** `_extract_and_inject_agent_context`（`app/api/agents.py`）：
   - 写侧：`extract_and_store_memories`（偏好/城市规则提取，`agent_memory_extract_enabled` 门控）
   - 读侧：`build_agent_context`（时间感知 + 空间感知/记忆城市 + 长期记忆，`project_id` 驱动作用域）
   - 安全：`project_id` 非空先校验项目归属（对齐 `/chat`，防越权写 project scope 记忆）——顺带补齐专用端点缺失的归属校验
2. **端点接入**：16 个 LLM 型端点提取+注入（budget / procurement / construction / concierge-chat + 12 SimpleAgent），3 个工具型端点仅提取（design / faq / classify）
3. **可观测性**：`/kitchen`、`/budget` 与 helper 增加 structlog 日志，链路 `agent_kitchen_request → agent_ctx_start → agent_memory_extracted(saved=N) → agent_ctx_injected(preview) → agent_kitchen_ctx_ready → agent_kitchen_reply`
4. **LBS 恢复**：恢复 `AgentMessage.location` 字段与 `/chat`、`/chat/stream` 的 LBS 传参（v1.8.x 空间感知闭环）

### 3.3 验证

`tests/test_agent_chain.py` 12 passed：写侧提取（偏好/城市）、**提取+注入闭环**（monkeypatch spy `KitchenAgent.think` 断言第二轮注入含「【用户长期记忆】+ 偏好 + 时间块」）、越权 403/404、简报时区断言、LBS POI 注入与诚实降级。

---

## 四、重点：CI 测试基建加固（conftest 清理 + 监控）

### 4.1 conftest 会话结束自动清理测试数据库残留

- `pytest_sessionfinish` hook：按 `os.getpid()` 删除本进程 `data/test_{pid}.db*`（含 -journal/-wal），正常/异常退出均触发
- 根治本地反复跑测试的 `data/` 残留累积（历史已清理 2 次 18+ 个文件）；只匹配 test db，不触碰 `data/ihome.db` 业务库
- **监控化**：清理输出 `test_db_cleanup: pid=… removed=N failed=M`（info）与 `test_db_cleanup_failed`（warning，进 pytest 日志），删除失败不再静默

### 4.2 CI 冗余配置修正

- `backend-test` job 移除冗余 `DATABASE_URL: ./data/test_${run_id}.db`（实际被 conftest 按 PID 强制覆盖，纯误导），加防回归注释：**勿改 conftest 为 `setdefault`**，否则 xdist 各 worker 共享同一 db 并发写冲突

### 4.3 决定性验证

本地模拟 CI 并行（`-n 2`）运行中观察：`data/` 同时存在 master + 2 worker **三个独立 `test_{pid}.db`**（PID 隔离成立），结束后归零（各进程 sessionfinish 均执行）。GitHub Actions runner 为 ephemeral，即使 hook 因 SIGKILL 未触发，残留也随 VM 销毁。

---

## 五、变更内容

### 5.1 相关提交

| 提交 | 内容 |
|------|------|
| `da90c6c` | feat(agents): 智能体全链路记忆闭环 + 时间感知时区一致性 |
| `ca9120e` | test(infra): 会话结束自动清理测试数据库残留 + 技术复盘文档 |
| `7fa02a6` | fix(time): 时区统一全量收尾 — 对外展示 13 文件 + 业务日期 4 处 |
| `913f881` | test(infra): conftest 清理逻辑监控化 + CI 冗余 DATABASE_URL 移除 |

### 5.2 文件变更（代码）

| 类别 | 文件 |
|------|------|
| API 层 | `app/api/agents.py`（记忆 helper + 19 端点接入）、`app/api/projects.py`、`app/api/procurement.py` |
| Agent | `app/agents/orchestrator.py`、`growth.py`、`finance_recon.py`（简报时区） |
| 服务层 | `a2ui_schema.py`、`a2ui_generator.py`、`ai_copy_service.py`、`ecosystem_bridge_status.py`、`health_monitor.py`、`okf_export_service.py`、`payment_service.py`、`points_service.py`、`predictive_maintenance_service.py`、`procurement_enhanced_service.py`、`procurement_service.py`、`quality_service.py`、`scene_automation_service.py`、`settlement_service.py` |
| 测试基建 | `tests/conftest.py`（sessionfinish 清理 + 监控日志）、`.github/workflows/ci.yml`（移除冗余 env） |
| 测试 | `tests/test_agent_chain.py`（12 用例） |
| 文档 | `docs/reports/technical-review-20260808.md`、`CHANGELOG.md` |

### 5.3 无破坏性变更

- 无新 feature flag、无 DB 迁移、无 API schema 变更
- 时区仅影响对外展示字段；DB 存储语义不变
- 记忆注入仅在端点内部注入上下文，不改变端点响应契约

---

## 六、验证结论

| 门禁 | 结果 |
|------|------|
| `tests/test_agent_chain.py` | **12 passed** |
| 时区收尾相关回归（projects/procurement/payments/settlement/health/scene/procurement_enhanced/points） | **235 passed** |
| 全量 pytest | **2046 passed / 2 skipped / 4 xfailed**，零回退 |
| flake8（max-line-length=120, max-complexity=15） | 0 issues |
| mypy | 0 issues |
| conftest 清理验证 | 串行 + xdist `-n 2` 运行前后 `data/test_*.db*` 计数均 0 |
| YAML（ci.yml） | 校验通过 |

---

## 七、回滚方案

本版本无新 feature flag / DB 迁移，回滚 = 版本回退：

```bash
# 方案一：回退相关提交（按需选择范围）
git revert 913f881 7fa02a6 ca9120e da90c6c

# 方案二：整体回退至 v1.10.2（保留后续提交，慎用）
git revert HEAD~4..HEAD
```

---

## 八、开发团队行动项

- [ ] 确认时区边界约定（DB 存储 UTC / 对外展示 +08:00）被新代码遵守；新增对外时间戳一律 `_BJ_TZ`
- [ ] 勿将 `tests/conftest.py` 的 `DATABASE_URL` 强制赋值改为 `setdefault`（xdist 并发写冲突）
- [ ] 记忆注入闭环在 19 端点的行为（含 `agent_memory_extract_enabled` 门控关闭时的零影响）按需回归
- [ ] 后续若修改 `pytest_sessionfinish` 清理逻辑，运行 `-n 2` 验证 data/ 前后归零

---

*详细复盘见 `docs/reports/technical-review-20260808.md`；Changelog 条目见 `CHANGELOG.md` [Unreleased]*

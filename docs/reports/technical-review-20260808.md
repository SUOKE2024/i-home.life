# 技术复盘：智能体全链路记忆注入 + 报告时区统一

- **日期**：2026-08-08
- **范围**：`da90c6c` + 随 `d1790d0` 入库的修复（当前基线 v1.10.x）
- **验证**：全量 pytest 2046 passed / 2 skipped / 4 xfailed，零回退；flake8 / mypy 通过

---

## 一、报告时间戳时区统一（UTC → 北京时间 +08:00）

### 背景与问题

平台业务时区为 Asia/Shanghai（`agent_context_service._DEFAULT_TZ = "Asia/Shanghai"`），但对外报告类时间戳此前混用 UTC，用户可读性差、跨端展示不一致：

- 运营简报：Orchestrator `generate_daily_briefing`、Growth `generate_weekly_report`、FinanceRecon `generate_recon_report`
- 方案/交付/监测报告：`solution_first_service`（2 处）、`b2b_delivery`（同步/异步 2 处）、`health_monitor_service`、`energy` API（含废弃 `datetime.utcnow()`）、`schemas/energy_monitor` default_factory

### 方案

统一 `_BJ_TZ = timezone(timedelta(hours=8), name="Asia/Shanghai")`（固定偏移，不依赖 tzdata，对齐既有实现），对外 `generated_at` 一律 `datetime.now(_BJ_TZ).isoformat()`；同步消除 2 处废弃 `datetime.utcnow()`（naive UTC）。

**边界**：DB 存储字段（`reviewed_at` / `completed_at` / `deleted_at` 等）与查询窗口起点（`since`）**保留 UTC** —— 与 PostgreSQL 会话 `TimeZone=UTC` 及存储语义一致，不属本次范围。

### 验证

- 三份运营简报实测输出 `2026-08-08T21:49:xx+08:00` ✓
- 断言测试：`test_daily_briefing_generated_at_beijing_tz` / `test_growth_report_*` / `test_finance_report_*`（`generated_at.endswith("+08:00")`）

---

## 二、智能体全链路记忆注入闭环

### 背景与问题

长期记忆链路（提取 `extract_and_store_memories` + 注入 `build_agent_context`）此前仅在 `/chat` 与 `/chat/stream` 两个端点闭环；19 个专用 Agent 端点既不提取也不注入记忆：

- 用户经 `/kitchen`、`/budget` 等专用端点表达偏好（"我喜欢北欧风格"）**不会被学习**（写侧断裂）
- 后续任何对话**读不到**这些偏好（读侧断裂）

### 方案

1. **统一 helper** `_extract_and_inject_agent_context`（`app/api/agents.py`）：
   - 写侧：`extract_and_store_memories`（偏好/城市规则提取，`agent_memory_extract_enabled` 门控）
   - 读侧：`build_agent_context`（时间感知 + 空间感知/记忆城市 + 长期记忆，`project_id` 驱动作用域）
   - 安全：`project_id` 非空先校验项目归属（对齐 `/chat`，防越权写 project scope 记忆）——**顺带补齐专用端点缺失的归属校验**
2. **端点接入**：16 个 LLM 型端点提取+注入（budget/procurement/construction/concierge-chat + 12 SimpleAgent），3 个工具型端点仅提取（design/faq/classify）
3. **可观测性**：`/kitchen`、`/budget` 与 helper 增加 structlog 日志，链路 `agent_kitchen_request → agent_ctx_start → agent_memory_extracted(saved=N) → agent_ctx_injected(preview) → agent_kitchen_ctx_ready → agent_kitchen_reply`
4. **LBS 恢复**：恢复 `AgentMessage.location` 字段与 `/chat`、`/chat/stream` 的 LBS 传参（v1.8.x 空间感知闭环，曾被外部还原丢失）

### 验证

- `test_agent_chain.py` 12 passed：写侧提取（偏好/城市）、**提取+注入闭环**（monkeypatch spy `KitchenAgent.think` 断言第二轮注入含「【用户长期记忆】+ 偏好 + 时间块」）、越权 403/404、简报时区断言、LBS POI 注入与诚实降级

---

## 三、环境故障排查（磁盘满 → SQLite readonly）

全量 pytest 曾反复 `attempt to write a readonly database`（单文件/批量测试正常，仅全量并发时触发）。排查结论：

- **根因**：磁盘容量 100%（Avail 3.2Gi），macOS 对满载 APFS 卷拒绝并发小文件写入
- **处置**：清理 `~/Library/Developer/Xcode/DerivedData`（3.4G）→ Avail 8Gi，全量通过
- **教训**：排查 SQLite readonly 先查 `df -h` 容量，勿误判为并发/权限；详见"资源瓶颈排查"节

---

## 四、资源瓶颈排查结论

| 项 | 结论 | 风险等级 |
|---|---|---|
| 生产 DB | PostgreSQL（`.env.production`）+ Redis，无 SQLite 并发问题 | 无 |
| 测试 DB | `conftest.py` 按 `os.getpid()` 隔离 db 文件 + `StaticPool` 单连接，xdist 各 worker 独立 | 低 |
| **data/ 残留 test_\*.db** | 每次 pytest 产生 `test_{pid}.db`（含 -journal/-wal），运行结束不删除，长期累积占磁盘（历史已清理 2 次 18+ 个） | **中（待修复）** |
| 缓存 | Redis 优先（池 50 连接）；内存降级单进程内安全，多 worker 不共享（已知限制，dev 环境） | 低 |
| DB 连接池 | PG `pool_size=20 + max_overflow=10 + pre_ping + recycle` | 低 |
| 磁盘 | 全量测试 + Xcode 构建缓存共同推高容量至 100% | 中（环境性） |

**已修复**：`conftest.py` 新增 `pytest_sessionfinish` hook，在 pytest 进程（含 xdist worker）结束时自动删除本进程 `data/test_{pid}.db*`（含 -journal/-wal），防止残留累积；实测跑完测试 data/ 无新增残留，历史 26 个残留已手动清理一次。

# v1.11.0 最终性能与稳定性复盘报告

> 生成日期：2026-08-09 · 归档：docs/reports/performance-stability-review-v1.11.0.md
> 配套：docs/reports/technical-review-20260808.md（技术复盘）/ validation-report.md（验收报告）

---

## 一、时区修复效果分析

### 1.1 修复范围与收益

| 批次 | 范围 | 数量 | 收益 |
|------|------|------|------|
| 第一批 | 运营简报/报告 `generated_at` | 3 简报 + 5 报告模块 | 用户可见时间戳统一 +08:00，跨端一致 |
| 第二批 | 对外展示类时间戳 | 13 文件 70+/−32 行 | 消除 UTC 展示（用户读 UTC 无意义） |
| 第三批 | 业务日期/年份 | 4 处（整改单号/业务单号/发票号/积分年度） | 消除北京时间 00:00–07:59 跨日/跨年错位 |
| 全仓 | 废弃 `datetime.utcnow()` | 多处 → **0** | 消除 naive-UTC 弃用 API |

### 1.2 稳定性量化

- **全量回归**：2046 passed / 2 skipped / 4 xfailed（基线 2021 → 2046，**零回退**）
- **时区断言确定性**：`+08:00` 断言基于固定偏移 `timezone(timedelta(hours=8))`，不依赖 CI runner 系统时区（UTC 环境稳定通过）
- **边界约定收益**：DB 存储字段保持 UTC 与 PG 会话 `TimeZone=UTC` 一致，避免 asyncpg aware/naive 编码错误（历史 v1.1.13 教训延续）
- **回归面**：时区收尾相关 235 passed（projects/procurement/payments/settlement/health/scene/procurement_enhanced/points）

## 二、CI 流水线优化数据

### 2.1 conftest 清理逻辑（本轮核心）

| 指标 | 数据 |
|------|------|
| 清理机制 | `pytest_sessionfinish` 按 `os.getpid()` 删除 `data/test_{pid}.db*`（含 -journal/-wal） |
| 决定性验证 | `-n 2` 并行：运行中 master + 2 worker **3 个独立 PID db 并存** → 结束后归零 |
| 监控日志 | `test_db_cleanup: pid=… removed=N failed=M`（info）+ `test_db_cleanup_failed`（warning 进 pytest 日志） |
| 历史累积 | 已清理 2 次 18+ 残留文件 → 自动清理根治 |
| 本轮孤儿 | 清理 8 个外部进程 SIGKILL 残留（16M）→ `data/` 仅业务库 |

### 2.2 CI 配置优化

| 变更 | 影响 |
|------|------|
| 移除冗余 `DATABASE_URL: test_${run_id}.db` | 消除误导（实际被 conftest 覆盖）；固化 setdefault 防回归注释 |
| CI `-n auto` 与本地串行双模式 | 各 worker 独立 PID 隔离验证通过 |
| runner ephemeral 兜底 | SIGKILL 场景 CI 无残留影响 |

### 2.3 测试集与时长

- 新增 `tests/test_agent_chain.py` 12 用例（记忆闭环/越权/时区/LBS）
- 版本断言回归 89 passed（~6 min）；全量 pytest ~28 min（1698s，`timeout-minutes: 30` 预算内）
- flake8 / mypy 0 issues；YAML 校验通过

## 三、SQLite 并发风险消除情况

### 3.1 风险矩阵（复核结论）

| 场景 | 风险 | 处置 | 状态 |
|------|------|------|------|
| 生产（PG `pool_size=20+overflow=10`） | 无 SQLite 并发问题 | 连接池 + pre_ping + recycle | ✅ 无风险 |
| 测试 SQLite `StaticPool` 单连接 | 单连接避免文件锁 | `check_same_thread=False` + PID 隔离 db | ✅ 消除 |
| 测试 db 残留 | 累积占磁盘 | `pytest_sessionfinish` 自动清理 + 监控 | ✅ 根治 |
| 后台任务并发占用（b2b_delivery） | StaticPool 单连接竞争 | `asyncio.sleep(0.05)` 让出事件循环 | ✅ 已处理 |
| 磁盘 100% readonly（历史事故） | 全量测试失败 | 清理 DerivedData 3.4G → 7.5Gi 可用 | ✅ 已解决 |
| xdist 并发写同一 db（防回归） | readonly 事故变体 | conftest 强制 PID 覆盖（勿改 setdefault） | ✅ 防回归 |

### 3.2 数据佐证

- 全项目 `**/*.db*` 扫描：无 test 孤儿；`data/` 仅 `ihome.db`（业务库）
- `.mypy_cache/cache.*.db` 为工具缓存（gitignored，非测试库）
- 部署脚本强制 PG（`deploy-production.sh`），生产无 SQLite 路径

## 四、版本与归档结论

| 项 | 结果 |
|----|------|
| Git Tag | `v1.11.0`（ac8a48c）已推送 |
| 版本号全链路 | 18 文件 + 本地 .env 同步，断言 89 passed |
| 归档 | assets/releases/v1.11.0/（4 文件）+ CODE_WIKI §12 + 复盘/确认报告 |
| 远程状态 | 仅 main 分支，无 open PR |

## 五、遗留与下一轮建议

- [ ] 外部前端缺口（console +12 页 / Flutter +3 页）未提交，建议独立 PR 合并
- [ ] 发布动作：正式部署 v1.11.0 至生产（部署脚本 + 全链路版本已就绪）
- [ ] 监控演进：本地 test db 孤儿清理可考虑 pre-commit 或启动时巡检（xdist 误报需规避）

---

*本报告由本次迭代实测数据生成，禁止虚构指标。*

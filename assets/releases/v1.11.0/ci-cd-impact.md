# v1.11.0 对 CI/CD 流水线的具体影响分析

> 归档：assets/releases/v1.11.0/ci-cd-impact.md · 变更基线：v1.10.2 → v1.11.0
> 范围：`.github/workflows/ci.yml` 全部 9 个 job 逐一评估

## 一、总览

| Job | 影响程度 | 说明 |
|-----|---------|------|
| `backend-test` | **高** | 本次迭代核心影响区（env 变更 + 测试集增长 + 清理逻辑） |
| `lint` | 低 | 新增/修改文件均过 flake8，无新约束 |
| `migration-test` | 无 | 本次零 DB 迁移 |
| `frontend-smoke` / `flutter-analyze` / `flutter-perf-baseline` / `apk-size-budget` / `security-audit` | 无 | 不涉及本次变更面 |
| `deploy` | 低 | 流程不变；仅 `APP_VERSION` 需在正式发布时同步（见 §5） |

## 二、backend-test（核心影响）

### 2.1 移除冗余 `DATABASE_URL` env（行为无变化）

- **变更**：删除 `DATABASE_URL: sqlite+aiosqlite:///./data/test_${{ github.run_id }}.db`
- **行为影响**：无——该值此前即被 `tests/conftest.py` 第 6 行强制覆盖为 `test_{os.getpid()}.db`，从未生效
- **价值**：消除误导性配置；新增注释固化约束——**勿将 conftest 强制赋值改为 `setdefault`**，否则 xdist 各 worker 共享同一 db，触发 SQLite 并发写冲突（readonly 事故变体）
- **验证**：本地模拟 CI 并行（`-n 2`）运行中观察到 master + 2 worker 三个独立 `test_{pid}.db`（PID 隔离成立），结束后归零

### 2.2 conftest 清理逻辑在 CI 的行为

| 场景 | 行为 | 影响 |
|------|------|------|
| 正常完成 | 每个 worker 独立 `sessionfinish` 删除自己的 `test_{pid}.db*` | 无残留 |
| 异常（测试失败） | 同上（hook 在 pytest 进程结束前触发） | 无残留 |
| SIGKILL/OOM/timeout 硬杀 | hook 不触发 | **CI 无影响**（runner ephemeral，残留随 VM 销毁）；本地会残留（见 §6） |
| 监控日志 | `test_db_cleanup`（info）/ `test_db_cleanup_failed`（warning） | CI 日志文件（`log_file_level=WARNING`）可捕获失败信号 |

### 2.3 测试集增长

- 新增 `tests/test_agent_chain.py`（12 用例：记忆提取/注入闭环、越权、时区断言、LBS）
- 全量 2046 passed / 2 skipped / 4 xfailed，`timeout-minutes: 30` 预算内（新增用例均为本地 mock，无 LLM/网络等待）

### 2.4 时区断言确定性

- `generated_at.endswith("+08:00")` 断言基于固定偏移 `timezone(timedelta(hours=8))`，**不依赖 runner 系统时区**（CI runner 为 UTC 也稳定通过）
- 记忆注入测试通过 monkeypatch spy 断言，不依赖外部服务

## 三、lint job

- 13 个时区文件 + conftest.py 全部通过 flake8（max-line-length=120, max-complexity=15），无新增 E402/F401（统一 `_BJ_TZ` 定义置于全部 import 之后）
- mypy 通过；本次无新增类型约束

## 四、migration-test job

- 本次迭代**零 DB 迁移、零 schema 变更**，`alembic upgrade/downgrade` 测试不受影响

## 五、deploy job（发布待办）

- 流程不变：`needs: [backend-test, frontend-smoke, lint]`，时区/记忆修复随 `app/` 代码同步自动生效（生产 PG + systemd 重启）
- ⚠️ **发布待办**：v1.11.0 正式发布时需同步 `APP_VERSION`（当前仍 1.10.2）：
  - `.github/workflows/ci.yml`（backend-test env、perf-regression env 共 2 处）
  - `.github/workflows/schema-compare.yml`
  - `scripts/deploy-production.sh`、`app/config.py`、`flutter_app/pubspec.yaml`、`webapp/package.json` 等全链路（见 `.claude/templates/version-bump.md`）
- 回滚：本次无新 flag，`scripts/rollback.sh` 无需新增条目；紧急回滚走 `git revert`（见 RELEASE_NOTES §七）

## 六、CI 与本地差异备忘

| 维度 | CI（`-n auto`） | 本地（pytest.ini 串行） |
|------|----------------|------------------------|
| db 文件数 | 1 + worker 数 | 1 |
| 清理 | 各进程 sessionfinish + runner ephemeral 兜底 | sessionfinish；SIGKILL 场景残留需手动清理 |
| 孤儿清理命令 | 无需 | `rm -f data/test_*.db data/test_*.db-journal`（进程退出后） |

## 七、结论

本次迭代对 CI/CD 为**低风险增量**：无流程/契约变更，核心是消除误导配置 + 补监控可观测性 + 测试集小幅增长。
唯一待办为发布 v1.11.0 时的 `APP_VERSION` 全链路同步（与版本 bump 流程合并执行，不单独操作 CI）。

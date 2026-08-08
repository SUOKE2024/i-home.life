# v1.11.0 版本修复完整清单

> 归档：assets/releases/v1.11.0/ · 变更基线：v1.10.2 → v1.11.0
> 用途：内部知识库归档（配合 RELEASE_NOTES.md 与 docs/reports/technical-review-20260808.md）

## 一、语义变更

| 类型 | 说明 |
|------|------|
| 修复 | 全仓对外展示时间戳 UTC → 北京时间 +08:00（三批：简报/报告 → 13 对外展示文件 → 4 业务日期） |
| 修复 | 废弃 `datetime.utcnow()` 全仓清零（0 处残留） |
| 优化 | 智能体记忆注入闭环：19 个专用端点补齐记忆提取/注入（原仅 /chat 两端点） |
| 优化 | `tests/conftest.py` 会话结束自动清理测试数据库残留（按 PID）+ 清理监控日志 |
| 优化 | CI `backend-test` 移除冗余 `DATABASE_URL` env + 防回归注释 |
| 无变更 | 无新 feature flag、无 DB 迁移、无 API schema 变更 |

## 二、代码变更清单

| 文件 | 变更 | 类型 |
|------|------|------|
| `app/api/agents.py` | 新增 `_extract_and_inject_agent_context` 统一 helper，接入 19 个专用端点；恢复 `AgentMessage.location` 与 /chat LBS 传参 | 优化 |
| `app/agents/orchestrator.py` | `generate_daily_briefing` 的 `generated_at` → +08:00 | 修复 |
| `app/agents/growth.py` | `generate_weekly_report` 的 `generated_at` → +08:00 | 修复 |
| `app/agents/finance_recon.py` | `generate_recon_report` 的 `generated_at` → +08:00 | 修复 |
| `app/api/projects.py` | `accepted_at` → +08:00 | 修复 |
| `app/api/procurement.py` | `actual_delivery_date` → +08:00（废弃 utcnow） | 修复 |
| `app/services/a2ui_schema.py` | CardHeader `timestamp` + `make_card` → +08:00 | 修复 |
| `app/services/a2ui_generator.py` | `updated_at` 默认值 → +08:00 | 修复 |
| `app/services/ai_copy_service.py` | 3 处废弃 `datetime.utcnow()` → +08:00 | 修复 |
| `app/services/ecosystem_bridge_status.py` | `updated_at` → +08:00 | 修复 |
| `app/services/health_monitor.py` | `checked_at` → +08:00 | 修复 |
| `app/services/okf_export_service.py` | 导出 `description` 时间戳 → +08:00 | 修复 |
| `app/services/payment_service.py` | `generated_at` → +08:00；发票号 `INV-YYYYMMDD` 用业务日期（`invoiced_at` 存储仍 UTC） | 修复 |
| `app/services/points_service.py` | 年度统计 + 排行榜默认年份 → 北京时间 | 修复 |
| `app/services/predictive_maintenance_service.py` | 缓解/解决备注时间戳 2 处 → +08:00 | 修复 |
| `app/services/procurement_enhanced_service.py` | 业务单号 `PREFIX-YYYYMMDD` 用业务日期 | 修复 |
| `app/services/procurement_service.py` | `linked_at` → +08:00 | 修复 |
| `app/services/quality_service.py` | 整改单号 `RO-YYYYMMDD` 用业务日期 | 修复 |
| `app/services/scene_automation_service.py` | `triggered_at` → +08:00 | 修复 |
| `app/services/settlement_service.py` | `exported_at` → +08:00 | 修复 |
| `tests/conftest.py` | 新增 `pytest_sessionfinish` 按 PID 清理 test db + 监控日志（`test_db_cleanup` / `test_db_cleanup_failed`） | 优化 |
| `.github/workflows/ci.yml` | 移除冗余 `DATABASE_URL` env + 防回归注释 | 优化 |
| `tests/test_agent_chain.py` | 新增 12 用例（记忆提取/注入闭环 spy、越权 403/404、时区断言、LBS） | 测试 |
| `docs/reports/technical-review-20260808.md` | 时区三批 + 记忆注入 + conftest CI 验证 + 资源瓶颈复核 | 文档 |
| `CHANGELOG.md` | [Unreleased] 条目（时区收尾 / 记忆注入 / conftest 清理） | 文档 |

## 三、时区统一模式与边界（知识库要点）

```python
# 统一模式（固定偏移，不依赖 tzdata）
_BJ_TZ = timezone(timedelta(hours=8), name="Asia/Shanghai")
```

| 场景 | 时区 | 原因 |
|------|------|------|
| 对外展示时间戳（报告/卡片/备注/checked_at 等） | 北京时间 +08:00 | 用户可读性、跨端一致 |
| 业务日期标识（单号 YYYYMMDD / 年度统计） | 北京时间 | 跨日/跨年 8 小时窗口错位 |
| DB 存储字段（reviewed_at/completed_at/invoiced_at 等） | UTC | 与 PG 会话 TimeZone=UTC 一致 |
| 查询窗口（since/cutoff/TTL/过期判断） | UTC | 避免时区转换歧义 |
| 认证（PASETO iat/exp） | UTC | 协议标准 |

## 四、feature flag / DB / 契约状态

| 项 | 状态 |
|------|------|
| 新 feature flag | 无 |
| DB 迁移 | 无（零 schema 变更） |
| API 契约 | 无破坏性变更 |
| 记忆提取门控 | 复用 `agent_memory_extract_enabled`（默认 False，关闭零影响） |

## 五、验证结论

| 门禁 | 结果 |
|------|------|
| 全量 pytest | **2046 passed / 2 skipped / 4 xfailed**（零回退，基线 2021→2046） |
| `tests/test_agent_chain.py` | 12 passed |
| 时区收尾回归 | 235 passed（projects/procurement/payments/settlement/health/scene/procurement_enhanced/points） |
| flake8 / mypy | 0 issues |
| conftest 清理 | 串行 + xdist `-n 2` 决定性验证（3 独立 PID db → 归零） |
| CI YAML | 校验通过 |

## 六、已知注意事项（知识库要点）

1. **本地孤儿残留**：`pytest_sessionfinish` 在进程被 SIGKILL/硬杀时不触发（hook 固有盲区）。
   本地出现残留时（无活跃 pytest 进程前提下）清理：
   ```bash
   rm -f data/test_*.db data/test_*.db-journal
   ```
2. **勿改 conftest 的 `DATABASE_URL` 强制赋值为 `setdefault`**：会导致 xdist 各 worker
   共享同一 db 并发写冲突（readonly 事故变体）。
3. **时区边界约定**：新增对外时间戳一律 `_BJ_TZ`，DB 存储字段保持 UTC，勿混用。
4. **CI runner 为 ephemeral**：hook 异常场景在 CI 无残留影响，本地是主要受益场景。

## 七、回滚

```bash
# 无新 flag/迁移，回滚 = 版本回退
git revert 913f881 7fa02a6 ca9120e da90c6c
```

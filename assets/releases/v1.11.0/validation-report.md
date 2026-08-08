# v1.11.0 最终验收报告

> 归档：assets/releases/v1.11.0/validation-report.md · 生成日期：2026-08-09
> 版本：v1.11.0（前置 v1.10.2）· 全链路版本号已同步（后端/Flutter/Web/控制台/CI/部署/测试断言）

---

## 一、时区修复验收

| 验收项 | 结果 | 证据 |
|--------|------|------|
| 运营简报/报告 `generated_at` 统一 +08:00 | ✅ | 实测三份简报输出 `+08:00`；`test_agent_chain.py` 断言 `endswith("+08:00")` |
| 13 个对外展示类文件统一 `_BJ_TZ` | ✅ | `projects/procurement/a2ui/ai_copy/ecosystem/health/okf/payment/predictive/procurement_service/scene/settlement` |
| 4 处业务日期/年份改用北京时间 | ✅ | 整改单号 / 业务单号 / 发票号 / 积分年度（跨日/跨年 8 小时偏差消除） |
| 废弃 `datetime.utcnow()` 清零 | ✅ | 全仓 0 处（仅 `diagnostics.py` 辅助函数定义，DB 存储用途） |
| 时区边界约定 | ✅ | DB 存储字段 + 查询窗口保持 UTC；对外展示 +08:00 |
| 回归测试 | ✅ | 时区收尾相关 235 passed |

## 二、智能体记忆注入闭环验收

| 验收项 | 结果 | 证据 |
|--------|------|------|
| 19 个专用端点补齐记忆提取/注入 | ✅ | `_extract_and_inject_agent_context` helper 接入 16 LLM 型 + 3 工具型端点 |
| 提取+注入闭环 | ✅ | `test_agent_chain.py` monkeypatch spy 断言第二轮注入含偏好+时间块 |
| 越权防护 | ✅ | `project_id` 归属校验（403/404 测试） |
| LBS 空间感知恢复 | ✅ | `AgentMessage.location` 恢复 + POI 注入与诚实降级 |
| 可观测性 | ✅ | structlog 链路 `agent_kitchen_request → … → agent_kitchen_reply` |

## 三、CI 优化与资源清理验收

| 验收项 | 结果 | 证据 |
|--------|------|------|
| conftest 会话结束清理 test db | ✅ | `pytest_sessionfinish` 按 PID 删除 `data/test_{pid}.db*` |
| CI 并行（xdist）清理生效 | ✅ | `-n 2` 决定性验证：运行中 3 独立 PID db 并存 → 结束后归零 |
| 清理监控化 | ✅ | `test_db_cleanup`（info）/ `test_db_cleanup_failed`（warning 进 pytest 日志） |
| CI 冗余 env 修正 | ✅ | 移除 `DATABASE_URL`（被 conftest 覆盖），加 setdefault 防回归注释 |
| 孤儿 SQLite 文件 | ✅ | 全项目扫描无 test 残留；`data/` 仅业务库 `ihome.db`；`.mypy_cache` 为工具缓存 |
| 本地孤儿清理 | ✅ | 已清理 8 个外部进程残留（SIGKILL 场景）；清理命令记入 changes.md |

## 四、版本 bump 验收（v1.10.2 → v1.11.0）

| 验收项 | 结果 | 证据 |
|--------|------|------|
| 后端 4 处 | ✅ | `app/config.py` / `app/mcp/server.py` / `.env.example` / `.env.production.example` |
| Flutter 3 处 | ✅ | `pubspec.yaml`（1.11.0+39）/ `config.dart` / `settings_page.dart` |
| Web/控制台 4 处 | ✅ | `webapp/package.json` / `version.json`（build 39）/ `Profile.jsx` / `console-src/package.json`（1.11.0.0） |
| CI/部署 5 处 | ✅ | `ci.yml` ×3 / `schema-compare.yml` / `deploy-production.sh` |
| 测试断言 3 文件 | ✅ | `test_v1_3_0_compliance` / `test_v1128_suoke_borrowed` / `test_mcp_2026_07_28`（函数名+docstring+断言同步） |
| 验证脚本 | ✅ | `verify_self_evolution.py` 版本断言 1.11.0 |
| 本地 .env | ✅ | `.env` / `.env.production`（未追踪）同步 1.11.0 |
| 残留检查 | ✅ | 仅剩依赖版本（pubspec.lock source_span）与 docstring 变更说明（合理保留） |
| 版本断言测试 | ✅ | **89 passed**（test_v1_3_0_compliance + test_mcp + test_v1128） |
| YAML 校验 | ✅ | ci.yml / schema-compare.yml 合法 |

## 五、全量验证结论

| 门禁 | 结果 |
|------|------|
| 全量 pytest | **2046 passed / 2 skipped / 4 xfailed**（零回退，基线 2021→2046） |
| 版本断言回归 | **89 passed** |
| 时区收尾回归 | **235 passed** |
| `test_agent_chain.py` | **12 passed** |
| flake8 / mypy | 0 issues |
| conftest 清理验证 | 串行 + xdist `-n 2` 前后归零 |

## 六、遗留与建议

- [ ] **发布动作**：打 tag `v1.11.0` + 同步 `scripts/rollback.sh` 说明（v1.11.0 无新 flag，回滚走 `git revert`，RELEASE_NOTES §七）
- [ ] CLAUDE.md / CODE_WIKI.md 的版本描述由外部改动推进中，未纳入本次 bump（避免冲突），发布前确认
- [ ] 本地 `data/` 残留治理：hook 异常终止场景需手动 `rm -f data/test_*.db data/test_*.db-journal`（changes.md §六）

## 结论

✅ **v1.11.0 全部验收通过**：时区统一（三批 + 边界约定）、记忆注入闭环（19 端点）、CI 基建加固（清理 + 监控）、资源清理彻底、版本号全链路同步，无破坏性变更，可进入发布流程。

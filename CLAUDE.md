# CLAUDE.md — i-home.life AI 协作契约

> 索克家居 · AI 智能装修平台。本文件是项目级 AI 协作硬约束，随代码版本控制。
> 改 AI 行为请走 PR，可追溯、可 review。**只写 AI 无法从代码推断的项目特有规则。**

## 项目定位

模块化单体（modular monolith，非微服务，见 `app/config.py` `service_role` 澄清）。
Python(FastAPI) 后端 + Flutter 多端(iOS/Android/HarmonyOS) + React Web 控制台。
所有路由在 `app/main.py` 无条件 `include_router` 加载。

## Agent 分类约定（v1.6.0）

两类 Agent，feature flag 独立控制，勿混淆：

- **执行型 Agent**（面向用户交付）：designer/budget/procurement/construction/qa_inspector/settlement/concierge 等 22 个，覆盖家装交付链路。
- **商业运营 Agent**（平台自身运营，借鉴 Polsia 9 大智能体 + 义乌「AI 嵌入生意每一环」）：growth/marketing/competitor_research/finance_recon，受各自 `xxx_agent_enabled` flag 灰度，默认 False。
- **主动 Orchestrator**：`OrchestratorAgent.generate_daily_briefing` 每日聚合 growth + finance 报告，阿里云 FC 定时触发器调用 `/api/admin/daily-briefing`（受 `business_ops_orchestrator_enabled` 控制，无 K8s/Cron）。
- **以销定产**：`procurement_demand_driven_enabled`（默认 False）开启后 `procurement_service.drive_procurement_from_bom` 从 designer BOM 反向驱动采购优先级（紧急/常规/可缓），借鉴义乌「以销定产」模式。

商业运营 Agent 数据源诚实标注（GrowthAgent 基于 `agent_feedbacks` 表，非全量调用日志；FinanceRecon 基于 `payment/escrow` 内部表，无 Stripe 对接），禁止伪装实时数据。

## 不可违反的硬约束（架构红线，违反即 reject）

- **部署**：阿里云 FC 函数计算。**禁止引入 K8s/Helm/容器编排方案**。
- **鉴权**：PASETO v4.local。**禁止使用 JWT/JWS**。密钥 ≥32 字节，`paseto_strict_mode=True` 时硬校验（见 `app/config.py` `_validate_paseto_key`）。
- **MCP**：遵循 2026-07-28 规范 8 项（stateless / discover / header-routing / cacheable / MRTR / RFC9207 / Tasks / Server Card）。改 MCP 看齐 `app/mcp/`。
- **缓存隔离**：私有数据 cache key 必须含 `user_id`。`cache_user_isolation_strict=True`（默认），未传 user_id 直接 raise。用 `build_isolated_key` / `get_isolated` / `set_isolated`。
- **配置单例**：`get_settings()` 是 `@lru_cache` 单例（`app/config.py`）。测试中**禁止 `get_settings.cache_clear()`**——它使其他模块 import 时的 `settings = get_settings()` 模块级绑定变成陈旧引用，导致跨文件测试隔离失败（曾致 test_v1129 audit + test_webauthn 全量跑失败、单独跑通过）。改 feature flag 用 `monkeypatch.setattr(get_settings(), "flag", value)`，teardown 自动还原。
- **AI 渲染**：4 级降级链 L0(ControlNet) → L1(mock) → L2(占位) → L3(error)。`ai_render_contract_strict=True` 时客户端 `require_real=True` 且后端不可用 → 503 诚实报错，**禁止移除降级路径**。
- **会话加密**：`allow_plaintext_session=False`（默认）。PASETO 密钥不可用时拒绝明文存储会话消息，防 PII 泄露。
- **诚实降级**：禁止用硬编码假数据伪装真实能力。不可用就明确 503/占位 + 标注（历史教训：v1.1.31 修复 6 处硬编码假数据）。

## 协作四原则（改编自 Karpathy LLM 编程四铁律）

1. **Think Before Coding** —— 需求有歧义先问，多方案先列选项，禁止默写假设。项目有 22 执行型 + 4 商业运营 Agent / 99 Service，猜错代价高。
2. **Simplicity First** —— 最小可行实现。不加未要求的功能/抽象/灵活性/异常处理。121 ORM 模型 + 73 路由已够复杂（`app/api/` 磁盘实为 73 个路由模块，main.py 76 处 include_router 含 2 个公开 .well-known + 1 个总 router）。
3. **Surgical Changes** —— 只动要求改的。禁止顺手重构无关代码、统一风格、删旧注释。每行改动须能追溯到用户请求。
4. **Goal-Driven Execution** —— 给可验证目标而非模糊命令。改 bug 先写复现测试；加功能先写验收用例。pytest 基线 1956 passed 不得回退（collect 1961 = 1956 passed + 2 skipped + 3 xfailed，2026-08-08 实测 488s）。基线门禁数字见 `scripts/test_baseline.json`（改 CLAUDE.md 须同步该文件）。

## 质量门禁（不得绕过）

- `pytest`（全量必须通过，`tests/` 目录；本地 `pytest.ini` 串行执行保异步稳定性，CI 用 `-n auto` 并行见 `.github/workflows/ci.yml`）
- `pre-commit run --all-files`（flake8 max-line-length=120, max-complexity=15；含 `detect-private-key`）
- `mypy`（`mypy.ini`，改后端代码必跑）
- 新增 API 必须补 `tests/test_*.py`（v1.2.5 教训：曾 37 个 API 模块零测试）
- 版本号全链路一致，见 `.claude/templates/version-bump.md`（v1.2.9 教训：曾 11 处漏改）

## 分端规则索引（按需加载，勿全读）

| 任务上下文 | 加载文件 |
|-----------|---------|
| 后端 Python / FastAPI / ORM / alembic | `.claude/guides/backend.md` |
| Flutter 多端 / 鸿蒙 / PWA | `.claude/guides/flutter.md` |
| React Web 控制台 (console-src) | `.claude/guides/web-console.md` |
| MCP / Agent / A2A 开发 | `.claude/guides/mcp-agent.md` |
| 测试编写规范 | `.claude/guides/testing.md` |
| 版本号升级 | `.claude/templates/version-bump.md` |
| 新增 API 模板 | `.claude/templates/new-api.md` |

> 上述 guide / template 文件若不存在，按需创建时参考对应源码目录，勿臆造。

## 多 LLM fallback chain

`deepseek → qwen → glm → doubao`（`llm_fallback_enabled=True`）。改 LLM 调用走 `BaseAgent._chat()`，勿绕过 fallback。

## 工作目录

- 后端根：`/Users/netsong/Developer/i-home.life`
- 测试：`tests/`（含 `e2e/`）
- 部署脚本：`scripts/`（`deploy-production.sh` / `bump-version.sh` / `check_schema_drift.py` / `rollback.sh` 通用回滚）

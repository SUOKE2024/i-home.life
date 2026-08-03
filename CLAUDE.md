# CLAUDE.md — i-home.life AI 协作契约

> 索克家居 · AI 智能装修平台。本文件是项目级 AI 协作硬约束，随代码版本控制。
> 改 AI 行为请走 PR，可追溯、可 review。**只写 AI 无法从代码推断的项目特有规则。**

## 项目定位

模块化单体（modular monolith，非微服务，见 `app/config.py` `service_role` 澄清）。
Python(FastAPI) 后端 + Flutter 多端(iOS/Android/HarmonyOS) + React Web 控制台。
所有路由在 `app/main.py` 无条件 `include_router` 加载。

## 不可违反的硬约束（架构红线，违反即 reject）

- **部署**：阿里云 FC 函数计算。**禁止引入 K8s/Helm/容器编排方案**。
- **鉴权**：PASETO v4.local。**禁止使用 JWT/JWS**。密钥 ≥32 字节，`paseto_strict_mode=True` 时硬校验（见 `app/config.py` `_validate_paseto_key`）。
- **MCP**：遵循 2026-07-28 规范 8 项（stateless / discover / header-routing / cacheable / MRTR / RFC9207 / Tasks / Server Card）。改 MCP 看齐 `app/mcp/`。
- **缓存隔离**：私有数据 cache key 必须含 `user_id`。`cache_user_isolation_strict=True`（默认），未传 user_id 直接 raise。用 `build_isolated_key` / `get_isolated` / `set_isolated`。
- **AI 渲染**：4 级降级链 L0(ControlNet) → L1(mock) → L2(占位) → L3(error)。`ai_render_contract_strict=True` 时客户端 `require_real=True` 且后端不可用 → 503 诚实报错，**禁止移除降级路径**。
- **会话加密**：`allow_plaintext_session=False`（默认）。PASETO 密钥不可用时拒绝明文存储会话消息，防 PII 泄露。
- **诚实降级**：禁止用硬编码假数据伪装真实能力。不可用就明确 503/占位 + 标注（历史教训：v1.1.31 修复 6 处硬编码假数据）。

## 协作四原则（改编自 Karpathy LLM 编程四铁律）

1. **Think Before Coding** —— 需求有歧义先问，多方案先列选项，禁止默写假设。项目有 22 Agent / 80+ Service，猜错代价高。
2. **Simplicity First** —— 最小可行实现。不加未要求的功能/抽象/灵活性/异常处理。50 ORM 模型 + 74 路由已够复杂。
3. **Surgical Changes** —— 只动要求改的。禁止顺手重构无关代码、统一风格、删旧注释。每行改动须能追溯到用户请求。
4. **Goal-Driven Execution** —— 给可验证目标而非模糊命令。改 bug 先写复现测试；加功能先写验收用例。pytest 基线 1821 passed 不得回退。

## 质量门禁（不得绕过）

- `pytest`（全量必须通过，`tests/` 目录，`pytest.ini` 串行执行，xdist 未启用以保异步测试稳定性）
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
- 部署脚本：`scripts/`（`deploy-production.sh` / `bump-version.sh` / `check_schema_drift.py`）

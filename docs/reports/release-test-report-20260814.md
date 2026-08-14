# 索克家居 i-home.life — 发布前全面测试报告

| 字段 | 值 |
|---|---|
| 测试日期 | 2026-08-14 |
| 被测版本 | 后端 `app/config.py` 1.13.6 · Flutter pubspec 1.13.6+46 · console 1.13.6.0 · webapp version.json 1.13.6(build 46) · MCP SERVER_VERSION 1.13.6 |
| 被测变更面 | git HEAD（3 个未推送提交）＋ 工作树 9 个未提交文件（v1.13.6/v1.13.7 LLM-as-judge 语义评估 + 评估框架 P0 修复），已按用户要求纳入本次验证 |
| 测试环境 | 本地 macOS：.venv Python 3.12.13 · Flutter 3.41.7 · Node 24.15.0 · Playwright 1.62 · uvicorn 127.0.0.1:8766 |
| 测试范围 | 功能 / 性能 / 兼容性 / 安全 四维 + 缺陷记录与回归 |
| 结论 | **达到发布标准。全量回归 0 失败、安全审查无漏洞、四端构建全绿；发现 4 项低危观察项均不阻断发布。** |

---

## 一、执行摘要

| 维度 | 结果 |
|---|---|
| 后端全量回归（pytest） | **2347 passed / 2 skipped / 4 xfailed / 0 failed**（34:10，exit 0）；比基线 2334 多 13（未提交改动新增测试），零回退 |
| 后端定向回归（变更模块） | eval/llm-judge/agent_case/tool_discipline **173 passed**（95s） |
| 安全专项测试 | 确定性安全套件 **179 passed**（SQL 注入/XSS/路径遍历/越权/缓存隔离/WebAuthn/MCP 安全/鉴权，343s） |
| Flutter | `flutter analyze` **0 issues**；`flutter test` **100/100 passed** |
| WebApp / Console 构建 | `npm run build` 均通过（webapp 4.3s / console 含 `tsc --noEmit` 1.7s） |
| 后端启动冒烟 | uvicorn 启动成功；`/api/health` 返回 1.13.6；OpenAPI 599 路径；健康详情诚实降级（Redis 未配置 + 磁盘 warning） |
| 数据库迁移 | 空库 `upgrade head → downgrade -1 → upgrade head` 往返幂等成功，`eval_snapshots` 建/删正常 |
| 性能 | 轻量读端点 P50 6–17ms、RPS 565–1520；注册/登录单请求 369ms；并发 10 下 bcrypt 串行化 ~2.3s（非阻断） |
| 兼容性 | Playwright 视觉 **10/10**（桌面 1440px + 移动 375px）；Flutter 鸿蒙条件导入完整；版本号 8 处全链路一致 |
| 安全 | PASETO 强制（JWT 0 命中）、无硬编码密钥、变更面静态审查无漏洞、限流按设计返回 429 |

**缺陷统计：发现 4 项（0 Critical / 0 High / 0 Medium / 4 Low），均不阻断发布，无需修复即达发布标准。**

---

## 二、缺陷/观察项清单

| ID | 严重度 | 缺陷 | 状态 | 说明与影响 |
|---|---|---|---|---|
| OBS-001 | Low | webapp / console 生产构建 `sourcemap: true`，产物含 `.map` 文件（前端源码暴露） | 待发布前评估（不阻断） | 生产环境建议改 `sourcemap: false` 或 `'hidden'`；React 前端源码本已随 minified JS 分发，风险有限 |
| OBS-002 | Low | 迁移 `a0b1c2d3e4f5_add_eval_snapshots.py` docstring 注释 "Revises: z8a9b0c1d2e3" 与实际 `down_revision="f6a7b8c9d0e2"` 不一致 | 待发布前评估（不阻断） | 实测 `alembic heads` 单一 head、无 branch、迁移往返成功，仅注释过期，无功能影响 |
| OBS-003 | Low | `scripts/bench-api.py` 顶部注释写「`python -m app.main` 启动后端」，但 `app/main.py` 无 `__main__` 块，该命令不会启动服务 | 待发布前评估（不阻断） | 实际启动需 `uvicorn app.main:app`，仅文档误导 |
| OBS-004 | Low（性能观察） | 注册/登录在并发 10 下 P50 ~2.3s（单请求 369ms），根因 bcrypt cost=12 同步哈希在 async 端点内阻塞事件循环、GIL 串行化 | 待优化（不阻断） | 注册/登录非高频热路径；可后续用 `run_in_threadpool` 将 bcrypt 移出事件循环 |

> 无 Critical / High / Medium 缺陷。上述 4 项均为低危观察项，可按排期发布后单独处理。

---

## 三、功能测试明细

### 3.1 后端全量回归（pytest）
- 命令：`.venv/bin/python -u -m pytest tests/ -q --timeout=60 --tb=short`（pytest.ini 串行）
- 结果：**2347 passed, 2 skipped, 4 xfailed, 19 warnings, 0 failed，34:10，exit 0**
- 相对基线（`scripts/test_baseline.json` = 2334 passed）：+13，来源于未提交改动新增的 LLM-as-judge / eval 测试，无回退。
- 测试期间存在外部会话并发 pytest 争用（负载峰值 45），但全量最终 0 失败，未受 flaky 污染。

### 3.2 后端定向回归（v1.13.6 变更模块）
| 文件 | 结果 |
|---|---|
| test_eval_v1136.py / test_eval_upgrade.py / test_eval.py | 全部通过 |
| test_agent_case.py / test_agent_tool_discipline.py | 全部通过 |
| 合计 | **173 passed（95s）** |

### 3.3 后端启动冒烟
| 检查项 | 结果 |
|---|---|
| uvicorn 启动 | ✅ `Application startup complete` |
| `/api/health` | ✅ `{"status":"ok","app":"索克家居","version":"1.13.6","domain":"i-home.life"}` |
| OpenAPI | ✅ 599 个路径 |
| `/api/health/detail` | ✅ 诚实降级：database ok / redis disabled / disk warning（11.51% free）/ secret_manager 已启用（PASETO 指纹 ecd7f3ca） |

### 3.4 Flutter
- `flutter analyze`：**No issues found!**（10.8s）
- `flutter test`：**100/100 passed**（24s）

### 3.5 WebApp / Console 构建
- webapp：`vite build` ✅（1624 modules，4.29s）
- console：`tsc --noEmit && vite build` ✅（140 modules，1.66s）

### 3.6 数据库迁移
- 空库 `alembic upgrade head` ✅（含 `created: eval_snapshots`）
- `alembic downgrade -1` ✅（`dropped: eval_snapshots`）
- 再次 `upgrade head` ✅（幂等重放）

---

## 四、性能测试明细

### 4.1 基准方法
- `scripts/bench-api.py`（默认 7 端点，`--concurrency 10 --requests 100`）
- 环境：uvicorn 127.0.0.1:8766，SQLite 开发库，启用 `RATE_LIMIT_BENCH_TOKEN` 旁路（测量原始吞吐，排除限流干扰）
- 另做一次「无限流旁路」基准以验证限流行为

### 4.2 干净环境（限流旁路开启，并发 10 × 100）

| 端点 | RPS | P50 | P90 | 错误 |
|---|---|---|---|---|
| 健康检查 `/api/health` | 1280 | 7.05ms | 11.23ms | 0 |
| OpenAPI `/api/openapi.json` | 1420 | 6.88ms | 7.72ms | 0 |
| 项目列表 `/api/projects` | 1280 | 7.40ms | 10.40ms | 0 |
| 物料列表 `/api/materials` | 566 | 17.21ms | 19.86ms | 0 |
| 特性开关 `/api/config/feature-flags` | 1520 | 6.36ms | 7.13ms | 0 |
| 用户注册 `/api/auth/register` | 4.4 | 2319ms | 2482ms | 0 |
| 用户登录 `/api/auth/login` | 4.8 | 2076ms | 2197ms | 0 |

### 4.3 限流验证（无限流旁路）
- 高并发下认证端点正确返回 **429**（认证 10 次/分/IP、普通 60 次/分/IP），安全限流生效。

### 4.4 性能结论
- 轻量读端点表现优秀（P50 < 20ms，RPS 566–1520）。
- 注册/登录单请求 369ms（bcrypt cost=12），并发下因同步 bcrypt 串行化升至 ~2.3s —— 见 OBS-004，非发布阻断项。
- 健康阈值对照：读端点 P50/P90 均落在「优秀」（<50ms / <200ms）区间；写端点属已知优化点。

---

## 五、兼容性测试明细

### 5.1 浏览器
- 构建目标：Vite 默认 `'modules'`（现代浏览器：Chrome 87+ / Firefox 78+ / Safari 14+ / Edge 88+）。
- Playwright 视觉回归 `layout.spec.ts`：**10/10 passed**（desktop 1440×900 + mobile 375×812）。
- 说明：本机 Playwright 仅装 chromium；Firefox / WebKit(Safari) 未做真机/多引擎抽检（可作发布后运维抽检项）。

### 5.2 Flutter 多端（iOS / Android / 鸿蒙）
- 鸿蒙工程完整：`flutter_app/ohos/` 含 AppScope + entry + hvigor + `GeneratedPluginRegistrant.ets` + `module.json5`。
- 条件导入完整：`SuokeNetworkImage`（native/stub）、`image_helper`（native/stub）、`platform_info`、`ws_helper` 均采用 `dart.library.io` 条件导入。
- 鸿蒙降级链：cached_network_image → OHOS 回退 Image.network；local_auth / 通知 / 传感器 / GPS / url_launcher 均 try-catch 优雅降级。
- 约束声明：`pubspec.yaml` 锁定 `sdk: ^3.9.2`（不用 Dart 3.10+ 语法，保证 Flutter-OH 3.35.7 可编译）。

### 5.3 版本号一致性
| 位置 | 版本 |
|---|---|
| app/config.py | 1.13.6 |
| flutter_app/pubspec.yaml | 1.13.6+46 |
| flutter_app/lib/config.dart / settings_page.dart | 1.13.6 |
| console-src/package.json | 1.13.6.0 |
| webapp/package.json / public/version.json | 1.13.6 |
| app/mcp/server.py SERVER_VERSION | 1.13.6 |

全链路 8 处一致，无旧版本残留。

---

## 六、安全测试明细

### 6.1 变更面静态审查（TRAE-security-review）
- 范围：未提交 9 文件（eval/llm_judge/base/agents/config）+ 3 个未推送提交（eval 端点、MCP server 版本、eval_snapshot 模型/迁移、health_monitor 时区修复）。
- 结论：**无可利用漏洞**。新端点均 `require_admin` 保护 + SQLAlchemy 参数化查询 + `llm_judge_enabled` 门控诚实 503 降级；无注入/越权/敏感数据暴露。

### 6.2 确定性安全套件（pytest）
| 类别 | 测试文件 | 结果 |
|---|---|---|
| 路径遍历 | test_security_path_traversal.py | 3/3 |
| XSS | test_security_xss.py | 7/7 |
| SQL 注入 | test_security_sql_injection.py | 6/6 |
| MCP 安全 | test_mcp_security.py | 32/32 |
| 鉴权修复 | test_auth_security_fixes.py | 12/12 |
| 缓存隔离 | test_cache_user_isolation.py | 22/22 |
| WebAuthn | test_webauthn.py | 32/32 |
| 认证 | test_auth.py | 19/19 |
| 越权（IDOR） | test_idor_v1_1_1/1_1_2/smart_home_scene/design_modules | 46/46 |
| **合计** | | **179 passed** |

### 6.3 静态扫描
- PASETO 强制：全仓 `jwt/JWS` 命中 0（仅 PASETO），符合项目硬约束。
- 硬编码密钥：`app/` 源码扫描 0 命中。
- 限流：高并发下 429 正确返回（认证 10/min、普通 60/min）。
- 生产构建 sourcemap 暴露源码 → OBS-001（Low）。

---

## 七、回归测试结论

| 轮次 | 范围 | 结果 |
|---|---|---|
| R1 | 确定性安全套件 | 179 passed |
| R2 | v1.13.6 变更模块定向 | 173 passed |
| R3 | 后端全量 | 2347 passed / 2 skipped / 4 xfailed / 0 failed |
| R4 | Flutter 全量 | 100/100 passed |

> 本次验证为「验证型」回归（未做代码修改），无修复后再回归场景；4 项低危观察项不涉及代码缺陷，故无需回归。

---

## 八、发布判定

**✅ 达到发布标准。**

- 功能：四端构建全绿、后端全量 0 失败、Flutter 100/100、后端冒烟正常、迁移往返幂等。
- 性能：读路径优秀，写路径（注册/登录并发）有明确优化点但不阻断。
- 兼容性：Chrome 双断点视觉回归通过、鸿蒙多端降级链完整、版本号全链路一致。
- 安全：变更面无漏洞、确定性安全套件 179 通过、无硬编码密钥、PASETO 强制、限流生效。

**发布后待办（非阻断）**：OBS-001（关闭生产 sourcemap）、OBS-002（修正迁移注释）、OBS-003（修正 bench 脚本文档）、OBS-004（bcrypt 移出事件循环）、Firefox/Safari 真机抽检、磁盘空间巡检（当前本地 11.51% 可用）。

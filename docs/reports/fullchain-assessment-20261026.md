# 索克家居 i-home.life 全景全链路开发进度评估

- **评估日期**：2026-10-26
- **评估范围**：后端领域层、Agent/AI 层、前端四端、部署运维、商业闭环、治理与测试资产
- **评估方法**：**以实测为准，不采信文档自述**。所有数字来自本机亲跑的代码统计、路由注册表、静态检查与全量测试，凡与 README/CHANGELOG 声明不一致处均已标注
- **基线版本**：v1.19.0（提交 `646e78c`）→ 本轮收口至 v1.19.1（`7819c8a` / `38873cc` / `d093d86`）

---

## 一、总结论

**工程实现约 85%，已具备完整的业务骨架与真实的门禁体系；剩余 15% 不在代码质量，而在"已修好但没生效"的发布链路与平台侧外部阻塞。**

本轮之前的状态是：**存在一个 P0 级发布风险——部署脚本所谓的"自动回滚"实际只是把同一份坏代码再重启一次**。这个缺陷已在代码里躺了一个版本，2026-10-16 那次 11 分钟 502 就是它的直接产物。本轮已修复、已测试、已提交、已补发版门禁。

| 维度 | 评分 | 判断依据 |
|---|---|---|
| 后端领域层 | 92 | 88 个 API 模块、795 个 API 路由，87/88 有 HTTP 层测试触达 |
| Agent / AI 层 | 90 | 27 个 Agent、harness 轨迹、三层自进化、OWASP 10 + ATH 5 治理齐备；**但向量库/ControlNet/OSS/Redis 均未配置，能力实际走降级** |
| 前端四端 | 88 | console 76 页 / webapp 24 页 / Flutter 60 页 / 小程序 11 页，无孤儿页 |
| 部署运维 | 88 | systemd + Nginx + FC 定时器齐备；本轮补齐真回滚与配置预检（原 78） |
| 商业闭环 | 60 | 支付/托管仍是内部台账，无第三方资金通道（项目自身已诚实标注，不计为缺陷） |
| 治理与测试 | 90 | 3034 用例全绿、零回退；缺口是 `structural` 模块无 HTTP 测试 |

---

## 二、实测规模（对照文档声明）

| 维度 | 文档声明 | 实测 | 结论 |
|---|---|---|---|
| API 模块 | 84 | **88**（89 文件含 `__init__`） | 文档滞后 |
| API 路由 | 777 | **795**（总注册 799） | 文档滞后 |
| Service | 132 | **133**（134 文件含 `__init__`） | 文档滞后 |
| ORM 模型 / 表 | 147 / — | **147 类 / 149 表** | 一致 |
| Alembic 迁移 | — | **70**，head `o1c2d3e4f5a6` | — |
| Agent | 27 | **27**（22 执行型 + 1 编排 + 4 商业运营，30 文件含 base/harness） | 一致 |
| console / webapp / Flutter | 75 / 19 / 62 页 | **76 / 24 / 60 页** | 文档滞后 |
| 小程序 | — | **11 页** | 新增 |
| 代码量 | — | app **108,205 行**，tests **67,703 行**，测试文件 **197** | — |

> 文档计数（README 与 CHANGELOG）已滞后 1–2 个版本，本轮已按实测校准 README。

---

## 三、门禁实测（本机亲跑，非引用历史报告）

| 门禁 | 结果 |
|---|---|
| 全量 pytest（`-n 4`） | **3034 passed / 2 skipped / 4 xfailed / 0 failed**（3040 collect） |
| 小程序 `tsc --noEmit` | **0 错误** |
| 小程序 `build:weapp` 生产构建 | **Compiled successfully**（48.75s） |
| `flutter analyze` | **No issues found** |
| console `vite build` | ✓ 成功 |
| webapp `vite build` | 1655 模块转换通过（静态资源拷贝被本机沙箱拦截，非代码问题） |
| 部署门禁 `scripts/tests/test_deploy_gate.sh` | **9 / 9 断言通过** |
| 核心链路端点抽查 | 17 项全部存在 |
| 小程序调用的后端端点 | **15 / 15 命中**，无悬空调用 |

---

## 四、全链路分层判断

### 后端领域层（92）

AI 装修全链路（设计 → 算量 → 报价 → 采购 → 施工 → 质检 → 结算）端点齐全，结算环节还有确定性付款门禁：质检无 open/in_progress 问题 + 托管账户全部 released 才放行，未通过返回 409 带 `gates` 明细，无数据时记 `no_data` 放行并如实标注——**不伪装已验收、不伪装已放款**，这是正确做法。

### Agent / AI 层（90）

27 个 Agent 分三类：22 个执行型、1 个 Orchestrator、4 个商业运营型。配套 harness 轨迹、三层自进化管线、治理审计。

**但必须看清一条**：`VECTOR_DB_URL`、`AI_RENDER_BACKEND_URL`、`OPENAI_API_KEY`、`OSS_ACCESS_KEY_ID`、`REDIS_URL` 在本地 env 全部未配置。也就是说 embedding/RAG、ControlNet 渲染、对象存储、多 worker 缓存这四项**实际都在走降级路径**。`/api/config/feature-flags` 已经如实暴露 `vector_db_url_configured=false`、`real_ai_render_enabled=false`，前端不得把 `ai_render_enabled` 读作"ControlNet 已就绪"。

### 前端四端（88）

console 76 页、webapp 24 页、Flutter 60 页、小程序 11 页。**无孤儿页**（此前怀疑的 `wearable_devices_page` 由 `smart_home_page:612` 直接 push，可达）。

小程序是本轮最大的增量：从"9 页本地演示数据"变成"11 页全接真实接口"，且数据源策略做对了——**写操作绝不降级**（业主提交需求必须真进派单池，否则是欺骗），只读接口故障才回退演示数据，且降级时页面显示 `DataSourceBadge` 标注。

### 部署运维（88，本轮从 78 提升）

systemd + Nginx + FC 定时器齐备。短板原在回滚，本轮已修（见第五节）。

### 商业闭环（60）

支付/托管仍是内部台账，无第三方资金通道。项目自己在 CHANGELOG 里标注为"诚实边界"，不计为缺陷——但对外讲"交易闭环"时必须带上这个限定。

---

## 五、本轮已闭环的问题

### P0-1 部署"假回滚"（已修 + 已测 + 已提交 `7819c8a`）

原门禁在健康探针失败时执行 `systemctl restart ihome` —— 把**同一份坏代码**再启一次，脚本自称"回滚"但从没回滚过。

修复三处：

1. **`code_snapshot()`**：rsync **之前**把 `app/ migrations/ alembic.ini` 打包到 `backups/code-pre-<ts>.tar.gz`，指针写 `.last-code-snapshot`，只留最近 5 份；快照生成失败直接 fail-closed，不继续发布。
2. **配置预检提前到 restart 之前**：坏配置根本不会触发重启，把"发布事故"降级为"发布被拦"。
3. **`rollback_code()`**：解包快照 → 重启 → 30s 内复验 `/health`，仍不就绪则**明确要求人工介入**，不再假装恢复。新增 `rollback` 子命令。

配套 `scripts/tests/test_deploy_gate.sh` 用假 `ssh`/`rsync`/`curl` 跑三场景 9 项断言：坏配置被拦且**不重启**、探针失败**真的触发回滚**、全绿**不误回滚**。这类缺陷读代码看不出来，必须有测试。

### P0-2 小程序全链路未入库（已提交 `38873cc`）

18 个新文件 + 30 处修改，共 4831 行。后端 `miniprogram.py` / `wechat_miniprogram_service.py` / `ops_alert_service.py`，前端 4 个 service 层 + 2 个新页面，4 个后端测试文件。

两个实现细节值得记：

- 未配置 appid/secret 时**fail-closed 直接报错**，不签发假 token、不伪造 openid；
- 运营提醒的 webhook 故障**只告警不阻断建单**（业主提交必须成功），手机号在日志里脱敏。

### P1-1 `.env.production` 缺小程序键（已补）

生产机是手工配的 `.env`（有），模板 `.env.production` 没同步 —— 换机或重建部署时小程序登录会直接 502 且无从排查。已补齐 `MINIPROGRAM_*` / `OPS_ALERT_*`，并在 `deploy-remote.sh` 的 `env_preflight` 加了软提示：缺键不阻断发布（后端会 fail-closed），但必须显式告警，避免"发布成功但小程序登录全挂"这种静默故障。

### P1-2 版本号未 bump（已 bump 至 1.19.1）

全链路 17 处同步。**过程中发现一个真问题**：`app_version` 实际被 `.env` 的 `APP_VERSION` 覆盖，只改 `config.py` 的默认值，`/health` 仍然报旧版本。以后 bump 必须同时改 env 与代码默认值。

顺带修掉两处漂移源：

- `flutter_app/lib/pages/settings_page.dart` 把版本号硬编码在 UI 里（每次发版必漏一处），改为读 `AppConfig.appVersion`；
- 新增 `test_backend_and_mcp_version_agree`：`app_version` 必须等于 MCP `SERVER_VERSION`，防止单侧 bump 造成 `/health` 与实际版本不一致。

### P1-3 小程序不在 CI（已加 `miniapp-check`，`d093d86`）

CI 12 → 13 个 job：`npm ci` → `tsc --noEmit` → `build:weapp` → 校验演示回落注入链。typecheck 不再靠人手跑。

### P1-4 演示数据回落是生产默认（已改为构建期控制，`d093d86`）

`ALLOW_DEMO_FALLBACK` 原在源码里写死 `true`。后果不是体验问题而是**数据可信度红线**：接口故障时业主看到"演示项目/演示空间"，会以为是自己的真实资产。

改为构建期常量：生产构建默认 `false`（走错误态如实告知），开发构建默认 `true`（保留无后端联调），需要时显式 `TARO_APP_ALLOW_DEMO_FALLBACK=true` 构建。写操作在任何开关下都不降级。

> 注：该常量在生产包内已被内联成字面量，无法从产物反查名字（已实测确认），因此 CI 断言校验的是注入链而非产物——这一点在 job 注释里写明了，不掩盖。

---

## 六、未闭环的问题

| 优先级 | 问题 | 说明 |
|---|---|---|
| P2 | `structural` 模块无 HTTP 测试 | 88 个 API 模块中唯一缺口。42 个端点、38 个用例只测 service 层，不覆盖鉴权/入参校验/响应序列化 |
| P2 | 47 处 `NotImplementedError` + 5 个返回 501 的端点 | 集中在 matter/commission、IFC/PDF 导出，需进能力清单，避免对外承诺时被误读为已支持 |
| P2 | 14 个 feature flag 在 `app/` 内零引用 | 要么接线，要么删掉，留在配置里会让"开关"变成幻觉 |
| P3 | console 视觉回归 Linux 基线缺失 | `continue-on-error: true`，等于没门禁 |
| P3 | 前端零单测 | 靠 4 个后端契约测试兜底 |

---

## 七、外部阻塞（非代码可解）

**小程序无法发版**，四道平台侧关口全部未过：

1. 微信认证（未通过）
2. ICP 备案
3. 服务器域名登记
4. 代码上传密钥

**FC 定时器令牌 `exp=2027-04-14`，无自动轮换** —— 到期当天三个定时任务会静默 401，且不会有任何告警。这是定时炸弹，建议在令牌到期前加入轮换机制或至少加到期提醒。

---

## 八、下一步建议

1. **部署 v1.19.1 到生产**（真回滚现在才真正生效，这是本轮最大价值）
2. `structural` 补 HTTP 层测试（42 端点，工作量最大但缺口最实）
3. 能力清单：“未实现/500 系列”端点对外可见，避免销售/客服误承诺
4. feature flag 分类清理（接线或删除）
5. FC 定时器令牌轮换机制（外部依赖，需平台侧配合）

---

## 附：本轮提交

| 提交 | 内容 |
|---|---|
| `7819c8a` | fix(deploy): 探针失败真正回滚代码，而非重启同一份坏代码 |
| `38873cc` | feat(release): v1.19.1 小程序全链路接入 + 版本号全链路同步 |
| `d093d86` | chore(ci): 小程序进 CI，演示数据回落改为构建期关闭 |

# CLAUDE.md — i-home.life AI 协作契约

> 索克家居 · **空间健康资产运营商**（AI 存量空间改造 + 智能运营）。本文件是项目级 AI 协作硬约束，随代码版本控制。
> 改 AI 行为请走 PR，可追溯、可 review。**只写 AI 无法从代码推断的项目特有规则。**

## 项目定位

**对外定位**：空间健康资产运营商 ——「一次改造交付，长期健康运营」。面向云南区域内**存量**空间资源（康养 / 疗愈 / 旅居 / 文旅 / 适老住宅）提供 AI 智能化改造与长期运营，是索克生活（`/Users/netsong/Developer/suoke_life/`）生态的**空间供应链与引流入口**。

**装修链路的定位（重要，勿误解为「废弃」）**：AI 装修全链路（设计 → 算量 → 报价 → 采购 → 施工 → 质检 → 结算）是**交付底座**，不对外主打但不得削弱。存量空间改造的唯一交付引擎就是这条链路——砍掉它，「AI 智能化改造」就只剩叙事。对外表述统一为「空间改造交付能力」，而非「装修平台」。

**商业模式约束**：轻资产改造服务商定位——**不持有房产、不做物业运营、不做房地产经纪**。资产由业主/运营方持有，平台提供改造交付 + 智能运营 + 数据服务。写业务代码/文案时不得暗示平台持有或运营不动产。

模块化单体（modular monolith，非微服务，见 `app/config.py` `service_role` 澄清）。
Python(FastAPI) 后端 + Flutter 多端(iOS/Android/HarmonyOS) + webapp(Vite+React，`webapp/`，2026-08-08 起替代旧 `web/` 静态多页，构建产物 `webapp/dist/` 由 Nginx root 服务) + 管理控制台(`console-src/`，React+Vite+TSX，构建至 `webapp/dist/console/`)。
所有路由在 `app/main.py` 无条件 `include_router` 加载。
WebApp 主页（Dashboard）底部悬挂 ICP 备案号「滇ICP备2026015233号-2」并链接 `https://beian.miit.gov.cn/`（见 `webapp/src/components/Shell.jsx` Footer），新增页面不得移除。
根目录 `DESIGN.md` 是「设计版 CLAUDE.md」（Google design.md 格式：YAML front matter 机器可读 token + Markdown 正文设计理念），AI 编写/修改前端 UI 前必读；`npx @google/design.md lint DESIGN.md` 由 CI design-lint job 门禁校验（0 errors）。token 与 Flutter `suoke_theme.dart` / 控制台 `tokens.ts`+`tokens.css` / webapp `tokens.css` 三端对齐，改 token 须三端同步。

## Agent 分类约定（v1.6.0）

两类 Agent，feature flag 独立控制，勿混淆：

- **执行型 Agent**（面向用户交付）：designer/budget/procurement/construction/qa_inspector/settlement/concierge 等 21 个，覆盖家装交付链路。
- **商业运营 Agent**（平台自身运营，借鉴 Polsia 9 大智能体 + 义乌「AI 嵌入生意每一环」）：growth/marketing/competitor_research/finance_recon，受各自 `xxx_agent_enabled` flag 灰度，v1.13.2 起默认 True（best-effort 降级，关闭即回退 enabled=False 诚实标注）。
- **主动 Orchestrator**：`OrchestratorAgent.generate_daily_briefing` 每日聚合 growth + finance 报告，阿里云 FC 定时触发器调用 `https://i-home.life/api/admin/daily-briefing`（受 `business_ops_orchestrator_enabled` 控制，无 K8s/Cron；2026-08-08 域名切换后触发器目标 URL 须为域名 443，不再用 `http://118.31.223.213:8081`）。v1.13.2 起该 flag 默认 True（子 Agent 未启用时 best-effort 降级标注）。v1.15.6 起 `generate_supplier_daily_briefing` 供应商每日经营简报复用同一 FC 触发模式调用 `/api/admin/supplier-daily-briefing`（受 `supplier_daily_briefing_enabled` 默认 True 控制；确定性数据段基于 delivery_orders/users/suppliers/products/escrow_payments 内部表并逐段标注，AI 建议 economy 档 best-effort）。
- **以销定产**：`procurement_demand_driven_enabled`（默认 True，v1.13.2 起）开启后 `procurement_service.drive_procurement_from_bom` 从 designer BOM 反向驱动采购优先级（紧急/常规/可缓），借鉴义乌「以销定产」模式。

商业运营 Agent 数据源诚实标注（GrowthAgent 基于 `agent_feedbacks` 表，非全量调用日志；FinanceRecon 基于 `payment/escrow` 内部表，无 Stripe 对接），禁止伪装实时数据。

## Agent 自进化管线（v1.10.2，借鉴 EverMind EverOS + SkillCorpus + HarnessBank）

三层独立 feature flag 灰度，v1.13.2 起默认全 True（经 59 用例 + 覆盖率 99% + verify 脚本 66 项验证；关闭即回退无记忆无进化静态行为）：
- **P0 Case 提取**（`agent_case_extraction_enabled`）：`AgentRuntime._maybe_extract_case` 从 `AgentTrace` 自动提取结构化 Case（task_intent + approach + quality_score），过滤非目标导向对话，best-effort 不影响主流程。见 `app/services/agent_case_service.py`。v1.13.2 后全链路闭环：主链路端点直连 `think/think_with_tools` 时由 BaseAgent 内建 hook（`_maybe_persist_execution_case`）用最小 AgentTrace 补沉淀；harness.run 设 `agent._harness_trace` 标记 + `extract_case_from_trace` trace_id 去重防双提取；Case/Skill 提取与注入支持 project scope（空间感知，owner_id=project_id）+ recency 排序键（时间感知，`search_cases` created_at / `get_skill_for_injection` updated_at）。
- **P1 Skill 蒸馏 + 检索注入**（`agent_skill_distillation_enabled`）：同主题 Case ≥3 条聚类蒸馏为 Skill（`distill_skill_from_cases`，生成前查重合并避免冗余——SkillCorpus 策展）；`BaseAgent.think/think_with_tools` 执行前检索同类 Case + Skill 注入上下文。
- **P1 Skill 进化 + 诊断归因**（`agent_skill_evolution_enabled`）：`record_skill_outcome` 回写成败计数 → `evaluate_skill_quality` 三维质控（Utility/Robustness/Safety）→ 低质 auto-archive / 高质 DRAFT→ACTIVE；`diagnose_credit_skill_patch` 借鉴 HarnessBank「诊断-归因分离」：LLM 诊断 (WHERE×WHY) 病理 + 确定性代码配对显著性检验（z≥1.96 才采纳），以病理为键而非任务键（抗过拟合）。v1.13.3 起 `record_skill_outcome` 由 BaseAgent 内建 hook `_maybe_record_skill_outcome` 在生产路径真实调用（此前仅 verify 脚本/测试调用，success/fail_count 恒 0 空转）：think/think_with_tools/think_stream 出口注入 Skill 后按确定性判定（reply 非空且非 [mock]/降级占位 → success=True）回写，P1 进化数据层激活；确定性失败（[mock]/思维链泄漏）已回写，语义级失败仍需 LLM 信号（遗留）；v1.15.5 起失败轨迹在 **Case 层**闭环（failure_type 病理分类 + 反模式蒸馏，见「v1.15.5 前沿借鉴落地」节）。
- **v1.14.1 蒸馏/质控生产触发方**（修复 2026-08-16 评估 P0「孤岛函数」）：`run_skill_evolution_cycle`（agent_skill_evolution_service）编排「聚类发现未蒸馏 Case 簇 → 蒸馏 → 三维质控 → DRAFT→ACTIVE 晋升/低质 archive」，生产端点 `GET /api/admin/skill-evolution`（平台管理员；FC 定时触发器可复用 daily-briefing 模式，单周期上限 50 簇/200 评估）；`get_skill_for_injection` 无 ACTIVE 时回退 DRAFT 试用期注入（打破「无使用记录→无法晋升→只注入 ACTIVE」死锁）。`diagnose_credit_skill_patch` 仍无 patch 生产方（诚实遗留）。
- **v1.13.3 全链路闭环**（断点 A–I 全修）：think/think_with_tools/think_stream 与 classify_intent / concierge.generate_response / content_publisher.generate_content_publish_reply 均支持 db/user_id/project_id 透传；`think_stream` 补齐 RAG+进化注入+流后 Case 沉淀（此前流式路径三无）；语音（voice_realtime）、IM 群聊（chat_service harness.run）、产品文案（products/camera_scan/ai_copy）、Skill 实例化（agent_skills）、编排 LLM 分解（agent_orchestration_service `_llm_decompose`）全部纳入注入/沉淀闭环；`_inject_preference_hint` helper 供 /chat 与 /chat/stream 共用 L4 偏好注入。
- 不引入外部记忆服务（EverOS/Raven），全部在模块化单体内自建；DASH/MSA（模型权重层）不适用 API-based 架构，不硬套。
- 用户指南见 `assets/guide/ai-self-evolution-guide.md`，隐私声明见 `assets/legal/agent-memory-privacy-notice.md`。

## Agent 可观测性 + 编排 + 评估（v1.12.x，基于 2026 生产级 Agent 前沿）

- **轨迹落库**：每个 Agent 执行（`harness.run`）按采样率落 `agent_traces` 表（`agent_trace_persist_enabled` 默认 True + `agent_trace_sample_rate`）。`workflow_id` 跨 Agent 传播（同一用户请求的所有 Agent 执行共享），prompt 上下文截断采样防 PII。v1.13.8 起 `tool_calls` 列记录每次工具调用的 tool/arguments/result（arguments 截 200 / result 截 300 字符，整体 4000），实现轨迹可回放（借鉴 DeepSeek Harness「Every run is traceable」，见 `app/agents/harness.py` `_serialize_tool_calls_for_trace`）。
- **多智能体编排**：`OrchestratorAgent.plan_and_delegate`（`agent_orchestration_pipeline_enabled` 默认 True）→ LLM 任务分解（规则兜底）→ `validate_dag` 循环检测 → `run_workflow` 拓扑执行（复用 harness 自动落 trace）→ 结构化聚合（`AgentTaskResult` 防 prompt injection）。子任务失败标 failed 不阻断聚合，诚实降级。**API：`POST /api/agents/orchestrate`**（全链路可达，flag 关闭按规则单任务执行并标注 rule_single）。
- **评估三要素**：`IHomeEval` 新增 FAITHFULNESS/COMPLETENESS/SUFFICIENCY 维度（启发式代理指标，非 LLM judge）+ `per_agent_scores` + `QUALITY_TARGETS` 量化基线。漂移检测 `detect_agent_drift`（基于 `agent_traces` 对比基线，`GET /api/eval/drift`）。
- **成本优化**：`BaseAgent._chat` 确定性响应缓存（`llm_response_cache_enabled` 默认 True，`with_tools=True` 不缓存）；`cost_tiered_routing_enabled` 默认 True（economy 档 Agent 优先 qwen/glm）；Orchestrator `cost_tier="economy"`。
- **治理安全**：OWASP Agentic Skills Top 10 对照审计 `run_governance_audit`（`app/services/agent_governance_audit.py`，只读确定性，`GET /api/admin/agent-governance-audit` 管理员调用）。`mcp_security_hardening_enabled` 默认 True（工具描述防投毒 + SSRF 拦截 + 输出敏感字段清洗）。

## Agent 工具纪律（v1.13.0，基于 2026 工具调用前沿）

- **契约纪律**：`AgentTool` 显式 `required`（仅声明真正必填参数，可选参数标 required 诱导 LLM 幻觉填充）；工具描述统一含「示例：」use-example（工具描述是最高优先级 prompt）。内置工具 11 个 + 管理工具 6 个（`category="admin"` 默认对通用可见列表隐藏，仅 `AdminAgent` 经 `get_admin_openai_schemas()` 显式拉取——渐进披露 + 治理红线）。
- **执行前校验**：`ToolRegistry.execute` 按 parameters 契约校验参数类型（number/string/boolean 等 + 未知参数名拒绝），`tool_argument_validation_enabled` 默认 True，防幻觉参数到达 DB/外部 API。
- **并行执行 + 预算早停**：`think_with_tools` 同一轮 tool_calls 并行（`parallel_tool_calls_enabled` 默认 True，5x 提速）；`agent_function_call_max_tool_tokens` 累计上下文触顶提前终止（`token_budget_hit` 落 `agent_traces` 表，per-agent 评估可观测）。**v1.13.1 并发约束**：有 db（DB 查询工具）必须串行——共享 AsyncSession 并行触发 SQLAlchemy ISCE 冲突致 DB 查询静默降级 fallback（真实数据失效）；仅无 db（纯计算/外部 API）场景并行。
- **成本追踪**：`_chat_single_provider` 提取 LLM `usage` → `think_with_tools` 多轮累计 → `agent_traces` 落库（prompt/completion/total tokens，供 per-agent 成本/效率评估）。
- **L4 双向学习**：`get_user_preference_hint` 同时注入 like 正向示例 + dislike 负向提示（防风格漂移）。
- **工具选择评估**：`app/eval/tool_accuracy.py`（56 条中文用例数据集，11 工具 × normal/boundary/confusable/negative）+ 确定性基线报告；`GET /api/eval/tool-accuracy` 暴露；`QUALITY_TARGETS.tool_selection_accuracy_min=60` / `token_budget_hit_rate_max=20`（漂移检测纳入）。v1.13.5 关键词表消歧打磨后基线 75%→**100%（0 混淆）**：设计类三重工具关键词细分（移除宽泛"方案"）、search_materials 与 get_budget 去"多少钱"冲突、negative 用例按「不应选工具」（predicted None）度量、关键词匹配大小写归一化。v1.13.8 起新增 Minimal 模式基线（`MINIMAL_TOOL_DATASET` 仅 get_budget/get_design_layout 两工具 + `get_minimal_tool_accuracy_report`，隔离工具数量对选择准确率的影响，借鉴 DeepSeek Harness「Minimal mode」）。

## v1.15.5 前沿借鉴落地（2026 评估执行，详见 `docs/frontier-borrowing-2026-08-17.md`）

- **失败学习**（`agent_failure_learning_enabled` 默认 True）：harness FAILED/FALLBACK 轨迹确定性沉淀失败 Case（`agent_cases.failure_type` 病理分类，零 LLM 成本）；同病理 ≥3 条蒸馏「[反模式] Skill」（名称前缀约定，与正向 Skill 分离，不进 outcome 回写）；执行前注入「历史失败教训」。关闭即回退失败不沉淀。
- **协议信任层**：A2A 响应与 `a2a_tasks` 表含 `trace_id`/`evidence` 证据链（全路径诚实标注降级原因）；可验证支付意图端点（`agent_payment_intent_enabled` 默认 True + TTL 600s，HMAC 复用 PASETO 主密钥）——escrow 买家付款端点已绑定 token 校验（v1.15.8，携带即强校验），**仍仅验证不扣款，禁止宣称支付闭环**。
- **语境工程**（`chat_context_compaction_enabled` 默认 True / `chat_context_max_turns=24`）：/chat 与 /chat/stream 服务端压缩超长 history（头部 LLM 摘要 + 尾部保留，摘要失败回退截断）；摘要走 BaseAgent fallback chain（economy 档），勿绕过。
- **复杂度自适应路由**（`adaptive_reasoning_routing_enabled` 默认 True）：`BaseAgent._estimate_task_complexity` 确定性规则（high/low/standard）动态调 `_resolve_chain(complexity)`；economy 档行为与无参旧调用完全兼容，改动链逻辑勿破坏该兼容。

## v1.15.7 第二轮前沿借鉴落地（2026 评估执行，详见 `docs/frontier-borrowing-round2-2026-08-18.md`）

- **ATH/国标信任层审计**：`run_governance_audit` 含 `ath_trust_layer` 独立章节（ATH1-5 五项确定性检查，对齐信通院 ATH 1.0 + 7 项国标）；OWASP 10 项保持独立，改审计勿合并两者（既有测试断言 total=10）。
- **记忆时间衰减**（`memory_time_decay_enabled` 默认 True / `memory_decay_half_life_days=30`）：`search_cases` 排序 = quality × exp(-年龄/半衰期)，候选池 limit×4 供衰减重排；关闭即回退 quality-only 旧排序。
- **org 共享记忆**：`GET /agents/memory/org` 全平台可读；scope=org 写入仅管理员（403）。team 级因无 Team 实体暂缓（P2，禁止伪称已实现）。
- **项目周报**（`project_weekly_briefing_enabled` 默认 True）：`GET /agents/projects/{id}/weekly-briefing` 六段确定性数据逐段标注数据源 + AI 建议 economy 档 best-effort；关闭 503。
- **Robot-Ready**：`robot_ready_service` 五项确定性校验——数据缺失逐项 `insufficient_data`，**全缺不得判不合格**（诚实降级红线）；`spatial-semantics/0.1` 为平台先行定义导出 schema（行业无标准，改 schema 须 bump 版本号并同步文档）。
- **LCC2 语义映射**（2026-09-12 3DGS/LCC 借鉴 P3 余项）：`GET /api/construction/projects/{id}/lcc2-mapping` 导出 `lcc2-semantic-mapping/0.1`（平台先行定义）——空间语义 + 空间数字底座 + 3DGS 资产清单 + 语义实体↔资产确定性映射；**平台不产出 LCC2 二进制**（.lcc2 为 XGRIDS 专有格式，需其 SDK/重建管线，诚实边界），仅语义映射 sidecar。

## 设备链路加固（2026-08-27，穿戴/智能家居接入评估报告落地，详见 `docs/reports/device-link-hardening-20260827.md`）

- **数据完整性校验**：`SensorSnapshotRequest` 数值范围约束（温度 -40~80 / 湿度 0~100 / 光照 0~200000 lux / GPS 纬度 ±90、经度 ±180、accuracy ≥0，越界 422）；`HealthMonitorCreate` 的 `monitor_type` 收窄为 Literal 枚举 + `value` 必需键校验（heart_rate→bpm、spo2→spo2、sleep_quality→sleep_score、fall_detection→fall_detected、activity_tracking→steps；air_quality 兼容历史键不强制）。**改这两处 schema 须同步 Flutter 端上传字段**。
- **桥命令超时与重试**：`scene_automation_service._bridge_send_command` 统一桥命令超时（`BRIDGE_COMMAND_TIMEOUT_SECONDS=10s`）+ 瞬时错误重试 1 次（共 2 次；确定性失败 NotImplementedError/ValueError 不重试）；`pool.get` 建连同样限时。防第三方桥挂起拖垮请求/场景。
- **触发扫描索引化**：`scene_automations.trigger_type` 冗余派生列（从 `trigger_condition.type` 派生，写路径统一：`create_scene`/`update_scene`/`accept_prediction`，测试直构须补该列）+ 索引（迁移 `c2d3e4f5a6b7`），`check_sensor_triggers` 改为 SQL 层按 `trigger_type == "sensor"` 预过滤。
- **凭据加密**：`app/services/device_credentials.py` 用 SHA-256(paseto_secret_key) 派生 AES-256-GCM 密钥，加密 Matter `wifi_credentials`/`thread_credentials` 落库（JSON 存 `{"encrypted": b64}`），解密失败诚实返回 None 不伪装。
- **per-user 限流**：`POST /api/sensors/snapshot` 按用户滑动窗口限流（`sensor_snapshot_rate_limit_per_minute` 默认 30/min，0/负值不限流），补通用 IP 限流与设备高频上报场景的错配；进程内存储，多 worker 不共享（best-effort）。
- **可观测性**：metrics 新增 `device_command_total/duration_seconds`、`scene_execute_total/duration_seconds`、`sensor_snapshot_upload_total`。

**第二批（2026-08-27 P2 遗留修复 + 穿戴/智能家居接入）**：
- **state 并发保护**：`scene_automation_service._device_lock(device_id)` per-device asyncio.Lock 串行化（进程内，多 worker best-effort），命令/场景状态更新锁内 `db.refresh` 再合并。
- **命令/场景异步化**：`DeviceCommandRequest`/`SceneExecuteRequest.execute_async=True` → 请求立即返回 `queued`，BackgroundTasks 独立 session 执行 + WS 回填（`async: true`）；同步路径保持兼容。
- **GB 50311 布线合规**：`plan_wiring` 返回 `weak_current_box`/`safety` 可选字段（接入 `check_weak_current_box`/`check_safety_compliance`）。
- **穿戴 BLE 接入（Flutter）**：`flutter_blue_plus ^2.3.12`（connect 需 `License.nonprofit` 免费档；鸿蒙能力探测降级）；`wearable_ble_service.dart` 扫描/连接/心率（0x180D/0x2A37）/电量订阅；`wearable_devices_page.dart` 页面 + 一键上报 health-monitor（device_id=BLE MAC）。`SensorService` 自适应采样（静止 10Hz / 运动 60Hz，加速度模长差 + 2s 防抖）；smart_home_page 加穿戴入口 + WS 订阅设备状态事件 + 快照 30s 周期上报。
- **米家真机化（后端）**：`python-miio>=0.5.12`；`MijiaBridge.get_devices`（`miio.cloud.CloudInterface` 云清单）/`get_device_state`（`MiotDevice.info` 局域网）/`send_command`（`MiotDevice.set_property` 动作映射 + siid/piid/value 直连）；云接口未初始化 `NotImplementedError`、调用失败 `RuntimeError` 诚实报错；**控制要求服务端与设备同网段**（诚实标注）。

**第三批（2026-09-23 智能家居生态全链路接入修复，测试见 `tests/test_smart_home_ecosystem_chain.py`）**：
- **生态 key 三处单源**：`ecosystem_bridge_status.ECOSYSTEMS[].key` 必须与 `BridgeFactory._bridges` 键逐字一致（`tests/test_ecosystem_bridge.py` 断言），`app/schemas/scene_automation.py` 的 `EcosystemName` Literal 是其白名单——**新增/改名生态须同步这三处**（历史上注册表写 `harmony` 而工厂只认 `harmonyos`，按注册表配置即 ValueError → 恒 pending）。无桥生态（alexa/google_home）已在 schema 层 422 拒绝，不得再放回。
- **凭据唯一生效通道**：项目级 `EcosystemIntegration.config`（AES-256-GCM）。`ECOSYSTEMS[].required_env_keys` 只是历史 env 检测口径（除本模块外无代码读取），**UI/接口不得把它读作项目可用性**；`GET /api/ecosystem/status?project_id=` 才附 `project_configured/has_credentials/credential_keys`（只回露字段名，凭据值永不出接口），`project_configured=null` 语义是「未查询该项目」，前端须与「查询后未配置」区分。
- **命令/场景生态解析必须对称**：`scene_automation_service.resolve_project_ecosystem(db, project_id)` 为单源（项目下首个已配置凭据的生态，无凭据兜底 `matter`）；**不要再给 `DeviceCommandRequest.ecosystem` 加 `default` 硬兜底**——已配米家凭据的项目会被判给 matter stub，命令恒 pending（场景执行同因该默认值而行为不对称）。
- **sync 归因**：`sync_to_ecosystem` 遇无桥生态提前返回 `reason="unsupported_ecosystem"` 且不落库生态对接；**不得归因 `invalid_credentials`**（凭据问题与「生态不存在」是两类故障，归错会误导排查）。
- **鉴权**：`POST /scenes/parse` 与 `GET /matter/device-types` 均需 `get_current_user`（曾匿名可读）；`matter/commission` 仍为 stub 501，实现前不得补假 UI。
- **受限枚举前端须逐字对齐**：`room_type`/`protocol`（`chk_smart_home_scheme_room_type` / `chk_smart_home_scheme_protocol`）与 `device_type`（`DEVICE_TYPES`）在 webapp/Flutter 下拉里多一个键即写库约束错误；`scene_type` 合法值为 `manual/scheduled/triggered/geo`（起床/睡眠等语义属 `scene_name`，触发时机属 `trigger_condition.type`）。

## 不可违反的硬约束（架构红线，违反即 reject）

- **部署**：生产 = 阿里云 ECS + Nginx（stream ssl_preread 分流 8081 + 80→443 + LE 证书，模板 `scripts/nginx-ihome.conf`）+ systemd uvicorn（8001，`scripts/ihome.service`）。阿里云 FC 函数计算仅用于定时触发器（`/api/admin/daily-briefing`）。**禁止引入 K8s/Helm/容器编排方案**。
- **鉴权**：PASETO v4.local。**禁止使用 JWT/JWS**。密钥 ≥32 字节，`paseto_strict_mode=True` 时硬校验（见 `app/config.py` `_validate_paseto_key`）。
- **MCP**：遵循 2026-07-28 规范 8 项（stateless / discover / header-routing / cacheable / MRTR / RFC9207 / Tasks / Server Card）。改 MCP 看齐 `app/mcp/`。
- **缓存隔离**：私有数据 cache key 必须含 `user_id`。`cache_user_isolation_strict=True`（默认），未传 user_id 直接 raise。用 `build_isolated_key` / `get_isolated` / `set_isolated`。
- **配置单例**：`get_settings()` 是 `@lru_cache` 单例（`app/config.py`）。测试中**禁止 `get_settings.cache_clear()`**——它使其他模块 import 时的 `settings = get_settings()` 模块级绑定变成陈旧引用，导致跨文件测试隔离失败（曾致 test_v1129 audit + test_webauthn 全量跑失败、单独跑通过）。改 feature flag 用 `monkeypatch.setattr(get_settings(), "flag", value)`，teardown 自动还原。
- **AI 渲染**：4 级降级链 L0(ControlNet) → L1(mock) → L2(占位) → L3(error)。`ai_render_contract_strict=True` 时客户端 `require_real=True` 且后端不可用 → 503 诚实报错，**禁止移除降级路径**。
- **会话加密**：`allow_plaintext_session=False`（默认）。PASETO 密钥不可用时拒绝明文存储会话消息，防 PII 泄露。
- **诚实降级**：禁止用硬编码假数据伪装真实能力。不可用就明确 503/占位 + 标注（历史教训：v1.1.31 修复 6 处硬编码假数据）。
- **健康声明合规**（Phase 0，继承索克生活口径）：康养/疗愈/适老相关文案**禁止疗效词**（治疗/治愈/降压/降糖/控血糖/消炎/抗癌/根治 等，词表见 `app/services/health_claim_compliance.py` `PROHIBITED_CLAIM_WORDS`），命中即阻断（`health_claim_compliance_enabled` 默认 True）。所有健康相关输出必须携带「非医疗诊断」免责口径（`assets/legal/health-claim-disclaimer.md`）。**平台不做医疗诊断/处方/疗效承诺**，CareAgent 等仅做监测与提醒。此红线与索克生活 `assets/legal/fifteenth_five_year_plan_disclaimer.md` + HC-001~HC-010 对齐，改词表须同步索克侧 `wellness_claim_compliance`。

## 协作四原则（改编自 Karpathy LLM 编程四铁律）

1. **Think Before Coding** —— 需求有歧义先问，多方案先列选项，禁止默写假设。项目有 21 执行型 + 4 商业运营 Agent / 112 Service，猜错代价高。
2. **Simplicity First** —— 最小可行实现。不加未要求的功能/抽象/灵活性/异常处理。140 ORM 模型 + 80 路由已够复杂（`app/api/` 磁盘实为 80 个路由模块，main.py 83 处 include_router 含 2 个公开 .well-known + 1 个总 router）。
3. **Surgical Changes** —— 只动要求改的。禁止顺手重构无关代码、统一风格、删旧注释。每行改动须能追溯到用户请求。
4. **Goal-Driven Execution** —— 给可验证目标而非模糊命令。改 bug 先写复现测试；加功能先写验收用例。pytest 基线 2790 passed 不得回退（collect 2796 = 2790 passed + 2 skipped + 4 xfailed，2026-09-23 生态链路契约用例补齐后全量校准，-n auto 8 worker 实测 9~12 分钟零失败；本机已装 ifcopenshell，IFC 测试不再 skip，但系统 python 无该库——全量必须用 `.venv/bin/python`）。基线门禁数字见 `scripts/test_baseline.json`（改 CLAUDE.md 须同步该文件）。

## 质量门禁（不得绕过）

- `pytest`（全量必须通过，`tests/` 目录；本地 `pytest.ini` 串行执行保异步稳定性，CI 用 `-n auto` 并行见 `.github/workflows/ci.yml`）
- `pre-commit run --all-files`（flake8 max-line-length=120, max-complexity=15；含 `detect-private-key`）
- `mypy`（`mypy.ini`，改后端代码必跑；v1.14.1 起 CI 阻塞门禁，非 allow-failure）
- 新增 API 必须补 `tests/test_*.py`（v1.2.5 教训：曾 37 个 API 模块零测试）
- 控制台视觉回归（`console-src/tests/visual/*`，Playwright + `vite preview`）由 CI job `console-visual` 承载；因基线仅 `*-darwin.png`，**引导期 `continue-on-error: true` 非阻塞**，Linux 基线经 `gh workflow run ci.yml -f update_snapshots=true` 引导提交后须转阻塞并加入 `deploy.needs`（勿长期停留非阻塞）。跑该套件前必须先 `cd console-src && npm run build`——`webapp` 的 `npm run build` 会清空 `webapp/dist/`（含 `console/`），顺序颠倒会让 preview 服务空产物、用例全红假象
- 版本号全链路一致，见 `.claude/templates/version-bump.md`（v1.2.9 教训：曾 11 处漏改）
- 测试基线不得回退：`python scripts/check_test_baseline.py`（v1.17.1 起接入 CI `backend-test` 的 "Check pytest baseline" 步骤，以 `--from-output pytest-ci.log` 复用同一份全量日志不重复跑；pre-commit 侧为手动阶段钩子 `pre-commit run --hook-stage manual test-baseline`）。新增测试后用 `--update` 校准 `scripts/test_baseline.json`，并同步本节基线数字

## 存量空间资产化（Phase 3，2026-09-13）

`space_assets` 台账（`app/models/space_asset.py` + `space_asset_service.py` + `app/api/space_assets.py`，受 `space_asset_ledger_enabled` 默认 True 控制）承载康养/疗愈/旅居/文旅/适老住宅存量空间的「评估 → 改造 → 交付 → 运营」全周期。

- **业态枚举与索克生活单源对齐**：`BUSINESS_FORMATS` 前四项（herb_food_courtyard/forest_herbal_bath/kangyang_study/seasonal_stay）取自索克生活 `lib/screens/suoke/lodge_manager_registration_screen.dart` `_lodgeTypes`，**改任一侧须同步另一侧**，禁止另造口径。
- **轻资产约束在三层强制**（勿绕过任何一层）：schema `model_validator` → service `_validate_holder` → model `platform_role` 默认值；`platform_role` 恒为 `service_provider`，API 层不接受写入（update 时被 pop）。
- **改造状态机不可跳跃**：`_STATUS_TRANSITIONS` 明确禁止 `assessed → operating`（必须经 `in_renovation → delivered`），非法流转返回 409 而非静默改写。
- **就绪度评分只算真实数据**：`compute_smart_readiness` 四维（设备 30/感知 25/场景 25/合规 20），无数据项计 0 分并在 breakdown 标注，禁止虚增。
- 台账归属按 `owner_id` 隔离（非 admin 仅见自己的资产）；`summary?all_owners=true` 仅 admin，否则 403。
- **业主端接线（v1.17.2）**：webapp `webapp/src/pages/SpaceAssets.jsx`（路由 `/space-assets`，导航「空间资产」）承载业主侧台账——`NEXT_STATUSES` 与后端 `_STATUS_TRANSITIONS` 对齐（`assessed` 不出「运营中」），策略 503 时透出 `space_asset_ledger_enabled=False` 不回退空态；单测 `SpaceAssets.test.jsx`。控制台侧契约见 `console-src/tests/visual/batch15.spec.ts`。

## 适老改造政策落地（v1.17.0，八部门《促进智能家居消费行动方案》适老化供给）

- **适老套餐与 F41 方案分工**：`PKG-ELDERLY-BATH` / `PKG-ELDERLY-ROOM` / `PKG-ELDERLY-FULL`（`partial_renovation_service.QUICK_INSTALL_PACKAGES`，一口价 + 干法 + 0 搬家）出**可售定价**，F41 `elderly_adaptation_service` 出**合规条目**（GB 50763-2012 + HC-006）；两者经 `space_assets.retrofit_package_code` 关联，勿另造一套适老条目口径。
- **适老元数据只挂适老套餐**：`elderly_theme` / `target_occupant` / `accessibility_standard` / `subsidy_category` / `elderly_design`（政策四维：尺寸适配/操作便利/方言识别/安全性能）；`elderly_design` **只声明适用维度**——方言识别仅「全屋」套餐声明，卫浴/卧室不硬凑（禁为凑齐四维编造能力）。
- **补贴预检诚实红线**（`elderly_subsidy_service`，受 `elderly_subsidy_precheck_enabled` 默认 True 控制）：不内置任何地方官方目录（`max_subsidy_per_unit` 未知即留空并在 warnings 强制标注）；个人资格（年龄/失能等级/困难身份）**不参与确定性判定**；输出恒带 `is_estimate=True`，禁止宣称「已获补贴/已通过核定」；新增地方档案走 `SUBSIDY_POLICY_PROFILES` 配置 + 版本号，禁止把地方标准写死进逻辑。
- 补贴五大刚需场景枚举（`SUBSIDY_CATEGORIES` 前五项）与地方补贴目录口径对齐，改词表须同步公开政策口径来源；无 LLM、无外部调用，纯确定性规则。
- **控制台接线**：`console-src/src/pages/ElderlyAdaptationPage.tsx` 承载套餐目录（只渲染 `elderly_theme=true`，非适老套餐不误标）+ 补贴预估；按钮与结果**必须标注「非资格认定」**，UI 不得读作补贴资格结论。视觉/交互契约见 `console-src/tests/visual/batch14.spec.ts`。
- **业主端接线（v1.17.2）**：webapp `webapp/src/pages/ElderlyPackages.jsx`（路由 `/elderly-packages`，导航「适老改造」）同口径只渲染 `elderly_theme=true`，按钮「补贴预估（非资格认定）」+ 结果恒带 `Badge` 「预估 · 非资格认定」并原样透出 `pre.warnings` / `pre.disclaimer`；单测 `ElderlyPackages.test.jsx`。
- **适老设备类型**：`smart_devices.device_type` 允许集单源为 `app/models/smart_home.py` 模块级 `DEVICE_TYPES`（CheckConstraint SQL 由单源派生），含 5 类适老/康养设备（fall_radar/emergency_call/care_bed/health_monitor/service_robot）；**改允许集必须同步 alembic 迁移**（SQLite 无原生 DROP CONSTRAINT，走 batch_alter_table，参考 `a3b4c5d6e7f8`），否则模型与 DB 漂移。

## 分端规则索引（按需加载，勿全读）

| 任务上下文 | 加载文件 |
|-----------|---------|
| 后端 Python / FastAPI / ORM / alembic | `.claude/guides/backend.md` |
| Flutter 多端 / 鸿蒙 / PWA | `.claude/guides/flutter.md` |
| React Web 控制台 (console-src) | `.claude/guides/web-console.md` |
| MCP / Agent / A2A 开发 | `.claude/guides/mcp-agent.md` |
| 测试编写规范 | `.claude/guides/testing.md` |
| 前端 UI / 视觉身份（webapp / console / Flutter 通用） | 根目录 `DESIGN.md` |
| 版本号升级 | `.claude/templates/version-bump.md` |
| 新增 API 模板 | `.claude/templates/new-api.md` |

> 上述 guide / template 文件若不存在，按需创建时参考对应源码目录，勿臆造。

## 多 LLM fallback chain

`deepseek → qwen → glm → doubao`（`llm_fallback_enabled=True`）。改 LLM 调用走 `BaseAgent._chat()`，勿绕过 fallback。

## 工作目录

- 后端根：`/Users/netsong/Developer/i-home.life`
- 测试：`tests/`（含 `e2e/`）
- 部署脚本：`scripts/`（`deploy-production.sh` / `bump-version.sh` / `check_schema_drift.py` / `rollback.sh` 通用回滚）

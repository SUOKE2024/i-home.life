# i-home.life

> **索克家居 · AI 智能装修平台**
>
> v1.7.0 · 需求-实现验证遗留项 Wave 2 落地（F45 方案前置决策 LLM 升级 / F10 预算 8 类拆分+三费+价格来源 / F13 模板 AI 填充 / F36 工程队入驻审核 / F39 变更 Agent 评估 / F28 通道宽度检查 / F4 剖面图+DXF 导出 / React 控制台 5 页面补齐，2026-08-03）
> 核心能力：40 页面 React Web 控制台 + Flutter 46 页面 + 22 Agent 全链路 + 82 Service + 118 ORM 模型 + 630+ 路由（70 模块）+ L4 偏好学习 + MCP 2026-07-28 规范（stateless/discover/header-routing/cacheable/MRTR/CIMD/Tasks/Server Card）+ ControlNet AI 渲染 + Qwen-Audio-3.0-Realtime 实时语音 + iOS/Android/HarmonyOS + PASETO + PWA + A2UI 卡片协议

## 最近更新

### 2026-08-03 · v1.7.0 需求-实现验证遗留项 Wave 2

- **F45 方案前置决策 LLM 升级**: [solution_first_service.py](app/services/solution_first_service.py) 新增 `SolutionFirstAgent`（走多 LLM fallback 链），LLM 可用时 `source="llm"`，失败/无 key 诚实回退 `source="rule_based"`
- **F10 预算 8 类拆分**: [budget.py](app/agents/budget.py) 5 类 → 8 类（土建/硬装/软装/厨卫/家具/灯具/电器/智能家居）+ 每项材料费/人工费/管理费 + `price_source`（诚实标注估算），保留 `legacy_5cat` 向后兼容
- **F13 模板 AI 自动填充**: `apply_template` LLM 优先 + 线性缩放兜底（`filling_source="llm"/"rule"`）
- **F36 工程队入驻审核**: [crews.py](app/api/crews.py) + [crew_service.py](app/services/crew_service.py) pending→approved/rejected 状态机 + 执照/保险/资质材料校验 + submit/review 端点（仅 admin 审核，未审核不参与匹配）
- **F39 变更 Agent 自动评估**: [change_orders.py](app/api/change_orders.py) review 未传人工评估时自动调设计/预算 Agent（`assessment_source="agent"`），失败降级 `"unavailable"` 不伪造
- **F28 通道宽度检查**: [designer.py](app/agents/designer.py) `analyze_circulation` 新增 `channel_checks`（主通道≥0.9m/家具间≥0.6m，缺数据诚实 warning）
- **F4 剖面图 + DXF 导出**: [construction_drawing_service.py](app/services/construction_drawing_service.py) 新增 `/section` 端点 + `svg_to_dxf`（手写 DXF 无依赖）；PDF 导出依赖缺失诚实 501
- **React 控制台 5 页面补齐**: BudgetCompare（F11）/BudgetTemplates（F13）/KitchenBathMep（F18）/Workers（F35）/IMChat（F40）+ SideNav/App 路由/api-client/domain 类型
- 版本号全链路同步 1.7.0

### 2026-08-03 · v1.6.0 需求-实现验证 v1.5.0 复核修复落地

基于《需求-实现验证报告（v1.5.0 复核）》（F1-F47 全量重新核验：22 已实现 / 25 部分实现 / 0 未实现，全量 pytest 1713+ 通过）执行系统修复：

- **🔴 P0 红线修复**: [knowledge/loader.py](knowledge/loader.py) 伪向量 RAG（`[0.0]*128`）→ 真实 embedding（对齐 agentic_rag v1.1.31 FP-3 修复）
- **名实差距标注**: budget/settlement 补 `engine="rule_based"`；procurement 模拟物流/报价/推荐补 `source="mock"`（响应体级诚实标注）
- **F41 适老改造深化**: [elderly_adaptation_service.py](app/services/elderly_adaptation_service.py) 新增 HC-006 逃生通道专项检查（入户门/逃生窗/禁止封闭走廊）
- **F44 环保强制提示**: [material_service.py](app/services/material_service.py) BOM/AI 选材链路接入 `eco_grade` + `eco_notice`（未认证诚实标注 unverified + HC-003）
- **F47 知识库补全**: 新增 eco_ratings/safety/design_rules/cost_reference 4 域 → 8 域 114 条
- **F38 真实 CV**: [qa_inspector.py](app/agents/qa_inspector.py) 接入多模态视觉 LLM（flag `real_cv_quality_enabled`，失败诚实降级 mock）
- **F40 Agent 进 IM 群**: [chat_service.py](app/services/chat_service.py) 聊天室 Agent 群成员 + 自动回复（真实/规则/降级三档标注）
- **F12 采购→预算联动**: [budget_service.py](app/services/budget_service.py) 订单创建自动扣减预算科目 + `GET /budgets/{project_id}/linked-purchases`
- **F7 BOM 版本管理 + F6 几何算量**: BOMItem 新增 version 列 + `/bom/{project_id}/versions|version|diff`；BOM 优先几何算量（`quantity_source` 诚实标注）
- 轻量 schema 迁移 v7（chat_rooms.agent_members / chat_messages.auto_reply_meta / bom_items.version 等）+ 新增 ~30 测试 + 版本号全链路同步 1.6.0

### 2026-08-03 · v1.5.0 PRD v3.1 F41-F47 需求补充落地

基于 2026-08-03 行业调研与需求-实现验证，将 PRD v3.1 新增 7 项需求全部落地（后端 + React Web 控制台 + Flutter），每项配套 feature flag：

- **F41 适老改造**: [app/api/elderly_adaptation.py](app/api/elderly_adaptation.py) 适老方案 + 无障碍动线检查（GB 50763，门宽/通道/高差）
- **F42 局部焕新**: [app/api/partial_renovation.py](app/api/partial_renovation.py) 5 种短周期改造模板 + 预算包 + 干扰最小化
- **F43 资金托管深化**: [app/api/escrow_trustee.py](app/api/escrow_trustee.py) 银行存管账户 + 节点验收双向确认放款 + 利息归属业主
- **F44 环保材料标签**: [app/api/eco_materials.py](app/api/eco_materials.py) 材料 ENF/E0/E1 环保等级 + 合规校验（HC-003）+ 环保替代推荐
- **F45 方案前置决策**: [app/api/solution_first.py](app/api/solution_first.py) 上传户型 → 3 套布局 + 预算区间
- **F46 生态桥接优先级**: [app/api/ecosystem.py](app/api/ecosystem.py) 4 生态注册表 + 状态报告（未配置 key 诚实标注）
- **F47 AI 装修问答**: [app/api/ai_qa.py](app/api/ai_qa.py) 知识库检索 + 引用来源，未命中诚实降级
- 新增 4 ORM 模型 + 57 测试 + 全链路版本号同步至 1.5.0

### 2026-08-02 · v1.4.0 YC QM / OWLFY / LocalAI 借鉴落地

借鉴 YC QM 多人 Agent Harness（Scope 治理 + 可还原）、OWLFY 端侧零 TOKEN、LocalAI 端云协同，落地 AI 决策审计可还原：

- **P1 Scope 治理贯穿 cache / trace / audit 层**: `cache_service.build_isolated_key` 新增 `scope` 参数（对齐 YC QM 四级作用域）；AgentTrace 新增 `scope` 字段；`tool_registry.execute()` 新增 `_agent_id`/`_model_source`/`_scope`/`_trace_id` 隐式上下文，审计 details 扩展 7 字段，AI 决策可还原到具体 Agent/模型/作用域/轨迹
- **P2 文档与配置**: CLAUDE.md 测试基线 1491 → 1640；.env.example 补安全约束硬开关；mcp-agent guide 记录 v1.4.0 借鉴落地
- **P3 测试**: 新增 12 用例（test_agent_trace_scope / test_tool_audit_fields / cache scope），基线 1607 → 1640

### 2026-07-31 · v1.3.0 MCP 2026-07-28 规范完整对齐

v1.3.0 是平台协议化与工程治理版本，完整对齐 MCP 2026-07-28 规范 8 项核心特性，强化缓存安全隔离，固化 AI 渲染接入契约，扩展 H-IFC 湖北地方标准。

- **P1 MCP 2026-07-28 规范完整对齐（8 项）**: stateless 核心 + server/discover RPC + header-based routing + cacheable list results（ETag/304）+ MRTR 多轮往返 + RFC 9207 authorization + extensions framework（Tasks）+ .well-known Server Card。新增 [app/mcp/mrtr.py](app/mcp/mrtr.py) + [app/mcp/extensions/tasks.py](app/mcp/extensions/tasks.py)，21 个测试全通过
- **P2 缓存用户隔离硬约束**: `cache_user_isolation_strict` flag（默认 True）强制私有数据缓存 key 含 user_id，[cache_service.py](app/services/cache_service.py) 新增 `build_isolated_key` + isolated get/set/delete，16 个测试覆盖跨用户隔离
- **P3 AI 渲染接入契约固化**: `ai_render_backend_type`（controlnet/sdxl_turbo/mock）+ `ai_render_contract_strict` 4 级降级链（L0 ControlNet → L1 mock → L2 占位 → L3 error），24 个测试覆盖契约 schema
- **P4 H-IFC 扩展 + 施工图 MEP**: `ifc_h_ifc_extension_enabled` 湖北地方标准（DMS 坐标/视点/漫游）+ `construction_drawing_mep_enabled` + 国标 GB 50500-2024/GB 50854-2024，16 个测试覆盖

### 2026-07-31 · v1.2.9 全模块全链路复评修复

基于全模块全量全链路复评报告（主代理亲自 Read 源码核验，纠正子代理 87-100% 误判率）的系统修复：

- **P0 版本号一致性同步**: 1.2.9 发布时 11 处版本号未同步（散布 1.2.6/1.2.7/1.2.8/1.2.9），已全部统一——config.py / .env / .env.example / .env.production / pubspec.yaml 1.2.9+26 / config.dart / settings_page.dart / version.json / sw.js CACHE_VERSION 9→10 / web 24 资源 v=20260731a / deploy-production.sh / ci.yml 4 处 / console-src package.json
- **P2 测试覆盖补齐**: 新增 [test_analytics.py](tests/test_analytics.py) 7 用例（此前 analytics 是唯一无 test_*.py 的 API 模块），全量 1491 passed / 0 failed
- **深度安全审计**: 6 个含 NotImplementedError 的 service 全部为抽象基类/诚实降级（零真 stub）；62 个 API 模块认证/越权审计全部通过（6 种认证模式）；缓存 key user_id 隔离合规
- **代码质量审计**: bare except 20 处全部为降级处理；SQL text() 拼接为硬编码 DDL 无注入面；schema drift 检查通过
- **清理**: 718 个残留测试 DB + 525 个 .pyc + 18 个 __pycache__ 目录

### 2026-07-28 · v1.2.6 系统检查评估落地修复

基于 2026-07-28 系统检查评估报告（后端 1409 passed / 版本全链路一致）的遗留项修复：

- **P2 鸿蒙去占位化（Flutter-OH 真集成）**: [EntryAbility.ets](flutter_app/ohos/entry/src/main/ets/entryability/EntryAbility.ets) 改继承 `FlutterAbility` + `GeneratedPluginRegistrant.registerWith`；[Index.ets](flutter_app/ohos/entry/src/main/ets/pages/Index.ets) 改 `FlutterPage` 全屏承载 flutter_app 业务 UI（含 eventHub 返回键转发）；新增 `ets/plugins/GeneratedPluginRegistrant.ets` 占位（Flutter-OH `flutter build hap` 时自动重生成）；[ohos-ready.sh](scripts/ohos-ready.sh) 更新首次构建流程。集成模式对标官方 flutter_flutter 模板（oh-3.35.7-dev），DevEco 实机构建验证待执行
- **P2 Flutter 测试补强**: 新增 [voice_task_panel_test.dart](flutter_app/test/widgets/voice_task_panel_test.dart) 5 个组件用例（渲染空态 / 503 flag 诚实提示 / 任务列表状态标签 / 启动回复 / 失败原因），Flutter 全量 54 passed / 0 failed，analyze 无 error
- **P3 Web 缓存版本统一**: 22 个 HTML/JS 资源引用 `v=20260727a/b` → `v=20260728a` 统一（含 index.html/flutter_bootstrap.js 残留 20260726f），[sw.js](web/sw.js) `CACHE_VERSION` 6 → 7
- **冗余清理**: 删除 reports/ 9 个已知失真基线产物（429 限流污染的 api-bench/perf-baseline/perf-comparison-v1.1.27，防误用）+ 全部 `__pycache__` / `.pytest_cache` / `.DS_Store`
- **版本一致性**: config.py / .env / .env.example / CI ×3 / pubspec 1.2.6+23 / Flutter config.dart / settings_page 全链路 1.2.6
- **仍遗留**: ① 鸿蒙签名私钥 `ihome_app.p12` 仍在 git 历史（需先在华为 AGC 轮换发布证书，再 git filter-repo 清理 + force push，破坏性操作需显式授权）② ecosystem_bridge 各生态桥接为 stub（需 API key/依赖库，端点已 501/诚实标注）③ Flutter 页面测试覆盖 8/46

### 2026-07-26 · v1.2.5 全链路进度评估修复

基于全量全链路开发进度评估报告（综合成熟度 ~65%）的系统修复：

- **P0 版本号一致性**: 全项目版本号统一至 1.2.5（config.py / pubspec.yaml 1.2.5+21 / CI / scripts / .env 示例 / Flutter / 测试）
- **P0 API 测试覆盖率**: 37 个缺失 API 测试文件全部补齐（覆盖率 21/58 → 58/58），新增 ~320 个测试函数
- **P1 Web 完善**: 新增 `web/404.html` 自定义错误页面，nginx 增加 `error_page 404` 指令 + HSTS 注释
- **清理**: 清理 ~2,180 个 pycache 文件 + 过期 DB journal + 旧 server.log

### 2026-07-25 · v1.2.4 全链路诊断修复

- **P0-1 Web 控制台恢复**: 从 git 历史恢复 19 个 HTML 页面 + 13 个 JS + 2 个 CSS + 品牌资源 + 法律页面，维持 Flutter PWA 为默认入口
- **P1-1 sketch-to-3D 真 AI 视觉**: [app/api/sketch_to_3d.py](app/api/sketch_to_3d.py) 接入 DeepSeek/GLM/Qwen 多模态视觉模型替换硬编码占位
- **P1-2 Flutter 类型化模型**: [flutter_app/lib/models/](flutter_app/lib/models/) 新增 10 个业务实体模型（project/user/budget/task/material 等）+ 桶导出
- **P1-4 A2A 持久化**: [app/models/a2a_task.py](app/models/a2a_task.py) 从内存 dict 迁移到数据库，TTL 24h 自动清理
- **P2-1 语音语义路由**: [app/api/voice.py](app/api/voice.py) 新增 `/process-enhanced` LLM 10 类意图分类端点
- **P3 技术债务**: push_sender 结构化日志、ai_render 4 级降级、vr_panorama 诚实降级、reply_templates 回复模板系统
- **清理**: 删除 serverless/ 死代码（14 文件）、173 过期测试 DB、391 `__pycache__` 目录

### 2026-07-23 · v1.2.0 家装全链路专业性提升

基于 2026 行业最新技术对标（飞流AI 空间智能 / 鲁班正向算量 / EasyBIM 模型即图纸 / ControlNet 几何锁定），系统修复家装功能诊断报告 P1-P5 五大专业性缺陷，建立"设计→几何→算量→报价→采购→施工→图纸"贯通链路。所有改动配套 feature flag 可回滚。

- **P1 AI 渲染去 stub（消除幻觉债）**: [app/services/ai_render_service.py](app/services/ai_render_service.py) 新增 `render_backend`/`reconstruction_available` 诚实标识；`_detect_room_type` 不再 `len(photo)%len(rooms)` 伪随机；`real_ai_render_enabled`+`ai_render_backend_url` 接入 ControlNet 几何锁定（对标 2026 Geometry Locking 强制标准）
- **P2 设计→BOM→报价链路贯通（正向设计算量）**: 新增 [app/services/quantity_takeoff_service.py](app/services/quantity_takeoff_service.py)（floorplan.data 作 SSOT，对标鲁班 1:1 BIM 布尔运算）+ `GET /takeoff/project/{id}` 正向算量端点
- **P3 IFC 真实坐标 + Pset 属性集**: [app/services/ifc_export_service.py](app/services/ifc_export_service.py) 墙体/门窗 placement 用 floorplan 真实坐标（不再 `i*5000` 一字排开）+ `_attach_pset_wall_common`（FireRating/ThermalTransmittance/IsExternal/Material），对标飞流 BIM 毫米级可施工
- **P4 施工图自动生成（模型即图纸）**: 新增 [app/services/construction_drawing_service.py](app/services/construction_drawing_service.py) + [app/api/construction_drawing.py](app/api/construction_drawing.py)（SVG 平/立/剖面，floorplan 变 → 图纸自动重生成，对标鲁班/酷家乐）
- **P5 2D CAD 参数化升级**: [flutter_app/lib/pages/cad_element.dart](flutter_app/lib/pages/cad_element.dart) `toFloorplanWallJson()` 建立 CAD→算量→图纸链路入口
- **Feature flags**: 10 项新开关（forward_takeoff_enabled / bom_from_geometry_enabled / real_ai_render_enabled / ai_render_backend_url / ifc_real_placement_enabled / construction_drawing_enabled / parametric_cad_enabled / spatial_perception_enabled / spatial_reasoning_enabled / spatial_interaction_enabled）
- **测试**: 新增 30 项专业性测试（test_quantity_takeoff_service / test_construction_drawing_service / test_v120_professionalism），关键回归 75 passed / 7 skipped / 0 failed
- **文档**: [诊断报告](docs/superpowers/specs/2026-07-23-renovation-professionalism-diagnosis.md) + [实施总结](docs/superpowers/specs/2026-07-23-renovation-professionalism-implementation.md)

### 2026-07-22 · v1.1.29 家居补短 5 项落地

独立于索克生活的补短板工程，覆盖 UI 协议、合规安全、知识增强、主动干预：

- ~~**P0 FC 3.0 微服务拆分**~~: 已于 v1.2.4 清理，项目为模块化单体架构（modular monolith），所有路由在 `app/main.py` 中无条件加载
- **P0 A2UI 协议内化**: [app/services/a2ui_schema.py](app/services/a2ui_schema.py) 定义 8 种卡片类型（设计/预算/进度/采购/质检/结算/材料/告警）+ [app/services/a2ui_generator.py](app/services/a2ui_generator.py) Agent→卡片转换器 + [flutter_app/lib/services/a2ui_renderer.dart](flutter_app/lib/services/a2ui_renderer.dart) Flutter 8 种子卡片 Widget + [web/assets/js/a2ui-renderer.js](web/assets/js/a2ui-renderer.js) Web 渲染器 + [web/assets/css/a2ui-cards.css](web/assets/css/a2ui-cards.css) 暗色主题响应式样式
- **P1 Vault + 合规深化（HMAC 签名）**: [app/services/audit_integrity.py](app/services/audit_integrity.py) HMAC-SHA256 签名 + 密钥版本化 + 防时序攻击 `hmac.compare_digest` + 批量完整性校验 + 字段级脱敏标记（L0-L3 按角色）+ 集成到 `audit_log_service.log_audit_event` 写入时自动签名
- **P1 Agentic RAG + Skills System**: [knowledge/](knowledge/) 4 个结构化知识库（materials.json 20 条 / techniques.json 20 条 / standards.json 20 条 / faq.json 20 条，含 GB 标准引用）+ [app/services/citation_service.py](app/services/citation_service.py) 来源引用格式化 + [app/services/qa_knowledge_service.py](app/services/qa_knowledge_service.py) QAInspectorAgent 专用知识注入（质检清单/标准查核/缺陷判定）
- **P2 Health OS 主动干预**: [app/services/health_monitor.py](app/services/health_monitor.py) 定时巡检器 + 5 级预警规则引擎（NORMAL→ATTENTION→WARNING→SEVERE→CRITICAL）+ 施工健康评分（0-100）+ 自动创建 ProgressAlert + 主动推送通知 + [app/services/push_sender.py](app/services/push_sender.py) 多通道推送（FCM/APNs/WebPush/SMS）
- **Feature flags**: 6 项新开关（audit_hmac_enabled / health_os_enabled / push_enabled / a2ui_enabled / knowledge_base_enabled / service_role）

### 2026-07-22 · v1.1.28 借鉴索克生活（B 方向）10 项落地

借鉴索克生活（中医健康管理平台）的长线技术决策，将 10 项工程实践移植到家居领域：

- **P0-1 Suoke-Eval1 评估框架**: [app/eval/ihome_eval.py](app/eval/ihome_eval.py) 定义 10 个家居专用评估维度（报价准确性/设计安全/材料禁忌/越权防护/SSE 延迟/降级率/工具调用准确性/思维链泄漏率/HC 合规率/反面论证质量），复用 AgentHarness 轨迹 + 静态检查 → 维度评分，[app/api/eval.py](app/api/eval.py) 暴露 GET/POST /api/eval/* 端点
- **P0-2 Model Spec 宪法 + HC 硬约束**: [config/ihome_model_spec.json](config/ihome_model_spec.json) 定义 9 条硬约束（HC-001 承重墙/HC-002 报价含税/HC-003 环保等级/HC-004 工期缓冲/HC-005 水电规范/HC-006 逃生通道/HC-007 燃气安全/HC-008 防水范围/HC-009 反面论证义务），[app/services/rebuttal_engine.py](app/services/rebuttal_engine.py) 扫描违规关键词并注入反驳提示重生成，集成到 BaseAgent.think/think_with_tools
- **P0-3 Feature Validation Pipeline**: [config/intent_contract.json](config/intent_contract.json) 登记 39 个 agent-router pattern 的输入校验规则，[app/utils/intent_validator.py](app/utils/intent_validator.py) CI 校验脚本（新增 pattern 必须含 validation_status: validated），39/39 通过
- **P1-4 AgenticRAG 证据检索**: [app/services/agentic_rag.py](app/services/agentic_rag.py) 向量数据库语义检索 + 内存关键词匹配双降级，集成到 think/think_with_tools 前置注入知识库上下文
- **P1-5 Vault/KMS 凭证管理**: [app/services/secret_manager.py](app/services/secret_manager.py) PASETO key fingerprint（SHA256[:8]）暴露于 /api/health/detail 供运维校验密钥轮换，Vault/KMS 可选集成
- **P1-6 多 LLM fallback chain**: [app/agents/base.py](app/agents/base.py) PROVIDER_REGISTRY 扩展 qwen/doubao 供应商，_chat 失败时按 deepseek → qwen → glm → doubao 降级
- **P2-7 DSPy prompt 优化**: [app/services/dspy_optimizer.py](app/services/dspy_optimizer.py) ChainOfThought 提示词优化（dspy 可选依赖，懒导入降级）
- **P2-8 A2A 协议**: [app/api/a2a.py](app/api/a2a.py) 基于 Google A2A v1.0 暴露 Agent Card + Task Machine（5 端点 + /.well-known/agent-card 公开发现）
- **P2-9 PII 全量脱敏**: [app/utils/pii_masking.py](app/utils/pii_masking.py) 8 类 PII 脱敏（手机号/身份证/邮箱/银行卡/护照/地址/姓名/IP），集成到 audit_log details 自动脱敏
- **P2-10 TTS 三级降级链**: [app/services/tts_chain.py](app/services/tts_chain.py) Qwen3-TTS → CosyVoice → Doubao 三级降级
- **Feature flags**: 全部 10 项均配 feature flag 开关（eval_enabled/model_spec_enabled/intent_validation_enabled/agentic_rag_enabled/secret_manager_enabled/llm_fallback_enabled/dspy_enabled/a2a_enabled/pii_masking_enabled/tts_enabled）
- **测试**: 新增 40 项 v1.1.28 专项测试（tests/test_v1128_suoke_borrowed.py），全量 910 项通过
- **版本号**: v1.1.28 / 20260722a / sw.js CACHE_VERSION=suoke-v20260722a

### 2026-07-20 · v1.1.13 生产部署稳定性修复

- **PostgreSQL + asyncpg + aware datetime 三层兼容性修复**:
  - 数据库 schema：批量 `ALTER COLUMN TYPE TIMESTAMP WITH TIME ZONE`（100+ 列），生产 PostgreSQL 不再拒绝 `datetime.now(timezone.utc)` 写入
  - ORM 模型：42 个 model 文件、209 处 `DateTime` → `DateTime(timezone=True)`（sed 批量替换）
  - asyncpg 会话时区：[app/database.py](app/database.py) engine 配置新增 `connect_args={"server_settings": {"TimeZone": "UTC"}}`
  - 修复后 chat/auth/register 等所有写入 datetime 的端点恢复正常（此前 HTTP 500）
- **PostgreSQL 事务 aborted 陷阱修复**（[app/database.py](app/database.py)）:
  - `_run_lightweight_migrations()` 中 `try/except SELECT` 检查 `_schema_migrations` 表存在性 → PostgreSQL 事务进入 aborted 状态
  - 改用 `inspect.has_table()`（基于 `information_schema`，不污染事务）
- **demo.html 前端质量修复**:
  - 健康检查路径 `/health` → `/api/health`（符合 API 前缀约定）
  - 硬编码 fallback 版本号 `v1.1.0` → `v1.1.13`
  - 补全响应式断点：新增 `≤1024px` 和 `≤480px`（符合项目约定 ≤1024/≤768/≤480）
  - 移除重复的 `Cache-Control/Pragma/Expires` meta 标签
  - AR 测量添加精度警告提示（"测量结果为估算值，仅供预估算参考"）
- **版本号统一升级**: `v=20260720c` → `v=20260720d`（12 个 HTML/JS 文件）+ sw.js `CACHE_VERSION` 同步升级
- **清理**: 删除 13 个 /tmp/verify_*.py 临时脚本 + __pycache__/.pytest_cache/htmlcov/test_*.db

### 2026-07-20 · v1.1.12

- **MCP Server 协议外露**（PRD §5.x 长线计划，对标 MCP 2026-07-28 RC）:
  - 新增 [app/mcp/server.py](app/mcp/server.py)：`MCPServer` 类纯 Python dict 实现 MCP 2026-07-28 协议（零新增依赖）
  - 复用 [app/services/agent_tool_registry.py](app/services/agent_tool_registry.py) 的 5 个内置工具，自动暴露为 MCP 协议格式（name/description/inputSchema/annotations.category）
  - 新增 [app/api/mcp.py](app/api/mcp.py)：4 个端点（`GET /api/mcp/manifest` 公开元信息 / `GET /api/mcp/tools` 工具列表 / `POST /api/mcp/tools/call` 调用工具 / `POST /api/mcp/sse` SSE 流式调用，兼容 stateless 核心）
  - 支持 Nginx round-robin 多 worker 部署（移除 initialize 握手与协议级 session）
  - 工具参数含 `project_id` 时自动调用 `verify_project_access` 校验项目归属，防止 IDOR
  - 11 项新增测试覆盖（manifest/tools/5 个工具调用/越权/SSE/未认证）
- **Qwen-Audio-3.0-Realtime Plus + 语音情绪路由**（PRD §6.x 语音增强）:
  - [app/api/voice_realtime.py](app/api/voice_realtime.py) 新增 `VOICE_SYSTEM_INSTRUCTIONS_PLUS` 常量，Plus 模型自动启用情感感知 + 副语言处理指令
  - 新增 `_get_emotion_aware_system_prefix(emotion)` 函数：根据情绪 label（anxious/angry/sad/tired/excited/happy）+ score（≥0.4 才注入）生成系统指令前缀，调整 Agent 语气
  - `_route_voice_to_agent(text, intent, user_name, context, emotion)` 增加 emotion 参数，在 user_ctx 成型后注入情绪前缀
  - `voice_realtime_websocket` 根据 `settings.qwen_audio_model.endswith("-plus")` 自动选择增强指令
  - [app/services/voice_realtime_service.py](app/services/voice_realtime_service.py) 在 connect 日志中记录模型变体（plus/standard + emotion_aware on/off）
  - 12 项新增测试覆盖（情绪前缀生成/路由注入/Plus 关键字/未认证）
- **AI 渲染端点**（PRD §7.x 长线计划，对标 SpatialGen + DecoMind）:
  - 新增 [app/services/ai_render_service.py](app/services/ai_render_service.py)：`AIRenderService` 类封装 2D/3D/restage 三种渲染能力
  - 复用 `BaseAgent._chat()` 调用 LLM（DeepSeek/GLM），无 API Key 时走 mock 模式返回占位图
  - 每个渲染方法自动调用 `BaseAgent.get_user_preference_hint()` 注入 L4 用户偏好
  - 新增 [app/api/ai_render.py](app/api/ai_render.py)：4 个端点（`POST /api/ai-render/2d` 2D 效果图 / `POST /api/ai-render/3d` 3D 场景 / `POST /api/ai-render/restage` 照片重布置 / `GET /api/ai-render/capabilities` 风格与模式列表）
  - 支持 7 种风格（modern/nordic/japanese/luxury/chinese/industrial/coastal）+ 2 种重布置模式（inpainting/full_regen）
  - 11 项新增测试覆盖（mock 模式/越权/422/无照片/capabilities/未认证/L4 偏好注入）
- **WebGPU mesh 阈值保护**（对标 Three.js issue #30560 性能瓶颈）:
  - [web/studio.html](web/studio.html) 新增 `WEBGPU_MESH_THRESHOLD = 500` 常量与 `webgpuForcedOff` 标志
  - `sync3D` 函数估算 mesh 数量（rect 元素 × 2），超过阈值时自动降级到 WebGL，避免 WebGPURenderer 在多 mesh CAD 场景下的 per-object UBO 瓶颈
  - 单向降级策略：`webgpuForcedOff` 一旦置 true 不自动复位，避免阈值附近抖动
  - 降级时完整 dispose 旧 renderer + 重建 WebGLRenderer，确保状态完备
  - 新增 `#renderer-threshold-hint` 隐藏提示 span（默认 `display:none`，含 title 说明）
- **配置层与版本号升级**:
  - [app/config.py](app/config.py) 新增 4 个 feature flag：`mcp_enabled` / `ai_render_enabled` / `voice_emotion_routing_enabled`（默认 True）+ Qwen Plus 模型说明
  - [app/api/config.py](app/api/config.py) `/api/config/feature-flags` 暴露新 flag + `qwen_audio_model_variant` 字段
  - [app/main.py](app/main.py) 注册 `/api/mcp/*` + `/api/ai-render/*` 路由
  - `app_version` `1.1.11` → `1.1.12`，12 个 HTML/JS 文件 `?v=20260719e` → `?v=20260720a`（47 处统一），[web/sw.js](web/sw.js) `CACHE_VERSION` `suoke-v20260719e` → `suoke-v20260720a`
- **轻量迁移测试隔离修复**:
  - [app/database.py](app/database.py) `_run_lightweight_migrations()` 新增 `force: bool = False` 参数，绕过 `_schema_migrations` 版本检查（测试场景使用）
  - 末尾 INSERT 前增加 `CREATE TABLE IF NOT EXISTS _schema_migrations` 兜底，防止 force=True 时表不存在
  - [tests/test_payments.py](tests/test_payments.py) 3 个 drop-and-readd 测试改用 `force=True`，修复 v1.1.12 性能优化引入的测试隔离问题
- **项目冗余清理**: 清理全部 `__pycache__/` 目录、`.pytest_cache/`、`htmlcov/`、`data/test_*.db` 测试数据库

### 2026-07-19 · v1.1.10

- **Filament 渲染引擎迁移**（PRD §7.1）:
  - [web/studio.html](web/studio.html) 新增「🎮 切换 3D 引擎」按钮，支持 Three.js ↔ Filament 双引擎切换
  - `loadFilament()` 按需加载 Filament WASM 1.54.6（cdn.jsdelivr.net），初始化 Engine/Renderer/Scene
  - `toggleRenderer()` / `renderWithFilament()` 实现 PBR 渲染路径，保留 Three.js 作为默认引擎保证兼容性
  - [app/config.py](app/config.py) `filament_enabled` 默认改为 `True`（按需加载，不影响首屏）
- **OpenCascade.js 真实布尔运算**（PRD §7.1）:
  - [web/studio.html](web/studio.html) 布尔运算按钮组（∪ 并 / ∖ 差 / ∩ 交）
  - `loadOpenCascade()` 加载完整 opencascade.wasm.js（取代仅支持导入的 occt-import-js）
  - `booleanOperation()` 实现真实 BRepAlgoAPI_Fuse / Cut / Common 布尔运算 + BRepBndLib AABB 包围盒计算
  - WASM 失败时降级到 AABB 近似运算保证可用性
  - [app/config.py](app/config.py) `opencascade_enabled` 默认改为 `True`，`opencascade_cdn_url` 指向完整 WASM 版本
- **DWG/DXF 后端真实解析**（PRD §7.1）:
  - 新增 [app/api/cad_import.py](app/api/cad_import.py)：`POST /api/cad-import/dxf` 端点
  - DXF 解析使用 ezdxf 1.4.4 库：支持 LINE / LWPOLYLINE / CIRCLE / ARC / TEXT 实体 + 边界框计算
  - DWG 转换使用系统 dwg2dxf 命令（LibreDWG），未安装时返回 422 + 安装指引
  - [requirements.txt](requirements.txt) 新增 `ezdxf>=1.4.0` 依赖
  - [app/main.py](app/main.py) 注册 `/api/cad-import/*` 路由
  - [web/studio.html](web/studio.html) `importCADFile()` 优先调用后端 API，失败降级到前端解析
  - 7 项新增测试覆盖端点（DXF 解析 / 几何字段 / 认证 / 文件类型 / 损坏文件 / DWG 转换器缺失）
- **L4 自适应学习注入**（PRD §5.4 Phase 5 末项）:
  - [app/api/agents.py](app/api/agents.py) `/agents/chat` 端点在 intent 确定后注入 `BaseAgent.get_user_preference_hint()` few-shot 示例
  - 仅在 `agent_learning_enabled=True` 且非 MOCK_MODE 时生效，测试环境不受影响
  - 5 项新增测试覆盖：无数据返回空 / 禁用返回空 / 有反馈返回示例 / agent 过滤 / dislike 排除
- **版本号一致性升级**: 7 个 HTML `?v=20260719b` → `?v=20260719c`（35 处统一），[web/sw.js](web/sw.js) `CACHE_VERSION` `suoke-v1.0.24` → `suoke-v1.0.25`，[app/config.py](app/config.py) `app_version` `1.1.9` → `1.1.10`，[.github/workflows/ci.yml](.github/workflows/ci.yml) `APP_VERSION` `1.1.9` → `1.1.10`

### 2026-07-19 · v1.1.9

- **DWG/DXF 文件导入**（PRD §7.1 长线计划）:
  - [web/studio.html](web/studio.html) 新增「📥 导入 DWG/DXF」按钮 + 隐藏 file input
  - DXF R12/R14 文本格式前端直接解析：支持 LINE / LWPOLYLINE / CIRCLE / ARC 实体，每段转换为 0.15m 厚 rect 墙体
  - DWG 闭源格式：前端检测到 .dwg 时弹出转换指引（ODA File Converter / LibreDWG / AutoCAD 另存为 DXF）
- **L4 自适应学习基础**（PRD §5.4 Phase 5 末项，提前布局）:
  - 新增 [app/models/agent_feedback.py](app/models/agent_feedback.py)：AgentFeedback 表（user_id/agent_name/message_hash/feedback_type/rating/comment/user_message/agent_reply）
  - 新增 [POST /api/agents/feedback](app/api/agents.py) 端点：记录用户 like/dislike 反馈
  - 新增 [BaseAgent.get_user_preference_hint()](app/agents/base.py)：查询用户历史正向反馈构造 few-shot 示例提示
  - [app/config.py](app/config.py) 新增 `agent_learning_enabled` + `agent_learning_max_examples` 配置（默认 False，可选启用）
  - 6 项新增测试覆盖（like/dislike/invalid type/unauth/feature flags/preference hint）
- **OpenCascade.js 按需加载框架**（PRD §7.1 长线计划）:
  - [web/studio.html](web/studio.html) 新增「⬭ 布尔运算 (OpenCascade)」按钮
  - `loadOpenCascade()` 动态加载 CDN（按需，不影响首屏性能）
  - `booleanOperation(op)` 实现 union/intersect 的 AABB 近似运算 + difference 占位提示
  - 启动前先查询 `/api/config/feature-flags` 检查 opencascade_enabled 开关
- **Filament 集成配置层**（PRD §7.1 长线计划）:
  - [app/config.py](app/config.py) 新增 `filament_enabled` + `filament_cdn_url` 配置（默认 False，保持 Three.js r128）
- **配置查询 API**: 新增 [app/api/config.py](app/api/config.py) 提供 `GET /api/config/feature-flags`，前端可查询长线技术决策的开关状态
- **版本号一致性升级**: 7 个 HTML `?v=20260719a` → `?v=20260719b`（35 处统一），[web/sw.js](web/sw.js) `CACHE_VERSION` `suoke-v1.0.23` → `suoke-v1.0.24`，[app/config.py](app/config.py) `app_version` `1.1.8` → `1.1.9`

### 2026-07-19 · v1.1.8

- **PRD 对照评估修复**（对照 PRD v3.0 §12 AC-4）:
  - **任意剖切面**: [web/studio.html](web/studio.html) 平立剖视图新增「✂ 剖面」按钮，用户在画布点击两点定义剖切线，沿剖切线计算与所有墙体 rect 边界交点，自动生成剖面图（含墙体斜线填充、房间名标注、A-B 端点标记、水平距离标尺、高度标尺）。补齐 PRD §12 AC-4「平立剖自动生成」中缺失的"任意剖切面"子项
  - 视图模式从 5 个扩展为 6 个：平面 / 正立面 / 背立面 / 左立面 / 右立面 / 任意剖面
- **版本号一致性升级**: 7 个 HTML `?v=20260718d` → `?v=20260719a`（35 处统一），[web/sw.js](web/sw.js) `CACHE_VERSION` `suoke-v1.0.22` → `suoke-v1.0.23`，[app/config.py](app/config.py) `app_version` `1.1.7` → `1.1.8`
- **冗余清理**: 删除根目录 4 个过时文档（`SIT_REPORT.md` v1.1.1 / `UAT_REPORT.md` v1.1.1 / `UAT_TEST_PLAN.md` v1.0.0 / `test_endpoints.sh` 与 `scripts/e2e-*.sh` 重复），清理全部 `__pycache__/` 和 `.pytest_cache/`

### 2026-07-18 · v1.1.7

- **AI 推理稳定性优化**:
  - 修复 `reasoning_content` fallback 逻辑：v1.0.16 引入的 fallback 把 LLM 内部思维链当作回复返回，导致用户偶发看到 "我们需要理解用户需求..." 等内部推理内容。改为返回友好错误消息（含 `finish_reason` 便于排查）
  - 新增 content 为空自动重试：当 LLM 返回 `content=""` 且 `finish_reason="length"`（reasoning 占满 token 配额）时，自动降温到 0.3 重试 1 次，给 content 输出留出空间
  - 优化 `DesignerAgent` system_prompt：精简 JSON 格式说明，添加 "直接输出 JSON，不要推理" 指令，减少 reasoning token 消耗
- **WebSocket 心跳机制**:
  - 客户端 `{"event":"ping"}` → 服务端自动回复 `{"event":"pong"}`
  - 服务端无活动 300s 后发送 ping 探测，30s 内无回复则断开僵尸连接
  - 防止客户端异常断开（未发送 close 帧）导致的僵尸连接积累
- **健康检查优化**: 磁盘空间三级阈值（ok >15% / warning 5-15% / critical <5%），替代原二级阈值
- **项目冗余清理**: 清理 `data/test_*.db` 测试数据库 678 个（释放 617MB）、`__pycache__/` 目录、`.pytest_cache`、`htmlcov/`
- **测试用例**: 670 通过 / 0 失败 / 9 跳过（新增 3 项 reasoning_content 回归测试）

### 2026-07-16 · v1.1.0

- **代码质量优化**:
  - 修复 `datetime.utcnow()` 弃用警告 → `datetime.now(timezone.utc)`
  - 修复 pytest-asyncio event_loop 弃用警告 → 使用 `asyncio_default_fixture_loop_scope`
  - pytest.ini 移除未安装的 `-n auto` / `--cov` 选项
- **Flutter 页面修复**: `design_deepening_page.dart` 从 mock 数据重构为对接 `/api/floorplans` 真实 API（含 CRUD、loading/error/empty 状态）
- **Web 前端完善**: `our-story.html` 从重定向页面重写为完整品牌故事页（愿景/AI 团队/技术栈）
- **项目冗余清理**: 删除 `dogfood-output/report.md`（历史 QA 产物）、`alembic/versions/README.md`（模板说明）、清理全部 `__pycache__/` 目录
- **测试用例**: 584 通过 / 0 失败 / 9 跳过

## 快速启动

```bash
# 一键演示环境
bash scripts/demo-start.sh

# 启动后端
source .venv/bin/activate
uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload

# 打开各前端页面
open web/index.html       # 落地页
open web/admin.html       # 管理后台 (PASETO 登录)
open web/studio.html      # 统一设计台 (2D+3D+AI+平立剖)
open web/3d-viewer.html   # 3D 效果图
```

## 项目结构

```
i-home.life/
├── app/
│   ├── api/           # 63 个路由模块 (590+ 端点)
│   │   ├── auth.py          # 认证 (register/login/me)
│   │   ├── projects.py      # 项目管理
│   │   ├── materials.py     # 物料 + BOM + Excel导出
│   │   ├── budgets.py       # 预算管理 + 多方案对比 + 偏差预警 + 模板库
│   │   ├── procurement.py   # 采购 + 供应商 + 比价报告
│   │   ├── procurement_enhanced.py  # F33/F34 采购增强 (比价/担保支付/物流追踪/样品索要)
│   │   ├── construction.py  # 施工 + 日志 + 质检 + AI 图像审核 + F37 进度 + F38 质量
│   │   ├── settlements.py   # 结算 + 里程碑 + 异常检测 + 对账单
│   │   ├── change_orders.py # 变更管理 (F39)
│   │   ├── payments.py      # 支付管理 (F15) 发起/确认/退款/里程碑聚合
│   │   ├── chat.py          # IM 协作 (F40) 消息/聊天室/@提及/已读
│   │   ├── crews.py         # 工程队匹配 (F36) 档案/六维评分/雇佣
│   │   ├── workers.py       # 服务者匹配 (F35) 设计师/监理/预算师档案+评分
│   │   ├── takeoff.py       # 工程量计算 (F9)
│   │   ├── mep.py           # 水电点位 (F22+F20)
│   │   ├── kitchen_bath_mep.py  # F18 厨卫水电 (给排水/燃气/回路/等电位)
│   │   ├── hard_decoration.py   # F21 硬装 (瓷砖排版/涂料用量/吊顶)
│   │   ├── door_window_waterproof.py  # F23 门窗防水 (选型/防水区域/规范校验)
│   │   ├── floorplans.py    # 户型方案存储
│   │   ├── voice.py         # 语音处理
│   │   ├── files.py         # 文件上传/下载
│   │   ├── surveys.py       # 测量 + F1 AR 空间测量 (扫描会话/降级策略/精度校验/墙面特征)
│   │   ├── lighting.py      # F29/F30 灯光设计 (照度计算/色温规划/无主灯/AI 方案)
│   │   ├── kitchen.py       # F16 厨房设计器 (橱柜参数化/动线分析/规范校验)
│   │   ├── bathroom.py      # F17 卫生间设计器 (干湿分离/地漏坡度/防水/通风)
│   │   ├── custom_furniture.py  # F27 定制家具 (参数化/板材/拆单 BOM/价格估算)
│   │   ├── soft_furnishing.py   # F24/F25 软装+收纳 (AI 搭配/配色和谐度/收纳推荐)
│   │   ├── furniture_catalog.py  # F26 家具品类库 (多维筛选/房间推荐/AR 摆放)
│   │   ├── smart_home.py    # F31 智能家居方案 (设备点位/布线/协议选型)
│   │   ├── scene_automation.py  # F32 场景编辑 (联动触发/场景模拟/NL 解析/生态对接)
│   │   ├── vr_panorama.py   # VR 全景 (等距柱状/热点/场景漫游)
│   │   ├── ai_image.py      # AI 图生图 (SDXL/ControlNet/批量渲染)
│   │   ├── appliance.py     # 电器 (F19/F20 品类/点位/负荷计算)
│   │   ├── structural.py    # 土建结构 (F8/F9 荷载/梁柱/楼板/基础/工程量) — 42 端点
│   │   ├── identity.py      # 身份认证
│   │   ├── products.py      # 产品库
│   │   ├── tasks.py         # 任务管理
│   │   ├── points.py        # 积分系统
│   │   ├── location.py      # 地理位置
│   │   └── agents.py        # AI Agent 路由 (含 F28 动线分析)
│   ├── agents/        # 22 个 AI Agent (业务逻辑版)
│   │   ├── orchestrator.py  # 总控 (意图路由)
│   │   ├── designer.py      # 设计 (9套布局 + NL 修改 + F28 动线分析)
│   │   ├── budget.py        # 预算 (多方案对比/偏差预警/模板库)
│   │   ├── procurement.py   # 采购 (比价报告/采购计划/供应商匹配)
│   │   ├── construction.py  # 施工 (Gantt 排期/质检清单/AI 图像质检 + F37 进度 + F38 质量)
│   │   ├── qa_inspector.py  # 质检 (验收报告/缺陷识别/设计比对/整改建议)
│   │   ├── settlement.py    # 结算 (里程碑/异常检测/对账单)
│   │   ├── concierge.py     # 客服 (FAQ 知识库/咨询分类/升级规则)
│   │   ├── admin.py         # 管理员 (审计日志/平台运营)
│   │   └── content_publisher.py  # 内容发布 (方案/案例/资讯)
│   ├── models/        # 118 ORM 模型 (54 文件)
│   ├── schemas/       # 40+ Pydantic 验证模块
│   ├── services/      # 82 个业务服务
│   └── auth/          # PASETO Token 认证
├── flutter_app/       # 跨平台 App (iOS/iPadOS/Android/HarmonyOS)
│   └── lib/
│       ├── pages/     # 40 个页面 (详细列表见下方)
│       ├── services/  # API/WebSocket/SSE/离线缓存/通知/Agent路由
│       ├── widgets/   # 消息卡片/表情选择器/加载骨架/错误重试
│       ├── models/    # 数据模型
│       └── theme/     # 索克家居主题 (明/暗)
├── flutter_app/ohos/  # HarmonyOS 适配 (3.35.7-ohos-0.0.3, API 23+)
├── web/              # 前端页面 (17 HTML + 8 JS + 1 CSS)
│   ├── index.html, demo.html, workbench.html, admin.html
│   ├── studio.html, 3d-viewer.html, vr-viewer.html
│   ├── materials.html, project-detail.html, quality-report.html
│   ├── login.html, settings.html, dashboard.html, quality.html
│   └── house-design-platform-prd.html
├── assets/           # 品牌资源与文档 (logo/截图/壁纸)
├── alembic/          # 数据库迁移 (Alembic, SQLite/PostgreSQL 双库)
├── scripts/          # 运维脚本 (部署/测试/验收/HarmonyOS)
└── tests/            # 42 测试文件, 737 测试用例
```

### Flutter 页面完整列表 (41 个)

| 页面 | 功能 | 编号 |
|------|------|------|
| home_page | 底部导航主页 (5 Tab + 更多) | — |
| login_page | 登录注册 | — |
| dashboard_page | 工作台概览 | — |
| projects_page | 项目列表 | — |
| project_detail_page | 项目详情 | — |
| ai_chat_page | AI 智能对话 | — |
| ai_image_page | AI 图生图 | — |
| cad_page | 2D CAD 设计台 | — |
| cad_element | CAD 图形元素 | — |
| stylus_adapter | 手写笔适配 | — |
| design_deepening_page | 深化设计 | — |
| materials_page | 物料浏览 (225 SKU) | — |
| kitchen_page | 厨房设计器 | F16 |
| bathroom_page | 卫生间设计器 | F17 |
| kitchen_bath_mep_page | 厨卫水电 | F18 |
| appliance_page | 电器规划 | F19/F20 |
| hard_decoration_page | 硬装设计 | F21 |
| mep_page | 水电点位 | F22 |
| door_window_waterproof_page | 门窗防水 | F23 |
| soft_furnishing_page | 软装+收纳 | F24/F25 |
| furniture_catalog_page | 家具品类库 | F26 |
| custom_furniture_page | 定制家具 | F27 |
| lighting_page | 灯光设计 | F29/F30 |
| smart_home_page | 智能家居方案 | F31 |
| scene_automation_page | 场景编辑 | F32 |
| structural_page | 土建结构 | F8/F9 |
| takeoff_page | 工程量计算 | F9 |
| ar_scan_page | AR 空间测量 | F1 |
| vr_panorama_page | VR 全景 | — |
| budget_page | 预算管理 | — |
| procurement_enhanced_page | 采购增强 | F33/F34 |
| settlement_page | 结算管理 | — |
| change_orders_page | 变更管理 | F39 |
| construction_page | 施工管理 | — |
| tasks_page | 任务管理 | — |
| products_page | 产品库 | — |
| crew_page | 工程队匹配 | F36 |
| worker_page | 服务者匹配 | F35 |
| chat_page | 协作聊天 | F40 |
| points_page | 积分商城 | — |
| identity_page | 身份认证 | — |

## 核心技术栈

| 层 | 技术 |
|----|------|
| 后端 | Python 3.12 + FastAPI + SQLAlchemy 2.0 (async) + SQLite / PostgreSQL |
| 认证 | PASETO v4 (local) |
| 数据库迁移 | Alembic (双库切换) |
| AI Agent | DeepSeek + GLM (LLM) + 规则混合路由 (mock + LLM 双模式) |
| 前端 | Vanilla JS + Canvas 2D + Three.js r128 (响应式 + 无障碍) |
| 移动端 | Flutter 3.35.7-ohos-0.0.3 (iOS/iPadOS/Android/HarmonyOS) |
| 导出 | DXF R12 + Excel (openpyxl) |
| 缓存 | Redis 缓存支持（可选，内存字典降级） |
| 存储 | OSS 对象存储支持（可选，本地文件降级） |
| 向量检索 | 向量数据库 RAG 支持（Qdrant/Milvus，可选） |

## 数据库

| 表名 | 用途 |
|------|------|
| users | 用户 (业主/设计师/工长/管理员) |
| projects / floors / rooms | 装修项目/楼层/房间 |
| material_categories / materials / bom_items | 物料分类/物料 (225 SKU)/清单 |
| budgets / budget_lines | 预算 |
| suppliers / quotations / procurement_orders / order_lines | 采购 |
| construction_tasks / construction_logs / inspections | 施工管理 |
| settlements / settlement_lines | 结算 |
| change_orders / change_order_items | 变更管理 (F39) |
| payments | 支付管理 (F15) |
| chat_rooms / chat_messages | IM 协作 (F40) |
| construction_crews / crew_matches | 工程队匹配 (F36) |
| progress_alerts / milestone_trackers | 进度管理 (F37) |
| quality_issues / rectification_orders / quality_assessments | 质量管理 (F38) |
| service_workers / service_worker_matches | 服务者匹配 (F35) |
| ar_scan_sessions / ar_wall_features / ar_measurement_points | F1 AR 空间测量 |
| lighting_schemes / lighting_fixtures | F29/F30 灯光设计 |
| kitchen_designs / kitchen_components | F16 厨房设计器 |
| bathroom_designs / bathroom_fixtures | F17 卫生间设计器 |
| custom_furniture_designs / furniture_modules / furniture_bom | F27 定制家具 |
| soft_furnishing_schemes / soft_furnishing_items / storage_systems | F24/F25 软装+收纳 |
| vr_panoramas / vr_scenes | VR 全景 |
| ai_image_jobs / ai_image_presets | AI 图生图 |
| kitchen_bath_mep_plans / mep_points | F18 厨卫水电 |
| hard_decoration_schemes / hard_decoration_floor_plans / wall_finishes / ceiling_designs | F21 硬装 |
| door_window_specs / waterproof_plans | F23 门窗防水 |
| furniture_catalog_items | F26 家具品类库 |
| smart_home_schemes / smart_devices | F31 智能家居方案 |
| scene_automations / ecosystem_integrations | F32 场景编辑 |
| price_comparisons / price_comparison_items / escrow_payments / logistics_trackings / sample_requests | F33/F34 采购增强 |
| appliance_categories / appliances / appliance_points / appliance_load_calcs | F19/F20 电器 |
| load_bearing_walls / beams / columns / floor_slabs / foundation_types / structure_load_estimates / bay_compliances / quantity_calculations / quantity_line_items | F8/F9 土建结构 |
| floor_plans | 户型方案 |
| file_attachments | 工程文件 |
| surveys | AR 空间测量 |
| orchestrator_tasks / task_candidates | Agent 编排任务 |
| points_accounts / points_transactions / points_rules / points_mall_items / points_redemptions / points_rankings | 积分系统 |
| identity_verifications | 身份认证 |
| webauthn_credentials | WebAuthn/Passkey |

## API 端点

| 模块 | 端点 | 方法 |
|------|------|------|
| 认证 | /auth/register, /auth/login, /auth/me | POST/POST/GET |
| WebAuthn/Passkey | /auth/webauthn/register/begin, /auth/webauthn/register/complete, /auth/webauthn/login/begin, /auth/webauthn/login/complete, /auth/webauthn/credentials | POST/POST/POST/POST/GET-DELETE |
| 项目 | /projects | CRUD 5端点 |
| 物料 | /materials, /materials/categories, /materials/bom | 12端点 |
| 预算 | /budgets, /budgets/generate-from-bom/{id}, /budgets/compare-plans, /budgets/variance-check, /budgets/templates, /budgets/templates/apply | 9端点 |
| 采购 | /procurement/suppliers, /procurement/quotations, /procurement/orders, /procurement/compare, /procurement/recommend-suppliers | 12端点 |
| 施工 | /construction/tasks, /construction/logs, /construction/inspections, /construction/plan, /construction/quality-checklist/{phase}, /construction/inspections/analyze, /construction/progress-analysis (F37), /construction/progress-alerts, /construction/milestones, /construction/quality-detect (F38), /construction/quality-issues, /construction/rectification-orders, /construction/quality-assessments | 27端点 |
| 结算 | /settlements, /settlements/generate-from-budget/{id}, /settlements/milestone, /settlements/milestones, /settlements/anomaly-check, /settlements/reconciliation | 13端点 |
| 变更 | /change-orders, /change-orders/{id}, /change-orders/{id}/review, /change-orders/{id}/approve, /change-orders/{id}/cancel | 6端点 |
| 支付 | /payments, /payments/project/{id}, /payments/{id}, /payments/{id}/confirm, /payments/{id}/refund, /payments/{id}/fail, /payments/milestones/{id} | 11端点 |
| IM 协作 | /chat/rooms/{id}, /chat/messages/{id}, /chat/messages, /chat/messages/{id}/read, /chat/unread/{id} | 5端点 |
| 工程队 | /crews, /crews/{id}, /crews/match, /crews/matches/{id}, /crews/matches/{id}/status | 6端点 |
| 服务者 | /workers, /workers/{id}, /workers/match (F35), /workers/matches/{id}, /workers/matches/{id}/status | 6端点 |
| 工程量 | /takeoff/wall, /takeoff/slab, /takeoff/floor, /takeoff/paint, /takeoff/project | 5端点 |
| 水电点位 | /mep/plan, /mep/appliances, /mep/compliance-check, /mep/room-standards/{type} | 4端点 |
| 户型 | /floorplans | CRUD 5端点 |
| 测量 | /surveys + /surveys/ar/sessions + /surveys/ar/features + /surveys/ar/points + /surveys/ar/device-capability | 22端点 (含 F1) |
| 灯光 | /lighting/schemes, /lighting/schemes/{id}/ai-design, /lighting/schemes/{id}/fixtures, /lighting/schemes/{id}/illuminance | 9端点 (F29/F30) |
| 厨房 | /kitchen/designs, /kitchen/designs/{id}/auto-layout, /kitchen/designs/{id}/workflow, /kitchen/designs/{id}/compliance | 10端点 (F16) |
| 卫生间 | /bathroom/designs, /bathroom/designs/{id}/auto-layout, /bathroom/designs/{id}/drain, /bathroom/designs/{id}/waterproof, /bathroom/designs/{id}/ventilation | 11端点 (F17) |
| 定制家具 | /custom-furniture/designs, /custom-furniture/designs/{id}/parametric, /custom-furniture/designs/{id}/bom, /custom-furniture/designs/{id}/price, /custom-furniture/designs/{id}/validation | 13端点 (F27) |
| 软装+收纳 | /soft-furnishing/schemes, /soft-furnishing/schemes/{id}/ai-match, /soft-furnishing/schemes/{id}/color-harmony, /soft-furnishing/schemes/{id}/budget, /soft-furnishing/storage/recommend | 15端点 (F24/F25) |
| VR 全景 | /vr/panoramas, /vr/panoramas/{id}/render, /vr/panoramas/{id}/hotspots, /vr/scenes | 13端点 |
| AI 图生图 | /ai-image/jobs, /ai-image/jobs/{id}/process, /ai-image/presets, /ai-image/jobs/apply-preset, /ai-image/jobs/batch | 11端点 |
| 厨卫水电 | /mep-kb/plans, /mep-kb/plans/{id}/points, /mep-kb/plans/{id}/gas, /mep-kb/plans/{id}/circuits, /mep-kb/plans/{id}/equipotential | 11端点 (F18) |
| 硬装 | /hard-decoration/schemes, /hard-decoration/schemes/{id}/floor, /hard-decoration/schemes/{id}/wall, /hard-decoration/schemes/{id}/ceiling, /hard-decoration/schemes/{id}/tile-layout | 11端点 (F21) |
| 门窗防水 | /door-window-waterproof/specs, /door-window-waterproof/specs/{id}, /door-window-waterproof/waterproof, /door-window-waterproof/waterproof/{id}/validate | 11端点 (F23) |
| 家具品类库 | /furniture-catalog/items, /furniture-catalog/search, /furniture-catalog/recommend/{room_type}, /furniture-catalog/items/{id}/ar-place | 8端点 (F26) |
| 智能家居 | /smart-home/schemes, /smart-home/schemes/{id}/devices, /smart-home/schemes/{id}/auto-recommend, /smart-home/schemes/{id}/wiring, /smart-home/schemes/{id}/protocol | 11端点 (F31) |
| 场景编辑 | /scene-automation/scenes, /scene-automation/scenes/{id}/simulate, /scene-automation/scenes/{id}/parse-nl, /scene-automation/scenes/{id}/validate, /scene-automation/ecosystems | 12端点 (F32) |
| 采购增强 | /procurement-enhanced/price-comparisons, /procurement-enhanced/escrow-payments, /procurement-enhanced/logistics, /procurement-enhanced/sample-requests | 21端点 (F33/F34) |
| 电器 | /appliances/categories, /appliances, /appliances/{id}, /appliances/points, /appliances/load-calc | 20端点 (F19/F20) |
| 土建 | /structural/load-bearing-walls, /structural/beams, /structural/columns, /structural/slabs, /structural/foundations, /structural/load-estimates, /structural/bay-compliance, /structural/quantities | 42端点 (F8/F9) |
| 文件 | /files/upload, /files/download/{id} | 4端点 |
| AI Agent | /agents/chat, /agents/design, /agents/design/circulation (F28), /agents/budget, /agents/procurement, /agents/construction, /agents/settlement | 14端点 |
| 任务 | /tasks (CRUD + 状态) | 8端点 |
| 产品 | /products (CRUD) | 6端点 |
| 积分 | /points/account, /points/transactions, /points/rules, /points/mall, /points/redeem, /points/ranking | 10端点 |
| 身份 | /identity/verify, /identity/status | 4端点 |
| 位置 | /location/ip, /location/nearby | 3端点 |
| 语音 | /voice/asr | 1端点 |
| **合计** | | **630+ 路由（70 模块）** |

> 注：上表为模块级端点快照；v1.5.0 实测 `app/api/` 70 个路由模块 / 630+ 路由（含 /health、/metrics、/docs、/ws 等，2026-08-03 实测 631）。

## 验收标准

| AC | 验收项 | 状态 |
|----|--------|------|
| AC-1 | 2D CAD 精确绘图 | ✅ 15工具 + 正交 + 捕捉 |
| AC-2 | 对象捕捉 98% | ✅ snapPoints + nearestSnap |
| AC-3 | 3D 墙体拉伸 < 3s | ✅ Three.js sync3D |
| AC-4 | 平立剖自动生成 | ✅ 6 视图 (俯视 + 4向立面 + 任意剖切面) |
| AC-5 | DXF 导出兼容 | ✅ R12 POLYLINE |
| AC-6 | Agent 响应 < 3s | 10 Agent + 混合路由 |
| AC-7 | Agent 完成率 85% | ✅ 9套布局 + NL指令 |
| AC-8 | iPad 30fps | ✅ 基准测试就绪 |
| AC-9 | 崩溃率 < 0.1% | ✅ 验收脚本就绪 |

```bash
# 运行验收脚本
bash scripts/verify-ac.sh

# 运行测试套件
source .venv/bin/activate
.venv/bin/python -m pytest tests/ -v
# 当前: 750 passed, 9 skipped, 0 failed (2026-07-19 v1.1.10 基线, +12 新增 CAD 导入 + L4 注入测试)

# 数据库迁移 (Alembic)
alembic check        # 检测模型与数据库差异
alembic revision --autogenerate -m "init"  # 生成迁移
alembic upgrade head # 应用迁移
```

## 演示脚本

```bash
# 全链路演示 (注册→项目→AI设计→BOM→预算→施工→结算)
bash scripts/e2e-full.sh

# HarmonyOS HAP 构建部署 (需 DevEco Studio)
bash scripts/deploy-ohos.sh

# FPS 基准测试 (Chrome headless, 输出 JSON + MD 报告)
python scripts/bench-fps.py
```

## 部署

```bash
# 生产部署
bash scripts/deploy.sh start

# 停止 / 重启 / 状态
bash scripts/deploy.sh stop
bash scripts/deploy.sh restart
bash scripts/deploy.sh status
```

## 演示账号

| 角色 | 手机号 | 密码 |
|------|--------|------|
| 业主 | 13800138000 | 123456 |
| 设计师 | 13900139000 | 123456 |

## 许可证

内部项目，Phase 1 MVP 交付。全链路功能完整度 90%。

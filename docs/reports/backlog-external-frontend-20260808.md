# 待办事项清单 — 外部依赖接入 + 前端缺口页（2026-08-08）

> 来源：2026-08-08 全景全链路评估报告。本清单为**外部依赖型 / 大工程量**项，
> 无法在纯代码层面闭环，需配置外部凭据或另行排期。已完成项见 CHANGELOG「全景评估修复（2026-08-08）」。
> **2026-08-09 更新**：B1（Agent 治理 8 页）+ C（单端独缺 7 页）已全部补齐并验证
> （console 63 页 / Flutter 55 页），详见 CHANGELOG「前端缺口补齐（2026-08-09）」。
> **2026-08-11 更新**：A2 灰度评估已执行——33 个默认 False flag 分四类评估，
> **A 类 16 个「无外部依赖可安全开启」已全部默认开启（v1.13.2）**，详见
> CHANGELOG「A2 灰度 flag 第一/二/三/四梯队 + D 类」。本节 A2 表仅剩需外部凭据项。
> **2026-08-13 更新**：B2（物联监测 3 页 console：HealthMonitor/施工图/Sensors，Energy 既有）+
> B3（管理后台 3 页 console：Admin/Notifications/Files，Payments 既有）+
> B4（供应链边缘 4 页 Flutter：CameraScan/ProductBatch/Location/VoiceRealtime）已全部补齐并验证，
> 详见 CHANGELOG「前端缺口补齐 B2/B3/B4」。B2 中 analytics 为「仅接收不持久化」公共端点，
> 无管理页价值，诚实标注跳过。

## A. 外部依赖接入（需第三方 API key / SDK，接入后删除诚实标注）

### A1. 生态桥接 `app/services/ecosystem_bridge.py`（最高优先，评估报告点名的唯二 stub）

当前状态：抽象基类 `EcosystemBridge` 已定义统一接口，各桥接约 25 处
`raise NotImplementedError("TODO: need API key")`；MijiaBridge 已有真实小米云登录。

| 桥接 | 需要的凭据/能力 | 文件位置 | 当前状态 |
|---|---|---|---|
| HomeKitBridge | HomeKit HAP pairing_code / setup_payload | ecosystem_bridge.py L119 | 纯 stub |
| HarmonyOSBridge | app_id / app_secret / device_id | ecosystem_bridge.py L284 | 纯 stub |
| MatterBridge | Matter passcode / discriminator | ecosystem_bridge.py L336 | 纯 stub |
| TuyaBridge | access_id / access_secret / endpoint | ecosystem_bridge.py L483 | 纯 stub |
| MijiaBridge | python-miio 签名请求（设备列表/控制） | ecosystem_bridge.py L173 | 登录真实，get_devices/send_command 等 stub |

接入流程建议：逐个桥接落地 → `connect` 真实鉴权 → `get_devices`/`send_command`
真实设备控制 → 打通 `scene_automation_service.check_sensor_triggers` 的
`action_status="pending"` → 改为真实执行。接入后更新 ecosystem_integrations 表 auth_status。

### A2. 外部依赖型能力（需配置后启用；无外部依赖项已于 v1.13.2 全部开启）

**已开启（v1.13.2，A2 灰度评估 A 类 16 个 + D 类 1 个）**：
商业运营 5（growth/marketing/competitor_research/finance_recon/business_ops_orchestrator）/
以销定产 / 自进化三层（case_extraction/skill_distillation/skill_evolution）/
治理类（ai_content_labeling/gbz185/protocol_compliance/memory_conflict_gate/otel_genai_semconv）/
lifecycle_orchestration / voice_agent_orchestration / ifc_h_ifc_extension_enabled

**剩余需外部凭据**：

| 能力 | 需配置 | flag |
|---|---|---|
| 向量 RAG 真实 embedding | embedding_api_key + vector_db_url | real_embedding_enabled |
| AI 渲染真实后端 | ai_render_backend_url | real_ai_render_enabled |
| DSPy 优化 | 安装 dspy 依赖 | dspy_enabled |
| 空间感知（户型/承重/管线识别） | 视觉模型 | spatial_perception_enabled |
| 空间推理（设计错误规避） | 规则引擎数据 | spatial_reasoning_enabled |
| 空间交互（设计→施工→采购协同） | 多角色链路 | spatial_interaction_enabled |
| 施工图 MEP 叠加 | PDF/SVG 引擎 | construction_drawing_mep_enabled |

**C 类接入指引（2026-08-11 梳理，配置后置 flag=true 并回归验证）**：

| flag | 配置项 | 代码接入点 | 验证方法 | 成本 |
|---|---|---|---|---|
| real_embedding_enabled | `embedding_api_key`（留空复用 deepseek_api_key）+ `vector_db_url`（Milvus/PGVector/Chroma） | embedding_service.py（False 时跳过真实 embedding） | AgenticRAG 知识检索返回真实向量命中 | embedding API token + 向量库存储 |
| real_ai_render_enabled | `ai_render_backend_url`（本地 ControlNet/ComfyUI 或云 API） | ai_render_service.py L167/240/342（flag+URL 双条件） | AI 渲染返回真实图非 mock（L0 链路） | GPU 推理 |
| dspy_enabled | `pip install dspy` | dspy_optimizer.py（False 时优雅降级返回原始提示词） | prompt 优化/签名编译生效 | 优化期 LLM 调用 |
| spatial_perception_enabled | 视觉模型（户型/承重/管线识别 API） | ai_render_service.py L705 视觉能力标识 | 户型图 → 结构分析链路 | 视觉模型推理 |
| spatial_reasoning_enabled | 规则引擎数据 | 空间推理服务 | 设计错误规避触发 | 低（本地规则） |
| spatial_interaction_enabled | 多角色链路数据 | 空间协同服务 | 设计→施工→采购指令贯通 | 低 |
| construction_drawing_mep_enabled | PDF/SVG 渲染引擎 | construction_drawing_service.py L724（MEP 管线标注叠加） | 施工图含给排水/电气管线走向 | 低（本地渲染） |

**B 类（前端/调试开关，按产品节奏）**：console_v2_enabled / voice_floating_widget_enabled /
workbench_adaptive_suggestions_enabled / tracing_enabled / diagnostics_enabled + rum /
slow_query_explain_enabled / voice_audio_prompt_enabled

## B. 前端缺口页（后端有 API、两端均无独立页面）✅ 已全部补齐（2026-08-09）

> 状态：B1（8 页 Agent 治理）+ B2/B3/B4（无独立页模块）+ C（单端独缺）中 B1 与 C 已落地；
> B2（物联监测 5 模块）、B3（管理后台 4 模块）、B4（供应链边缘 4 模块）属**数据/管理型页面**，
> 依赖 A1 生态桥接或运营接入后方有展示价值，保留待排期。

### B1. Agent 平台治理类（8 个，属平台侧能力，建议 Web console 补）✅ 已完成

| 后端模块 | 路径 | 说明 |
|---|---|---|
| agent_identity | /api/agents/identity | GB/Z 185 智能体身份卡（v1.9.0，flag 门控） |
| agent_approvals | /api/agents/approvals | Agent 工具批准（v1.8.0） |
| agent_skills | /api/agents/skills | Agent Skill 资产（v1.8.0） |
| agent_memory | /api/agents/memory | Agent 长期记忆管理 |
| a2a | /api/a2a | A2A 协议（Agent 间通信） |
| mcp | /api/mcp | MCP Server 管理 |
| harness_api | /api/harness | Agent 测试 Harness |
| eval | /api/eval | Suoke-Eval1 评估 |

### B2. 物联监测类（5 个）✅ 已补齐（2026-08-13，console）

| 后端模块 | 路径 | 说明 | 状态 |
|---|---|---|---|
| energy | /api/energy | 能耗监测（A1） | ✅ EnergyPage 既有（console） |
| sensor_snapshot | /api/sensors | 传感器快照（A5，已与 sensor 触发闭环打通） | ✅ SensorsPage（能力声明 + 数据流向诚实标注） |
| health-monitor | /api/health-monitor | 施工健康巡检（A2） | ✅ HealthMonitorPage |
| construction_drawing | /api/construction-drawing | 施工图（v1.2.0） | ✅ ConstructionDrawingPage（SVG 渲染） |
| analytics | /api/analytics | 前端埋点采集（公开端点，无管理页） | ⏭ 跳过（仅接收不持久化，无管理页价值） |

### B3. 管理后台类（4 个）✅ 已补齐（2026-08-13，Web console）

| 后端模块 | 路径 | 说明 | 状态 |
|---|---|---|---|
| admin | /api/admin | 用户管理/审核（Flutter settings 仅角色图标） | ✅ AdminPage（统计/用户/审计日志） |
| notifications | /api/notifications | 通知（Flutter 仅 services 层推送初始化） | ✅ NotificationsPage |
| files | /api/files | 文件管理 | ✅ FilesPage |
| payments | /api/payments | 支付（api.dart 已有 10 个封装方法） | ✅ PaymentsPage 既有（console） |

### B4. 供应链边缘类（4 个）✅ 已补齐（2026-08-13，Flutter）

| 后端模块 | 路径 | 说明 | 状态 |
|---|---|---|---|
| camera_scan | /api/products/camera | 拍照上架（api.dart 已有方法，无页面调用点） | ✅ CameraScanPage |
| product_batch | /api/products/batch | 批量上传（api.dart 已有方法） | ✅ ProductBatchPage |
| location | /api/location | 位置服务 | ✅ LocationPage |
| voice_realtime | /api/voice/* | 实时语音（Flutter 有 services 层 voice_realtime_service） | ✅ VoiceRealtimePage |

## C. 单端独缺（对方端已覆盖，补齐成本低）

| 缺页端 | 模块 | 对方端 |
|---|---|---|
| Web console（api-client 未封装） | points / ai-image / identity / surveys-AR | Flutter 有页面 |
| Flutter | b2b_delivery / sketch_to_3d / ifc_export | Web 有页面（DeliveryPage/Sketch3DPage/IFCExportPage） |

## D. 建议排期

1. **P0**：A1 生态桥接（需商务/凭据决策，打通 sensor 触发 → 设备控制闭环）
2. **P1**：B1 Agent 治理页（Web console，v1.9.0 GB/Z 185 身份卡需配套展示）✅ 已完成（2026-08-09）
3. **P2**：B2/B3/B4 + C 单端补齐 ✅ **全部完成（2026-08-13）**——B2 物联监测 3 页（Energy 既有）、
   B3 管理后台 3 页（Payments 既有）、B4 供应链边缘 4 页 Flutter；analytics 跳过（仅接收不持久化）
4. **P3**：A2 灰度 flag 按需开启 ✅ **已完成（2026-08-11）**——
   A 类 16 个 + D 类 1 个已默认开启（v1.13.2）；剩余 C 类 7 项需外部凭据、B 类 7 项按产品节奏

> 备注：`app/api/analytics.py` collect_events 为"仅接收不持久化"预留端点（设计如此，勿当 bug）。

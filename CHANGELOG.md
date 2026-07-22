# Changelog

所有版本变更记录。格式参考 [Keep a Changelog](https://keepachangelog.com/)。

## [1.1.29] - 2026-07-22

### 家居补短 5 项落地（独立于索克生活）

#### 新增

- **P0 FC 3.0 微服务拆分** (`serverless/`)
  - 7 个微服务：auth-gateway / agent-orchestrator / design-render / project-flow / commerce / realtime
  - 每个服务独立的 `s.yaml`（FC 3.0 配置）+ `handler.py`（FastAPI 路由挂载）
  - `common/warmup.py` 冷启动优化（OSS 挂载探测 + DB 连接池预热 + 模块预加载）
  - design-render 分配 2GB/600s（CAD/3D 计算密集型），agent-orchestrator 300s（LLM 调用），其余 120s

- **P0 A2UI 协议内化** (`app/services/a2ui_schema.py` + `app/services/a2ui_generator.py` + Flutter/Web renderers)
  - 8 种卡片类型：design_plan / budget_breakdown / construction_progress / procurement_order / qa_report / settlement_summary / material_card / alert_card
  - Agent 输出 → A2UI JSON 自动转换（design_to_card / budget_to_card / qa_to_card 等）
  - Flutter `A2UIRenderer` widget（8 种子卡片 Widget，Material Design）
  - Web `A2UIRenderer` vanilla JS + `a2ui-cards.css` 暗色主题响应式

- **P1 Vault + 合规深化 — HMAC 签名** (`app/services/audit_integrity.py`)
  - HMAC-SHA256 签名（密钥从 PASETO key 派生，版本化支持轮换）
  - `hmac.compare_digest` 防时序攻击
  - 批量完整性校验（`verify_audit_integrity` → `AuditIntegrityReport`）
  - 字段级脱敏标记（L0-L3，按角色）— 金额 L2 / 银行账号 L3 / PII L1
  - 集成到 `audit_log_service.log_audit_event` 自动签名

- **P1 Agentic RAG + Skills System** (`knowledge/` + `app/services/`)
  - 4 个结构化知识库（80 条）：materials / techniques / standards / faq
  - 每条含 `id / content / citation（GB 标准号）/ tags`
  - `knowledge/loader.py` 关键词搜索 + 向量搜索预留
  - `citation_service.py` 来源引用格式化（`📚 参考来源：GB 50210-2018 §4.2.3`）
  - `qa_knowledge_service.py` QAInspectorAgent 专用：`get_checklist(phase)` / `check_standard(material)` / `get_defect_knowledge(keyword)`

- **P2 Health OS 主动干预** (`app/services/health_monitor.py` + `app/services/push_sender.py`)
  - `HealthRuleEngine` 5 级预警规则（NORMAL→ATTENTION→WARNING→SEVERE→CRITICAL）+ 0-100 健康评分
  - `HealthMonitor` 定时巡检器（后台 asyncio 任务）+ 自动创建 `ProgressAlert` + 推送通知
  - `push_sender.py` 多通道推送（FCM/APNs/WebPush/SMS，当前 mock 模式）

#### 变更

- `app/config.py`：app_version 1.1.28 → 1.1.29，新增 6 项 feature flags
- `app/api/config.py`：暴露 v1.1.29 feature flags
- `app/services/audit_log_service.py`：HMAC 签名集成

#### 测试

- `tests/test_v1129_gap_filling.py`：29 项专项测试（微服务/A2UI/HMAC/知识库/Health OS）
- 全量测试通过

## [1.1.28] - 2026-07-22

### 借鉴索克生活（B 方向）10 项落地

将索克生活（中医健康管理平台）的 10 项长线技术决策移植到家居领域。

#### 新增

- **P0-1 Suoke-Eval1 评估框架** (`app/eval/ihome_eval.py`)
  - 10 个家居专用评估维度：BUDGET_ACCURACY / DESIGN_SAFETY / MATERIAL_CONTRAINDICATION / IDOR_RESISTANCE / SSE_LATENCY / FALLBACK_RATE / TOOL_CALL_ACCURACY / REASONING_LEAK_RATE / HC_COMPLIANCE_RATE / COUNTER_ARGUMENT_QUALITY
  - `IHomeEvalRunner` 聚合 AgentHarness 轨迹 + 静态检查 → 维度评分
  - `app/api/eval.py` 暴露 GET /api/eval/report、POST /api/eval/run、GET /api/eval/dimensions

- **P0-2 Model Spec 宪法 + HC 硬约束** (`config/ihome_model_spec.json` + `app/services/rebuttal_engine.py`)
  - 9 条硬约束：HC-001 承重结构 / HC-002 报价含税质保金 / HC-003 材料环保等级 / HC-004 工期缓冲 / HC-005 水电规范 / HC-006 逃生通道 / HC-007 燃气安全间距 / HC-008 防水范围 / HC-009 反面论证义务
  - 3 条软约束：SC-001 风格一致性 / SC-002 预算偏差预警 / SC-003 无障碍适老化
  - `rebuttal_engine` 扫描违规关键词，注入反驳提示重生成
  - 集成到 `BaseAgent.think` / `think_with_tools`（`_rebuttal_check` 辅助方法）

- **P0-3 Feature Validation Pipeline** (`config/intent_contract.json` + `app/utils/intent_validator.py`)
  - 39 个 agent-router pattern 全量登记，含 required_slots / examples / validation_status
  - CI 校验脚本：pattern_id snake_case / validation_status 枚举 / examples ≥1 / 与 agent-router.js 一致性比对
  - 39/39 validated，零警告

- **P1-4 AgenticRAG 证据检索** (`app/services/agentic_rag.py`)
  - 向量数据库语义检索（Qdrant/Milvus）+ 内存关键词匹配双降级
  - 集成到 `think` / `think_with_tools` 前置注入知识库上下文

- **P1-5 Vault/KMS 凭证管理** (`app/services/secret_manager.py`)
  - PASETO key fingerprint（SHA256[:8]）暴露于 `/api/health/detail`
  - Vault/KMS 可选集成（vault_url 配置时拉取密钥，否则降级到本地 .env）
  - `/api/health/detail` 新增 secret_manager + intent_contract 健康检查

- **P1-6 多 LLM fallback chain** (`app/agents/base.py`)
  - PROVIDER_REGISTRY 扩展 qwen（阿里云百炼）+ doubao（火山引擎 ARK）
  - `_chat` 拆分为 `_chat`（fallback 编排）+ `_chat_single_provider`（单供应商调用）
  - 降级链：deepseek → qwen → glm → doubao

- **P2-7 DSPy prompt 优化** (`app/services/dspy_optimizer.py`)
  - ChainOfThought + BootstrapFewShot 提示词优化
  - dspy 可选依赖（懒导入，未安装时返回 base_prompt）

- **P2-8 A2A 协议** (`app/api/a2a.py`)
  - 基于 Google A2A v1.0：Agent Card + Task Machine
  - 5 端点：GET /.well-known/agent-card（公开）/ GET /agents / POST /tasks/send / GET /tasks/{id} / GET /tasks/{id}/status
  - 22 个 Agent 注册，内存任务存储

- **P2-9 PII 全量脱敏** (`app/utils/pii_masking.py`)
  - 8 类 PII：手机号 / 身份证 / 邮箱 / 银行卡 / 护照 / 地址 / 姓名 / IP
  - `mask_dict` 递归脱敏嵌套结构
  - 集成到 `audit_log_service.log_audit_event` details 字段自动脱敏

- **P2-10 TTS 三级降级链** (`app/services/tts_chain.py`)
  - Qwen3-TTS → CosyVoice → Doubao 三级降级
  - OpenAI 兼容 /audio/speech 端点，MP3 输出

#### 变更

- `app/config.py`：app_version 1.1.27 → 1.1.28，新增 10 项 feature flags + qwen/doubao LLM 设置
- `app/agents/base.py`：PROVIDER_REGISTRY 扩展 + _chat fallback + think/think_with_tools AgenticRAG + rebuttal 集成
- `app/services/audit_log_service.py`：details 字段 PII 自动脱敏
- `app/api/config.py`：/api/config/feature-flags 暴露 10 项新 flag
- `app/main.py`：注册 eval + a2a 路由，/api/health/detail 暴露 key fingerprint + intent contract 状态
- `.env`：APP_VERSION 1.1.27 → 1.1.28
- `web/assets/js/app-config.js`：appVersion 1.1.25 → 1.1.28
- `flutter_app/pubspec.yaml`：version 1.1.26+15 → 1.1.28+16
- Web 前端版本号：20260721f → 20260722a（sw.js CACHE_VERSION 同步）

#### 测试

- 新增 `tests/test_v1128_suoke_borrowed.py`：40 项专项测试覆盖全部 10 项
- 全量测试 910 项通过，16 项 skipped
- Flutter analyze 317 issues（全 info/warning，0 error）
- flake8 F401 修复（ihome_eval.py / agentic_rag.py）
- `tests/test_audit_log.py` 更新：适配 PII 脱敏后 IP 127.0.0.1 → 127.0.*.*

---

## [1.1.27] - 2026-07-21

### 性能优化

- 慢查询日志中间件（SQLAlchemy 事件，超阈值 WARNING + Prometheus 直方图）
- 缓存装饰器（@cached 走 cache_service）
- 请求端点规范化（降低 Prometheus label 基数）

## [1.1.26] - 2026-07-21

### API 缓存控制

- 幂等 GET 端点 max-age=30s 缓存
- 动态端点 no-store

## [1.1.25] - 2026-07-21

### 传感器集成评估与 Flutter 端补齐

- Flutter SensorService（sensors_plus + geolocator）
- 跨平台传感器一致性矩阵（Web/Flutter/后端 三端 6 传感器一致）

## [1.1.24] - 2026-07-21

### 智能体路由 + 硬件集成评估与完善

- Agent Router 双端一致性（39 pattern）
- Web 端硬件触发卡片补齐
- HarmonyOS AR 降级实现

## [1.1.23] - 2026-07-21

### 评估报告驱动修复

- Rate Limit 中间件（滑动窗口，60 req/min）
- Audit Log 审计日志（PII 脱敏 + 独立事务）
- 16 项安全专项测试（SQL 注入 / XSS / 路径遍历）
- Alembic 迁移文件入库

## [1.1.13] - 2026-07-20

### 生产部署稳定性修复

- PostgreSQL + asyncpg + aware datetime 三层兼容性
- demo.html 前端质量修复

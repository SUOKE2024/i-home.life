# Changelog

所有版本变更记录。格式参考 [Keep a Changelog](https://keepachangelog.com/)。

## [1.2.0] - 2026-07-23

### 家装全链路专业性提升 — 诊断报告 P1-P5 修复

基于 2026 行业最新技术对标（飞流AI 空间智能 / 鲁班正向算量 / EasyBIM 模型即图纸 / ControlNet 几何锁定），系统修复家装功能五大专业性缺陷，建立"设计→几何→算量→报价→采购→施工→图纸"贯通链路。所有改动配套 feature flag 可回滚。

#### P1 AI 渲染去 stub（消除幻觉债）
- [app/services/ai_render_service.py](app/services/ai_render_service.py) 新增 `render_backend` / `reconstruction_available` 诚实标识字段
- 真实渲染后端接入：`real_ai_render_enabled` + `ai_render_backend_url` 控制 ControlNet 几何锁定调用（对标 2026 Geometry Locking 强制标准）
- `_detect_room_type` 不再用 `len(photo)%len(rooms)` 伪随机，诚实返回 `unknown`（需 `spatial_perception_enabled` 视觉模型）
- `reconstruction_params.available=False` 诚实标识未真实执行（不再伪造 3DGS 参数为已执行）

#### P2 设计→BOM→报价链路贯通（正向设计算量）
- 新增 [app/services/quantity_takeoff_service.py](app/services/quantity_takeoff_service.py)：floorplan.data 作 SSOT，从几何自动派生工程量
- 新增 `forward_takeoff_for_project()`：墙体/地面/吊顶/涂料分项算量，对标鲁班 1:1 BIM 布尔运算
- [app/api/takeoff.py](app/api/takeoff.py) 新增 `GET /takeoff/project/{project_id}` 正向算量端点（含越权校验）
- feature flag：`forward_takeoff_enabled` / `bom_from_geometry_enabled`

#### P3 IFC 真实坐标 + Pset 属性集
- [app/services/ifc_export_service.py](app/services/ifc_export_service.py) 墙体/门窗 placement 用 floorplan.data 真实 start 坐标（不再 `i*5000` 一字排开）
- 新增 `_attach_pset_wall_common` / `_attach_pset_door_common`（FireRating/ThermalTransmittance/IsExternal/材质）
- feature flag：`ifc_real_placement_enabled`（默认 True），关闭回退占位坐标

#### P4 施工图自动生成（模型即图纸）
- 新增 [app/services/construction_drawing_service.py](app/services/construction_drawing_service.py)：从 floorplan 几何生成 SVG 平/立/剖面图
- 新增 [app/api/construction_drawing.py](app/api/construction_drawing.py)：`/construction-drawing/{project_id}/floor-plan|elevation|all`
- "模型即图纸"：floorplan 变 → 图纸自动重生成，无人工干预（对标鲁班/酷家乐）
- feature flag：`construction_drawing_enabled`

#### P5 2D CAD 参数化升级
- feature flag：`parametric_cad_enabled`（前端 cad_page DrawingElement 升级为 BIM 构件，画线即建墙）
- BIM 导出方法：DrawingElement → floorplan.data 兼容 JSON，建立 CAD→算量→图纸链路入口

#### 新增 feature flags（10 个）
- `forward_takeoff_enabled` / `bom_from_geometry_enabled` / `real_ai_render_enabled` / `ai_render_backend_url`
- `ifc_real_placement_enabled` / `construction_drawing_enabled` / `parametric_cad_enabled`
- `spatial_perception_enabled` / `spatial_reasoning_enabled` / `spatial_interaction_enabled`

#### 测试
- 新增 [tests/test_quantity_takeoff_service.py](tests/test_quantity_takeoff_service.py)（10 项）：几何解析 / 正向算量 / SSOT 链路贯通
- 新增 [tests/test_construction_drawing_service.py](tests/test_construction_drawing_service.py)（9 项）：SVG 生成 / 模型即图纸
- 新增 [tests/test_v120_professionalism.py](tests/test_v120_professionalism.py)（11 项）：AI 诚实降级 / IFC 真实坐标 / 端到端链路
- 关键回归 75 passed / 7 skipped（ifc/floorplans/materials/ai_render 全绿）

#### 文档
- 新增 [docs/superpowers/specs/2026-07-23-renovation-professionalism-diagnosis.md](docs/superpowers/specs/2026-07-23-renovation-professionalism-diagnosis.md) 诊断报告
- 新增 [docs/superpowers/specs/2026-07-23-renovation-professionalism-implementation.md](docs/superpowers/specs/2026-07-23-renovation-professionalism-implementation.md) 实施总结

## [1.1.30] - 2026-07-22

### 系统化专业度提升 — 模型约束 + 服务增强 + 前端可视化 + 跨模块编排

#### 新增

- **L1 数据模型约束补齐**（13 个模型文件）
  - 172 个 CHECK 约束（枚举值限值、正值约束、范围约束）
  - 32 个 `deleted_at` 软删除字段
  - 覆盖：budget、material、product、construction、procurement、kitchen、bathroom、lighting、hard_decoration、soft_furnishing、door_window_waterproof、custom_furniture、smart_home

- **L1 施工/采购 Service 强化**
  - `construction_service`: `add_task_dependency` / `get_task_chain` / `estimate_duration` / `generate_wbs`（8 阶段标准 WBS）/ `calculate_critical_path`（拓扑排序 + 前向/后向传播）
  - `ConstructionTask` 新增 `predecessor_id` 自引用外键 + `successors` 关系
  - `procurement_service`: `generate_from_bom` / `compare_suppliers` / `verify_delivery` / `link_to_construction` / `get_material_availability`
  - `ProcurementOrder` 新增 `construction_task_id` + `material_delivered_at`；`OrderLine` 新增 `delivered_quantity`

- **L1 前端可视化** (`Flutter`)
  - `FloorPlanCanvas` 组件：4 层渲染（网格/房间/组件/MEP）、暗色主题适配、pan/zoom、snap-to-grid
  - 厨房页面新增"平面图" Tab：组件点击→详情 BottomSheet

- **L2 事件驱动编排层**
  - `app/services/event_bus.py`：12 事件类型 + 装饰器注册 + `asyncio.gather` 并发分发 + 错误隔离
  - `app/services/orchestration_rules.py`：5 条编排规则（BOM→采购 / 材料到货→施工 / 验收→推进 / 变更→预算 / 项目创建→预算）
  - 接入 `main.py` 启动生命周期，受 `integration_event_bus_enabled` feature flag 控制

- **L2 合规校验全覆盖**（5 个服务模块，12 个新函数）
  - `lighting`: `check_illuminance_compliance`（GB 50034）/ `check_glare_compliance` / `check_uniformity`
  - `hard_decoration`: `check_floor_slip_resistance`（DIN 51130）/ `check_wall_fire_rating`（GB 50222）
  - `smart_home`: `check_weak_current_box`（GB 50311）/ `check_safety_compliance`
  - `mep`: `check_equipotential_bonding`（GB 50096）/ `check_load_balance` / `check_drainage_slope`（GB 50015）
  - `custom_furniture`: `check_furniture_load_capacity`

#### 变更

- `app/config.py`：app_version 1.1.29 → 1.1.30，新增 `integration_event_bus_enabled` feature flag
- `app/models/construction.py`：ConstructionTask 新增 predecessor_id + successors 关系
- `app/models/procurement.py`：ProcurementOrder 新增 construction_task_id + material_delivered_at；OrderLine 新增 delivered_quantity
- `tests/test_audit_log.py`：适配 PII 脱敏后的 _hmac 注入

#### 测试

- 后端 pytest：936 通过（2 预存审计日志测试已修复）
- Flutter analyze：0 error（470 warnings/infos 为预存）
- Flutter test：42 passed（3 失败为预存编译问题 `Icons.hammer`）

#### 清理

- 清理 14 个 `__pycache__` 目录 + 331 个 `.pyc` 文件

---

### L3 补充批次（同日）

#### 新增

- **FloorPlanCanvas 扩展** – 6 个页面完成可视化改造
  - `mep_page`: 新增"点位图" Tab（电/水/燃气三色图例）
  - `custom_furniture_page`: 新增"布局图" Tab（7色模块类型 + BOM 摘要 + 模块图例）
  - `smart_home_page`: 新增"设备布局图" Tab（5色设备分类 + 区域分组 + 设备数量徽章）
  - `bathroom_page`: 新增"平面图" Tab（设施布局 + 点击详情弹窗）
  - `lighting_page`: 新增"布局图" Tab（色温渐变条 + 灯具颜色编码）
  - `hard_decoration_page`: 新增"方案预览" Tab（材质颜色编码 + 墙面/天花注释浮层）

- **FloorPlanCanvas 交互增强**
  - 拖拽移动（drag-to-move + 网格吸附 + 阴影/虚线反馈）
  - 缩放控件（百分比徽章 + ±按钮 + 80×80 小地图）
  - 双击重置视图（300ms 动画）

- **施工甘特图** (`GanttChart` 组件)
  - CPM 关键路径计算 + 依赖贝塞尔箭头 + 进度填充 + 今日线
  - 施工页面新增"甘特图 / 列表"视图切换

- **AI 辅助排程** (`construction_service.ai_predict_duration`)
  - PERT 三点估算法（乐观/最可能/悲观）
  - 历史同类型项目工期统计 + 置信度评分
  - 风险因素自动识别

- **AI 材料推荐** (`material_service.recommend_materials`)
  - 品类匹配 + 风格关键词 + 品牌评分 + 环保等级推断
  - 预算等级自适应（economy / standard / premium）
  - Top 5 推荐 + 匹配度评分 + 推荐理由 + 总预算利用率

- **API 端点暴露**（11 个新端点）
  - `construction`: WBS 生成 / 任务依赖 / 关键路径 / AI 工期预测 / 工期估算
  - `procurement`: BOM→采购 / 供应商比价 / 到货核验 / 施工联动 / 库存查询

#### 变更

- `.env`: APP_VERSION 1.1.29 → 1.1.30
- `smart_home_page.dart`: 替换 `Icons.floor_plan` → `Icons.architecture`

#### 测试

- 后端 pytest: 全量通过
- Flutter analyze: 0 error（本文变更范围内）
- Flutter test: 50 passed

---

### 终验修复批次（同日）

#### 修复

- `chat_message_card.dart`: 修复 `Icons.hammer` → `Icons.handyman`（不存在的图标）；修复 `const TextStyle` 中非 const 变量引用
- `custom_furniture_page.dart`: 修复语法错误（单字符多余 `},` → `)`）

#### 测试

- 新增 3 个 Service 层测试文件（31 passed, 3 xfailed）
  - `test_construction_service.py`: 15 tests — WBS/依赖/工期/CPM/AI 预测
  - `test_procurement_service.py`: 9 tests — 比价/核验/库存
  - `test_material_service.py`: 10 tests — 材料推荐
- 3 个 xfail 暴露模型缺陷：phase 枚举不匹配、缺少 actual_duration_days 字段、Floor.area 字段名不一致

#### 验证

- 后端 pytest: 31 新测试通过（全量 +34）
- Flutter test: 50 passed（之前 42+3fails → 全修复后全绿）
- Flutter analyze: 0 error
- 残留 .pyc: 0

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

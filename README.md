# i-home.life

> **索克家居 · AI 智能装修平台**
>
> v1.1.28 · 借鉴索克生活 B 方向 10 项落地：Suoke-Eval1 评估框架 + Model Spec HC 硬约束 + 意图契约校验 + AgenticRAG + Vault 密钥管理 + 多 LLM fallback + DSPy 优化 + A2A 协议 + PII 脱敏 + TTS 降级链（2026-07-22）
> 核心能力：15 工具 CAD 设计台 + 平立剖 6 视图（含任意剖切）+ DWG/DXF 导入 + 22 Agent 全链路 + L4 偏好学习 + MCP 协议外露 + AI 渲染（2D/3D/restage）+ 语音情绪路由 + WebGPU 智能降级 + 475+ API + Flutter 41 页面 + 三端覆盖（iOS/Android/HarmonyOS）+ PASETO 认证 + PWA 离线

## 最近更新

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
│   ├── api/           # 46 个路由模块 (461 端点)
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
│   ├── agents/        # 10 个 AI Agent (业务逻辑版)
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
│   ├── models/        # 80+ ORM 模型 (41 文件)
│   ├── schemas/       # 40+ Pydantic 验证模块
│   ├── services/      # 43 个业务服务
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
| **合计** | | **461 端点** |

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

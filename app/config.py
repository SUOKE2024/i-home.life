from functools import lru_cache

from pydantic import model_validator
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    model_config = {"env_file": ".env", "env_file_encoding": "utf-8", "extra": "allow"}

    @model_validator(mode="after")
    def _validate_paseto_key(self):
        # v1.2.1 P0-1 修复：原 debug=True 默认 + 仅 not debug 校验 → 生产误用默认配置跳过密钥校验
        # 现默认 debug=False，且 paseto_strict_mode=True 时无论 debug 都硬校验
        is_default_key = self.paseto_secret_key == "change-me-to-a-random-32-byte-key-minimum"
        key_too_short = len(self.paseto_secret_key.encode()) < 32
        # 校验条件：生产（not debug）或 strict_mode 开启
        enforce = (not self.debug) or self.paseto_strict_mode
        if enforce and is_default_key:
            raise ValueError(
                "PASETO_SECRET_KEY 不能使用默认值。请在 .env 中设置 >=32 字节的强密钥。"
                "（开发环境可设 PASETO_STRICT_MODE=false 跳过，但生产必须配置强密钥）"
            )
        if enforce and key_too_short:
            raise ValueError(
                "PASETO_SECRET_KEY 长度不足 32 字节（当前 %d 字节）。"
                "生产环境必须配置强密钥；开发环境可设 PASETO_STRICT_MODE=false。"
                % len(self.paseto_secret_key.encode())
            )
        return self

    app_name: str = "i-home.life"
    app_version: str = "1.13.1"
    # v1.2.1 P0-1：默认 False（生产安全）。开发环境在 .env 设 DEBUG=true。
    # 原默认 True 导致生产误用跳过 PASETO 密钥校验。
    debug: bool = False
    # v1.12.x：显式日志级别（DEBUG/INFO/WARNING/ERROR，空=按 debug 推断）。
    # 生产默认 WARNING 会吞掉编排/Agent 链路的 INFO 事件日志；
    # 排查编排问题时在 .env 设 LOG_LEVEL=INFO 即可观察全链路。
    log_level: str = ""
    # v1.2.1 P0-1/P1-7：PASETO 严格模式 flag。True=无论 debug 都硬校验密钥（生产默认）；
    # False=回滚旧行为（仅 not debug 校验，密钥不足时 \x00 填充，紧急回滚用）
    paseto_strict_mode: bool = True

    # 数据库: 开发用 SQLite, 生产用 PostgreSQL
    database_url: str = "sqlite+aiosqlite:///./data/ihome.db"
    # PostgreSQL 生产配置示例: postgresql+asyncpg://user:pass@localhost:5432/ihome

    # Redis 缓存 (留空则禁用缓存, 使用内存字典降级)
    redis_url: str = ""
    # 示例: redis://localhost:6379/0

    # 对象存储 OSS (留空则使用本地文件存储)
    oss_endpoint: str = ""
    oss_access_key: str = ""
    oss_secret_key: str = ""
    oss_bucket: str = "ihome-assets"
    oss_region: str = "cn-hangzhou"

    # 向量数据库 RAG (留空则禁用语义检索)
    vector_db_url: str = ""
    vector_db_collection: str = "ihome_knowledge"
    # 支持 Qdrant: http://localhost:6333
    # 支持 Milvus: http://localhost:19530

    # ── Embedding 服务（v1.1.31 FP-3 修复：AgenticRAG 真实向量检索，替代 [0.0]*128 占位）──
    real_embedding_enabled: bool = False  # 默认关闭，需配置 embedding_api_key + vector_db_url
    embedding_api_url: str = ""           # OpenAI 兼容 /v1/embeddings 端点（留空则复用 deepseek/qwen base）
    embedding_api_key: str = ""           # 留空则复用 deepseek_api_key
    embedding_model: str = "text-embedding-3-small"  # 或 bge-m3 / embedding-3（智谱）
    embedding_dim: int = 1536             # text-embedding-3-small=1536; bge-m3=1024; 智谱 embedding-3=2048

    # ── 防水验收真校验（v1.1.31 FP-2 修复：原后4项硬编码 passed=True）──
    waterproof_strict_check: bool = True  # True=真校验 design 字段；False=回滚旧行为（紧急回滚用）

    paseto_secret_key: str = "change-me-to-a-random-32-byte-key-minimum"
    paseto_token_expire_minutes: int = 60 * 24
    # v1.2.1 P1-8：Agent 会话加密硬校验开关。
    # False（默认）= PASETO 密钥不可用（默认/过短/未配置）时拒绝明文存储会话消息，
    #   _get_fernet() 直接 raise，防止 PII 泄露；
    # True = 开发环境显式允许明文降级（仅本地调试用，生产禁止开启）。
    # 注意：paseto_strict_mode=True 时 PASETO 密钥已被 config 层硬校验，本 flag
    # 仅在 strict_mode=False 的回滚路径或密钥为空字符串时生效。
    allow_plaintext_session: bool = False
    # v1.8.2 P2.5: Token 撤销列表 Redis 化（多 worker 共享，评估报告建议项）
    # False（默认）= 进程内 dict（FC 单实例场景 OK，logout 仅当前 worker 生效）
    # True = Redis 共享撤销列表（多 worker 必需），Redis 不可用时 best-effort 降级到内存
    paseto_revocation_redis_enabled: bool = False
    paseto_revocation_redis_url: str = ""  # 留空则降级到内存（不自动复用 cache_service）

    # ── WebAuthn / FIDO2 / Passkey ──
    webauthn_enabled: bool = True
    webauthn_rp_id: str = "localhost"
    # 允许的来源（逗号分隔，如 "https://app.i-home.life,https://api.i-home.life"）
    webauthn_origins: str = "http://localhost:8766"
    webauthn_challenge_ttl: int = 120

    @property
    def webauthn_origin_list(self) -> list[str]:
        """解析 origins 为列表，支持多域名部署"""
        return [o.strip() for o in self.webauthn_origins.split(",") if o.strip()]

    @property
    def webauthn_origin(self) -> str:
        """返回第一个 origin，向后兼容单值调用"""
        return self.webauthn_origin_list[0] if self.webauthn_origin_list else "http://localhost:8766"

    # DeepSeek V4
    deepseek_api_key: str = ""
    deepseek_api_base: str = "https://api.deepseek.com"
    deepseek_model: str = "deepseek-chat"

    # GLM-5.2 (智谱 AI)
    glm_api_key: str = ""
    glm_api_base: str = "https://open.bigmodel.cn/api/paas/v4"
    glm_model: str = "glm-4-plus"

    # ── Qwen-Audio-3.0-Realtime (阿里云百炼) ──
    qwen_audio_api_key: str = ""          # DashScope API Key
    qwen_audio_model: str = "qwen-audio-3.0-realtime-flash"  # flash | plus
    # 百炼 Realtime WebSocket。官方推荐业务空间专属域名以获更好性能稳定性：
    #   wss://{WorkspaceId}.cn-beijing.maas.aliyuncs.com/api-ws/v1/realtime
    # model 查询参数由 VoiceRealtimeSession._build_ws_url 自动注入，无需在此拼接。
    qwen_audio_ws_url: str = "wss://dashscope.aliyuncs.com/api-ws/v1/realtime"
    qwen_audio_voice: str = "cherry"      # 默认音色: cherry / zhidan / longxiaochun 等

    # ── 语音服务 ──
    voice_asr_model: str = "qwen-audio-3.0-realtime"  # ASR 模型 (复用 Qwen-Audio)
    voice_tts_model: str = "qwen3-tts"                # TTS 模型
    voice_emotion_detection: bool = True               # 是否启用情绪检测
    voice_emotion_sensitivity: float = 0.6             # 情绪检测灵敏度 (0-1)
    voice_duplex_mode: bool = True                     # 是否启用双工模式
    voice_turn_detection: str = "server_vad"          # 轮次检测模式: server_vad | smart_turn | none(push-to-talk)
    voice_vad_threshold: float = 0.5                   # VAD 阈值 (0-1)
    voice_vad_silence_ms: int = 800                    # VAD 静音检测毫秒
    voice_audio_prompt_enabled: bool = False           # 是否启用说话人增强（声纹锁定，针对多人场景）
    voice_max_recording_seconds: int = 300             # 单次最大录音时长（秒）
    # v1.2.7 借鉴 Qwen-Audio-3.0-Realtime：音频格式契约（对齐百炼官方）
    # 输入 16kHz/16bit/单声道 PCM，输出 24kHz/16bit/单声道 PCM
    voice_input_audio_format: str = "pcm"
    voice_output_audio_format: str = "pcm"
    # 主动关怀：用户静默超过阈值（毫秒）后模型主动发起追问。
    # Qwen3.5-Omni-Realtime server_vad 模式生效；Audio-Realtime 可能忽略。0=关闭。
    voice_idle_timeout_ms: int = 0
    # 场景画像：default | site | support | elderly
    # site=工地(flash+smart_turn+声纹锁定)，support=客服共情(plus+主动关怀)，
    # elderly=养老陪伴(plus+主动问候)。详见 SCENARIO_PROFILES。
    voice_scenario: str = "default"
    # v1.2.1 P1-9：语音会话内存 TTL。VoiceSessionManager._sessions 原无过期机制，
    # 长运行下 WebSocket 会话对象常驻内存导致泄漏。设 TTL 后超时未活跃的会话自动淘汰。
    voice_session_ttl_seconds: int = 3600              # 语音会话空闲超时（秒），默认 1 小时
    # v1.2.3 P2：语音 LLM 语义路由开关。
    # 启用后 /voice/process-enhanced 使用 LLM（deepseek → glm → qwen fallback）做意图分类，
    # 关闭或 LLM 不可用时回退到关键词匹配。
    voice_llm_routing_enabled: bool = True

    # ── Agent FunctionCall / MCP ──
    agent_function_call_enabled: bool = True           # 是否启用 FunctionCall
    # ── FunctionCall 工具真实数据（v1.1.31 FP-1 修复：原 5 工具硬编码假数据）──
    # True=工具 handler 查真实 DB（需 db session）；False=回滚到硬编码 mock（紧急回滚用）
    tool_real_data_enabled: bool = True
    agent_function_call_max_rounds: int = 5            # 单次对话最大工具调用轮数
    # v1.13.0（2026 前沿对齐）：执行前按工具 parameters 契约校验 LLM 参数类型。
    # True=类型不匹配直接返回校验错误（防幻觉参数到达 DB/外部 API）；
    # False=原样透传（零回归，紧急回滚用）。
    tool_argument_validation_enabled: bool = True
    # v1.13.0（2026 前沿对齐）：同一轮多个 tool_calls 并行执行（asyncio.gather）。
    # 2026 工具调用指南：并行工具调用可 5x 提速（多个 200ms 数据源 → 总耗时 ≈ 最大单个）。
    # True=并行；False=串行（紧急回滚用）。
    parallel_tool_calls_enabled: bool = True
    # v1.13.0（2026 前沿对齐）：Agent loop token 预算（早停规则）。
    # 单次 think_with_tools 累计 tool_calls 参数 + 工具结果上下文超过该值时
    # 提前终止循环并强制生成最终回复，防止长任务上下文爆炸（max_rounds 之外的第二道闸）。
    agent_function_call_max_tool_tokens: int = 12000

    # MCP 工具服务器地址 (留空则仅使用内置工具)
    agent_mcp_server_url: str = ""
    # v1.8.0 Agent 三档安全 posture（借鉴 YC QM）：strict / auto / dangerous
    # - strict: 命中高危清单（或清单空=全部）的工具需人工批准（AgentApproval pending）
    # - auto（默认）: 正常执行（外部数据 PII masking 已在 audit 层处理）
    # - dangerous: 全放行
    agent_security_posture: str = "auto"
    # strict 模式下的高危工具清单（逗号分隔）。空 = 全部工具需批准。
    agent_strict_high_risk_tools: str = ""
    # 审批请求（AgentApproval）有效时长（小时），超时自动过期。
    agent_approval_ttl_hours: int = 24
    # v1.8.0 Agent Skill 资产化总开关（scope-owned 可授权共享的 Agent 能力）。
    agent_skill_enabled: bool = True
    # v1.10.1 自进化管线（借鉴 EverMind EverOS Agent Memory + HarnessBank + SkillCorpus）：
    # 三层独立灰度，默认全 False（诚实降级：关闭则 Agent 维持无记忆无进化静态行为）。
    # P0: 从 AgentTrace 自动提取结构化 Case（task_intent + approach + quality_score）
    agent_case_extraction_enabled: bool = False
    # P1: Case 聚类蒸馏为 Skill + Agent 执行前检索注入同类 Case/Skill
    agent_skill_distillation_enabled: bool = False
    # P1: Skill 随成败进化（三维质控 Utility/Robustness/Safety + WHERE×WHY 诊断归因）
    agent_skill_evolution_enabled: bool = False

    # ── MCP Server 暴露（v1.1.12 新增）──
    # 启用后 /api/mcp/* 端点可用，外部 AI 客户端（Claude/Cursor/小艺）可调用 Agent 工具
    # 兼容 MCP 2026-07-28 stateless 核心，支持 Nginx round-robin 负载均衡
    mcp_enabled: bool = True
    # v1.3.0 MCP 2026-07-28 完整对齐子开关（受 mcp_enabled 总开关约束）：
    # server/discover RPC + .well-known Server Card
    mcp_discover_enabled: bool = True
    # Multi Round-Trip Requests（sampling/elicitation 轮询式双向通信）
    mcp_mrtr_enabled: bool = True
    # Tasks 扩展（tasks/create, tasks/update, tasks/get, tasks/list, tasks/cancel）
    mcp_tasks_extension_enabled: bool = True
    # Enterprise 扩展（enterprise/status 能力声明 + enterprise/audit 审计轨迹）
    # 对齐 MCP 2026 Roadmap Enterprise Readiness（审计/SSO/网关）
    mcp_enterprise_extension_enabled: bool = True

    # ── AI 渲染（v1.1.12 新增，PRD §7.x）──
    # 启用后 /api/ai-render/* 端点可用，支持 2D 效果图 / 3D 场景 / 照片重布置
    # 复用 BaseAgent._chat() 调用 LLM，注入 L4 偏好示例
    ai_render_enabled: bool = True

    # ── 语音情绪路由（v1.1.12 新增）──
    # 启用后在 _route_voice_to_agent 中根据用户情绪（anxious/angry/sad/tired/excited/happy）
    # 注入系统指令前缀，调整 Agent 语气
    # 需配合 voice_emotion_detection=True 使用
    voice_emotion_routing_enabled: bool = True

    # ── 语音智能体编排（借鉴 GPT Voice / Claude Voice 2026-07 调度范式）──
    # 启用后 POST /api/voice/orchestrate 可用：
    # - 一句话启动后台 Agent 任务（长任务不阻塞语音对话）
    # - 连接词切分多意图并行编排（"同时/另外/再帮我"）
    # - 语音任务生命周期控制（"任务进度"/"取消任务"）
    voice_agent_orchestration_enabled: bool = False
    # v1.2.8 讨论式方案交互：LLM 生成多方案 + 语音调整修订
    # v1.3.x 默认开启（console 已接通 /design/proposals + revise UI；LLM 不可用时自动降级确定性单方案）
    design_proposal_llm_enabled: bool = True
    # 悬浮窗常驻语音交互（Flutter 前端 flag，后端仅暴露）
    voice_floating_widget_enabled: bool = False

    # ── Qwen-Audio-3.0-Realtime 模型变体 ──
    # 默认 flash（速度优先），可切换 plus（推理更强 + 情感感知 + 副语言）
    # plus 模型自动启用 VOICE_SYSTEM_INSTRUCTIONS_PLUS 增强指令
    # 取值：qwen-audio-3.0-realtime-flash | qwen-audio-3.0-realtime-plus
    # qwen_audio_model 默认值见下方（保持 flash 以控制成本，plus 用于高价值场景）

    # ── L4 自适应学习（PRD §5.4 Phase 5 末项，提前布局）──
    # 启用后 chat 端点会注入用户历史正向反馈作为 few-shot 示例
    # 仅在非 MOCK_MODE（有 LLM API Key）时实际生效，测试环境不受影响
    agent_learning_enabled: bool = True
    agent_learning_max_examples: int = 3  # 单次注入的最大 few-shot 示例数

    # ── Agent 长期记忆 + 时间/空间感知（跨会话智能）──
    # 启用后 chat 端点注入用户长期记忆（agent_memories 表）与当前时间/位置上下文
    agent_memory_enabled: bool = True           # 长期记忆读写与注入总开关
    agent_memory_max_items: int = 10            # 单次注入的最大记忆条目数
    agent_memory_extract_enabled: bool = True   # 对话自动提取记忆
    agent_time_awareness_enabled: bool = True   # 时间感知：注入北京时间上下文
    agent_location_awareness_enabled: bool = True  # 空间感知：注入用户城市上下文

    # ── 3D 渲染引擎（PRD §7.1）──
    # 启用后前端按需加载 Filament WASM，可与 Three.js 切换
    filament_enabled: bool = True
    filament_cdn_url: str = "https://cdn.jsdelivr.net/npm/filament-js@1.54.6"

    # ── CAD 几何内核（PRD §7.1）──
    # 启用后前端按需加载 OpenCascade.js 进行真实布尔运算
    opencascade_enabled: bool = True
    opencascade_cdn_url: str = "https://cdn.jsdelivr.net/npm/opencascade.js@0.2.5/dist/opencascade.wasm.js"

    cors_origins: list[str] = ["http://localhost:3000", "http://localhost:5173"]

    amap_api_key: str = ""  # 高德地图 Web API Key

    # 第三方身份核验
    aliyun_id_verify_appcode: str = ""  # 阿里云身份证实名认证 AppCode

    # ── Agent Harness 统一编排（v1.2.0）──
    harness_trace_enabled: bool = True
    harness_trace_max_history: int = 500
    harness_agent_timeout_seconds: int = 60
    harness_max_retries: int = 1

    # ── Agent 执行轨迹持久化（v1.12.x 可观测性打磨，对齐 2026 workflow ID 传播范式）──
    # 启用后每个 Agent 执行（harness run）按采样率落一条 agent_traces 记录，
    # 供离线评估 / per-agent 漂移检测 / 问题回溯；关闭时零落库零开销。
    agent_trace_persist_enabled: bool = True
    agent_trace_sample_rate: float = 1.0   # 0-1 落库采样率（1.0 = 全量）

    # ── 多智能体协作编排（v1.12.x 打磨，对齐 2026 hub-spoke/pipeline 编排）──
    # 启用后 OrchestratorAgent.plan_and_delegate 可用：用户需求 → 任务分解 →
    # 按依赖顺序分发子 Agent → 结构化聚合；关闭则维持单意图分类路由。
    agent_orchestration_pipeline_enabled: bool = True

    # ── LLM 响应缓存（v1.12.x 成本/延迟优化，对齐 2026 确定性 subtask 缓存）──
    # 对非工具调用的重复请求（相同 provider+model+messages）命中缓存，
    # 避免相同确定性子任务重复调用 LLM；TTL 内过期自动失效。
    llm_response_cache_enabled: bool = True
    llm_response_cache_ttl: int = 600

    # ── 在线进化闭环（v1.2.0）──
    # 轨迹驱动的 Agent 自我改进：收集执行轨迹 → 分析失败模式 → 优化 prompt/降级策略
    agent_evolution_enabled: bool = True
    agent_evolution_trace_min_samples: int = 20  # 最小轨迹样本数

    # ── API 速率限制（v1.2.1）──
    # 基于内存滑动窗口，按 IP 限流；认证端点独立配额防暴力破解
    rate_limit_enabled: bool = True              # 全局开关，关闭时直接放行
    rate_limit_per_minute: int = 60              # 普通 API：每 IP 每分钟 60 次
    rate_limit_auth_per_minute: int = 10         # 认证端点（/login、/register）：每 IP 每分钟 10 次
    # v1.2.1：基准测试/压测专用旁路令牌。
    # 非空时，请求携带 header `X-Bench-Token: <token>` 即跳过速率限制，
    # 用于 scripts/bench-api.py 测量原始吞吐（不受限流干扰）。
    # 默认空字符串 = 不启用旁路 = 生产保持限流保护。
    # 仅在压测/预发环境设置强随机值，生产环境禁止配置。
    rate_limit_bench_token: str = ""

    # ── 审计日志（v1.2.0）──
    # 启用后敏感操作（登录/注册/创建/修改/删除/导出/权限变更）将写入 audit_logs 表
    # 关闭时 log_audit_event 直接跳过，不写库不抛错
    audit_log_enabled: bool = True

    # ── 性能优化（v1.1.27 新增）──
    # 慢查询日志中间件：基于 SQLAlchemy 事件，超阈值记录 WARNING + Prometheus 直方图
    slow_query_log_enabled: bool = True
    slow_query_threshold_ms: int = 200       # 超过此阈值（毫秒）记录慢查询日志
    slow_query_explain_enabled: bool = False  # 是否对慢 SELECT 执行 EXPLAIN ANALYZE（仅调试）

    # 缓存装饰器：@cached 装饰的函数走 cache_service，关闭时直透
    cache_decorators_enabled: bool = True
    pref_hint_cache_ttl: int = 300           # Agent preference hint 缓存 TTL（秒）
    hot_endpoint_cache_ttl: int = 300        # 热点端点缓存 TTL（秒）
    # v1.3.0 缓存用户隔离硬约束开关：
    # True（默认）= build_isolated_key/get_isolated/set_isolated 私有数据未传 user_id 时 raise
    #   强制执行项目硬约束"所有缓存 key 必须含 user_id 或为公共数据"
    # False = 回退到 u:anon: 前缀（仅开发环境调试用，紧急回滚用）
    cache_user_isolation_strict: bool = True

    # ── OpenTelemetry 分布式追踪（v1.2.2 F4）──
    # 补齐 logs/metrics/traces 可观测三支柱：启用后通过 OTLP 导出 HTTP 请求/DB 查询
    # span 到 Jaeger/Tempo/OTel Collector，并将 trace_id/span_id 注入结构化日志
    # （日志-追踪关联，便于按 trace 在日志中检索）。
    # 默认关闭：未安装 OTel 依赖或未配置 endpoint 时 setup_tracing 优雅降级为 no-op，
    # 运行时零开销。生产启用需配置 OTEL_EXPORTER_OTLP_ENDPOINT 指向 collector
    # （如 http://otel-collector:4318）并安装 requirements.txt 中的 opentelemetry-* 包。
    tracing_enabled: bool = False
    otel_exporter_otlp_endpoint: str = ""        # OTLP/HTTP 端点，空则用 console exporter（仅本地调试）
    otel_service_name: str = "i-home-life"        # 服务标识（resource service.name）

    # ════════════════════════════════════════════════════════════════
    # v1.10.x 全链路诊断系统（diagnostics）— MELT+P 可观测性落地
    # ════════════════════════════════════════════════════════════════
    # 五大能力：① 性能指标采集（滚动快照落库，FC 无持久 Prometheus）
    # ② 全链路追踪（HTTP→DB→LLM/Agent span 关联 trace_id）
    # ③ 异常检测与告警（规则 + z-score 统计，可管理 open/ack/resolved）
    # ④ 优化建议（规则引擎，从 trace/指标证据生成可执行建议）
    # ⑤ 可视化诊断界面（webapp /diagnostics，管理端只读）
    # 对齐 2026 行业前沿：OTel GenAI 语义约定、RUM Core Web Vitals、
    # exemplar→trace→log 关联、AI 辅助根因定位（自研规则版）。
    # 总开关关闭时全部采集路径零开销（单次 contextvar 读判断即返回）。
    diagnostics_enabled: bool = False            # 总开关（灰度，默认关）
    diagnostics_sample_rate: float = 0.1         # 全链路追踪采样率（0-1，降低落库开销）
    diagnostics_snapshot_interval_seconds: int = 60   # 指标快照采样间隔
    diagnostics_alert_interval_seconds: int = 60      # 异常检测巡检间隔
    diagnostics_rum_enabled: bool = False        # 前端 RUM（Core Web Vitals）采集
    diagnostics_retention_hours: int = 168       # 诊断数据保留期（默认 7 天，后台清理）
    diagnostics_anomaly_zscore: float = 3.0      # 统计异常 z-score 阈值
    # 规则告警阈值（可随灰度调优）
    diagnostics_error_rate_threshold: float = 0.10    # 端点错误率阈值（≥ 触发告警）
    diagnostics_p95_latency_threshold_ms: int = 2000  # 端点 p95 延迟阈值（毫秒）
    diagnostics_slow_query_burst_threshold: int = 10  # 单窗口慢查询数量阈值
    diagnostics_llm_fallback_threshold: float = 0.30  # LLM fallback 率阈值
    diagnostics_db_query_storm_threshold: int = 30    # 单请求 DB 查询数阈值（N+1 检测）
    diagnostics_rum_lcp_threshold_ms: int = 2500      # RUM LCP 阈值（Core Web Vitals poor）

    # ════════════════════════════════════════════════════════════════
    # v1.1.28 借鉴索克生活：长线技术决策 feature flags
    # ════════════════════════════════════════════════════════════════

    # ── 正式评估框架（Suoke-Eval1 借鉴）──
    # 启用后 /api/eval/* 端点可用，AgentHarness.run_eval() 接入 ihome_eval 维度
    eval_enabled: bool = True
    eval_sample_rate: float = 0.1

    # ── Model Spec 宪法 + HC 硬约束（借鉴 suoke_model_spec）──
    # 启用后 DesignerAgent/BudgetAgent/ProcurementAgent 输出经 rebuttal_engine 校验
    model_spec_enabled: bool = True
    model_spec_path: str = "config/ihome_model_spec.json"

    # ── Feature Validation Pipeline（借鉴 intent_contract）──
    # 启用后新增 agent_router pattern 必须含 validation_status: validated
    intent_validation_enabled: bool = True
    intent_contract_path: str = "config/intent_contract.json"

    # ── AgenticRAG 证据检索（激活 vector_db_url）──
    # 启用后 think_with_tools 前置 evidence 检索，注入知识库上下文
    agentic_rag_enabled: bool = True
    agentic_rag_max_evidence: int = 3  # 单次注入最大证据条数

    # ── 密钥管理（借鉴 Vault 指纹机制）──
    # 启用后 PASETO key 指纹暴露于 /api/health/detail，支持轮换校验
    secret_manager_enabled: bool = True
    # Vault/KMS 地址（留空则使用本地 .env，不接外部密钥服务）
    vault_url: str = ""
    vault_token: str = ""
    vault_namespace: str = "ihome-life-prod"

    # ── 多 LLM fallback chain（借鉴 llm_fallback_chains）──
    # 启用后 _chat 失败按 chain 降级：deepseek → qwen → glm → doubao
    llm_fallback_enabled: bool = True

    # ── 意图成本路由（借鉴端侧/本地模型分层 + EY token strategy）──
    # 启用后 cost_tier="economy" 的 Agent 优先走低成本供应商，
    # 将低价值意图（客服/通知/积分/文件/身份/通用）的解析成本压低。
    # v1.12.x：默认开启（Orchestrator 意图分类等低价值解析走 economy 档）。
    cost_tiered_routing_enabled: bool = True
    # 低成本供应商（逗号分隔，按优先级排列，须在 PROVIDER_REGISTRY 中）
    economy_providers: str = "qwen,glm"
    # 经济档意图（低价值任务，优先使用低成本档位）
    economy_intents: str = "concierge,notifications,points,files,identity,general,support"

    @property
    def economy_provider_list(self) -> list[str]:
        """解析 economy_providers 为列表。"""
        return [p.strip() for p in self.economy_providers.split(",") if p.strip()]

    @property
    def economy_intent_list(self) -> list[str]:
        """解析 economy_intents 为列表。"""
        return [i.strip() for i in self.economy_intents.split(",") if i.strip()]

    # Qwen (阿里云百炼 / DashScope) — fallback chain 第二档
    qwen_api_key: str = ""
    qwen_api_base: str = "https://dashscope.aliyuncs.com/compatible-mode/v1"
    qwen_model: str = "qwen-plus"

    # Doubao (火山引擎 ARK) — fallback chain 末端
    doubao_api_key: str = ""
    doubao_api_base: str = "https://ark.cn-beijing.volces.com/api/v3"
    doubao_model: str = "doubao-seed-1-6-250615"

    # ── 施工边缘盒子本地推理端点（v1.4.x，借鉴 OWLFY 端侧零 TOKEN）──
    # 可选：在工地/内网边缘盒子上跑 Ollama/LocalAI 等 OpenAI 兼容端点。
    # 将 economy_providers 配为 "local,qwen,glm" 即可让低成本档优先走本地，
    # 数据不出现场、token 成本归零。未配置 key 时自动跳过（不 mock）。
    local_llm_api_key: str = ""            # 本地端点可留空（多数本地服务无鉴权）
    local_llm_api_base: str = "http://localhost:11434/v1"
    local_llm_model: str = "qwen2.5:7b"

    # ── B2B 装企交付（v1.4.x，借鉴"卖结果不卖功能"交付式产品）──
    # POST /api/b2b/delivery：输入户型/面积/风格/预算 → 整包返回
    # 设计方案 + 报价 + 施工计划（纯编排、只读、不落库）
    b2b_delivery_enabled: bool = True

    # ── DSPy prompt 优化（借鉴 dspy_optimization_service）──
    # 启用后 DesignerAgent/BudgetAgent prompt 经 ChainOfThought 优化
    dspy_enabled: bool = False  # 默认关闭，需安装 dspy 依赖

    # ── A2A 协议（借鉴 Google A2A v1.0）──
    # 启用后 /api/a2a/* 端点可用，发布 Agent Card + Task Machine
    a2a_enabled: bool = True

    # ── PII 全量脱敏（借鉴 pii_masking）──
    # 启用后 audit_log details + agent trace 自动脱敏 8 类 PII
    pii_masking_enabled: bool = True

    # ── TTS 输出链（借鉴 tts_chain 三级降级）──
    # 启用后 /api/voice/tts 端点可用，支持 Qwen3-TTS → CosyVoice → Doubao
    tts_enabled: bool = True
    tts_provider_priority: str = "qwen3_tts,cosyvoice,doubao"

    # ════════════════════════════════════════════════════════════════
    # v1.1.29 家居补短：合规 + 主动干预 + 微服务 + A2UI
    # ════════════════════════════════════════════════════════════════

    # ── 审计 HMAC-SHA256 防篡改签名 ──
    # 启用后 audit_log 写入时自动附加 HMAC 签名，支持完整性校验
    audit_hmac_enabled: bool = True

    # ── 施工健康 OS 主动干预 ──
    # 启用后 HealthMonitor 定时巡检项目进度，异常时自动创建预警 + 推送通知
    health_os_enabled: bool = True
    health_os_check_interval_seconds: int = 3600  # 巡检间隔（秒）

    # ── 推送通道 ──
    # 启用后 push_sender 可通过 FCM/APNs/WebPush 发送推送通知
    push_enabled: bool = True
    # 推送提供商（规划中，逗号分隔优先级）：fcm, apns, webpush, sms
    # 当前为 mock 模式，所有推送走 _send_to_device mock 路径
    push_provider: str = ""

    # ── A2UI 协议 ──
    # 启用后 Agent 回复可输出 A2UI JSON 卡片（Flutter/Web 端渲染）
    a2ui_enabled: bool = True

    # ── 装修知识库 ──
    # 启用后 Agent RAG 可检索结构化装修知识库（材质/工艺/标准/FAQ）
    knowledge_base_enabled: bool = True
    knowledge_base_path: str = "knowledge"

    # ── 部署形态（模块化单体）──
    # v1.2.2 架构澄清：本项目为模块化单体（modular monolith），所有路由在 app/main.py
    # 中无条件 include_router 加载，无按角色拆分的微服务进程。早期 v1.1.29 设想的
    # "SERVICE_ROLE 微服务模式"从未落地（无对应的条件路由加载代码），为避免架构误导，
    # 此处保留字段仅为向后兼容（feature-flags 接口仍返回），取值固定为空字符串。
    # 如未来确需拆分服务，应基于独立仓库 + 消息总线重新设计，而非复用本字段。
    service_role: str = ""

    # ── Matter 智能家居协议桥接（A7）──
    # 启用后 /api/smart-home/matter/* 端点可用，支持 Matter 2.0 设备配网与管理
    # 需配合 BridgeFactory + MatterBridge 使用（当前为 stub, 标注 TODO: need API key）
    matter_enabled: bool = True

    # ── A1 智能家居能耗监测（v1.2.2）──
    # 启用后 /api/energy/* 端点可用，支持能耗记录、报告生成、节能建议
    energy_monitor_enabled: bool = True

    # ── A2 智能家居健康监测系统（v1.2.0）──
    # 启用后 /api/health-monitor/* 端点可用，支持健康监测记录 + 空气质量监控
    health_monitor_enabled: bool = True

    # ── A5 采购交付透明度 ──
    # 启用后 /api/procurement/orders/{order_id}/delivery 等端点可使用
    delivery_tracking_enabled: bool = True

    # ── A6 施工预测性维护 ──
    # 启用后 /api/construction/predictive-analysis 等端点可使用
    predictive_maintenance_enabled: bool = True

    # ── A4 预测式智能场景推荐（v1.2.2）──
    # 启用后 /api/scene-automation/scenes/behaviors 和 /scenes/predictions/* 端点可用
    # 基于用户行为日志（时间模式/设备转换/环境数据）生成场景预测
    predictive_scene_enabled: bool = True

    # ── 事件总线编排（v1.2.2）──
    # 启用后应用启动时注册跨模块事件编排规则，实现服务间松耦合通信
    # 关闭时 EventBus 仍可被各服务直接调用 emit()，但不注册内置编排规则
    integration_event_bus_enabled: bool = True

    # ════════════════════════════════════════════════════════════════
    # v1.2.0 家装专业性提升（诊断报告 2026-07-23）
    # 解决 P1-P5：AI渲染stub / 设计-BOM-报价断链 / IFC坐标造假 / 施工图缺失 / CAD非参数化
    # 所有改动配套 feature flag 可回滚，默认 False 灰度，验证后开启
    # ════════════════════════════════════════════════════════════════

    # ── S1/S2: 正向设计算量（floorplan.data 作 SSOT，takeoff 从几何派生）──
    # 启用后 /takeoff/project/{project_id} 从 active floorplan 几何自动算工程量
    # 关闭时回退到原 /takeoff/wall 手工输入端点
    forward_takeoff_enabled: bool = True

    # ── S1: BOM 从 floorplan 几何派生（增强 generate_bom_for_project）──
    # 启用后 generate_bom 优先从 floorplan.data 几何派生，无 floorplan 时回退到 Room 表
    bom_from_geometry_enabled: bool = True

    # ── S5: 定额库定价（v1.1.31 FP-6 修复）──
    # 启用后 generate_budget_from_bom 用 BOM量 × 定额单价（app.standards.quota_library
    # 按 category_code × tier 查询），定额缺失回退 BOMItem.total_price；
    # 关闭时直接用 BOMItem.total_price（原行为）。
    # v1.2.1 修复：原 budget_service 引用本 flag 但 config 未声明，致 AttributeError。
    quota_library_enabled: bool = True

    # ── S3: AI 渲染去 stub（接入真实 ControlNet 几何锁定 / 诚实降级）──
    # 启用后 ai_render_service 走真实渲染后端；关闭或后端不可用时诚实降级到 mock（不再伪造参数）
    real_ai_render_enabled: bool = False  # 默认关闭，需配置渲染后端 URL
    ai_render_backend_url: str = ""  # 渲染后端地址（如 http://localhost:7860 或第三方 API）
    # v1.3.0 P3: AI 渲染接入契约固化（ControlNet + Depth Anything V2 + SDXL-Turbo）
    # 后端类型：controlnet（几何锁定，对标 2026 行业强制）/ sdxl_turbo（15s 快速预览，95% 空间准确度）/ mock
    ai_render_backend_type: str = "controlnet"
    # 契约严格模式：True 时客户端 require_real=True 且后端不可用 → 503 诚实报错（不走占位图）
    ai_render_contract_strict: bool = True

    # ── S4: IFC 真实坐标 + Pset 属性集 + 门窗洞口扣减 ──
    # 启用后 ifc_export 用 floorplan 真实坐标放置构件，附加 Pset_WallCommon 等
    ifc_real_placement_enabled: bool = True
    # v1.3.0 P4: H-IFC 扩展（湖北 BIM 应用导则：视点/漫游/地理位置数据字段）
    # 启用后 IfcSite 附加 RefLatitude/RefLongitude + Pset_HIFCExtension，默认关闭灰度
    ifc_h_ifc_extension_enabled: bool = False

    # ── S5: 施工图自动生成（模型即图纸，floorplan 变 → 图纸重生成）──
    # 启用后 /api/construction-drawing/* 端点可用，生成 SVG 平/立/剖面图
    construction_drawing_enabled: bool = True
    # v1.3.0 P4: 施工图 MEP 图示占位（给排水/电气管线走向标注）
    construction_drawing_mep_enabled: bool = False

    # ════════════════════════════════════════════════════════════════
    # v1.5.0 需求补充落地（PRD v3.1 F41-F47, 2026-08-03 行业调研）
    # 存量焕新（适老/局部焕新）+ 信任合规（资金托管/环保标签）+ AI 决策（方案前置/生态桥接/问答搜索）
    # ════════════════════════════════════════════════════════════════

    # ── F41 适老改造（适老卫浴/无障碍动线/适老智能设备）──
    elderly_adaptation_enabled: bool = True

    # ── F42 局部焕新模式（厨卫焕新/墙面刷新/单空间短周期改造）──
    partial_renovation_enabled: bool = True

    # ── F43 资金托管深化（escrow 对接银行存管/第三方监管，节点验收双向确认放款）──
    escrow_trustee_enabled: bool = True

    # ── F44 环保材料库标签（材料 SKU 增加 ENF/E0 环保等级与绿色认证筛选）──
    eco_material_label_enabled: bool = True

    # ── F45 方案前置决策（上传户型 → AI 先出 3 套方案 + 预算区间）──
    solution_first_enabled: bool = True

    # ── F46 生态桥接优先级（优先落地 1-2 个主流生态真实联动，其余 stub 诚实标注）──
    ecosystem_bridge_priority_enabled: bool = True

    # ── F47 AI 装修问答/案例搜索（AgenticRAG + 案例库，带引用来源）──
    ai_qa_search_enabled: bool = True

    # ── S6: 2D CAD 参数化升级（画线即建墙，写入 floorplan.data）──
    # 启用后 cad_page DrawingElement 升级为 BIM 构件（带厚度/材质/层高）
    parametric_cad_enabled: bool = True

    # ── S7-S9: 空间智能三能力（对标飞流 AI 3.0，中长期布局）──
    spatial_perception_enabled: bool = False   # 户型结构/承重/管线识别
    spatial_reasoning_enabled: bool = False    # 设计错误规避规则引擎
    spatial_interaction_enabled: bool = False   # 设计→施工指令→采购多角色协同

    # ── Sketch-to-3D 视觉识别（v1.2.0）──
    # 启用后 /api/sketch-to-3d/analyze 使用多模态视觉模型（DeepSeek/GLM/Qwen）分析手绘草图
    # 关闭时返回占位结果（confidence=0, mode="feature_disabled"）
    sketch_to_3d_vision_enabled: bool = True

    # ── F38 质检缺陷识别真实 CV（多模态视觉 LLM）──
    # 启用后 QAInspectorAgent.detect_defects / compare_with_design 调用
    # 多模态视觉模型（DeepSeek/GLM/Qwen 优先，复用 LLM fallback 供应商）分析现场照片，
    # 输出结构化缺陷列表（类型/位置/置信度/建议）。
    # 默认 True：配置视觉 key 时走真实 CV（cv_mode="real_vision_llm"）；
    # 未配置任何视觉 key 时 _call_vision_llm 抛 RuntimeError → 诚实降级 hash mock
    # （cv_mode="mock" + note 标注），禁止伪装真实视觉能力。
    real_cv_quality_enabled: bool = True

    # ── Web 控制台 v2（React+Vite，对齐移动端 UI/UX）──
    # 启用后 Nginx /console/* 入口对外可见；前端经 /api/config/feature-flags 读取
    # 关闭时回退旧静态页（workbench.html 等 18 页保留作回滚资产）
    console_v2_enabled: bool = False

    # v1.2.9 Workbench 上下文自适应建议（GenUI-lite：按时段/角色重排快捷输入）
    # 关闭时回退静态 SUGGESTIONS 常量
    workbench_adaptive_suggestions_enabled: bool = False

    # ── 项目全链路编排（事件总线接线）──
    # 启用后 5 处业务点发射 PROJECT_CREATED / BOM_GENERATED / MATERIAL_DELIVERED /
    # INSPECTION_PASSED / CHANGE_ORDER_APPROVED 事件，触发跨模块编排规则
    # （自动建预算 / 自动采购建议 / 任务就绪推进 / 后继任务链推进 / 预算更新）。
    # 关闭时发射函数 no-op，零回归；procurement_service 保留原直接 task-ready 逻辑。
    # 状态机校验与 accept 端点独立于此 flag（属 bugfix，不受 flag 控制）。
    lifecycle_orchestration_enabled: bool = False

    # ── 验收报告标准清单比对（quality_service.generate_acceptance_report）──
    # True=完整比对标准验收清单 + 实际 QualityIssue；False=仅汇总 issue（回退）
    acceptance_checklist_enabled: bool = True

    # ════════════════════════════════════════════════════════════════
    # v1.6.0 平台商业运营 Agent（借鉴 Polsia 9 大智能体 + 义乌「AI 嵌入生意每一环」模式）
    # 平台自身获客/增长/营销/竞品/财务对账，区别于面向用户交付的执行型 Agent。
    # 默认 False 灰度，验证后开启（遵循长线技术决策 feature flag 约束）。
    # ════════════════════════════════════════════════════════════════

    # ── P0 功能使用率周报 + Agent 调用统计（GrowthAgent）──
    # 启用后 GrowthAgent.generate_weekly_report 基于 agent_feedbacks 表生成周报；
    # 关闭时返回 enabled=False 提示。
    growth_agent_enabled: bool = False

    # ── P1 多渠道推广素材生成（MarketingAgent）──
    # 启用后 MarketingAgent.generate_content 生成小红书/抖音/朋友圈素材草稿；
    # 诚实标注 AI 生成草稿需人工审核。
    marketing_agent_enabled: bool = False

    # ── P1 竞品调研（CompetitorResearchAgent）──
    # 启用后基于 LLM 公开知识生成竞品调研简报；诚实标注非实时数据。
    competitor_research_agent_enabled: bool = False

    # ── P1 平台财务对账（FinanceReconAgent，区别于 settlement 工程结算）──
    # 启用后基于 payment/escrow 表统计平台抽成收入；无 Stripe/广告平台对接时诚实标注。
    finance_recon_agent_enabled: bool = False

    # ── P2 主动 Orchestrator 定时调度 + 运营日报 ──
    # 启用后 OrchestratorAgent.generate_daily_briefing 生成每日运营简报；
    # FC 定时触发器调用 /api/admin/daily-briefing 端点（无 K8s/Cron）。
    # v1.13.2 起默认开启（内部能力，子 Agent 未启用时 best-effort 降级标注）。
    business_ops_orchestrator_enabled: bool = True

    # ── P3 供应链以销定产（designer BOM → procurement 反向驱动）──
    # 启用后 procurement_service.drive_procurement_from_bom 从 BOM 反向驱动采购建议；
    # 关闭时 procurement 保留原直接 task-ready 逻辑。
    # v1.13.2 起默认开启（复用 generate_from_bom 基座，零回归）。
    procurement_demand_driven_enabled: bool = True

    # ════════════════════════════════════════════════════════════════
    # v1.9.0 前沿研究 2026 第二轮落地（docs/superpowers/specs/2026-08-05-frontier-research.md）
    # 均为可回滚 feature flag，默认 False 灰度，验证后开启。
    # ════════════════════════════════════════════════════════════════

    # ── P0 AI 生成内容标识（《人工智能生成合成内容标识办法》合规）──
    # 启用后 AI 渲染/效果图/报告输出管道补显式标识 + 元数据隐式标识（水印字段预埋）；
    # 关闭时保持原输出不变（零回归）。
    # v1.13.2 起默认开启（合规能力，关闭即回退零回归）。
    ai_content_labeling_enabled: bool = True

    # ── 高 MCP 安全硬化（2026 MCP 工具投毒/SSRF 防御）──
    # 启用后 agent_tool_registry 执行工具时：description 防投毒校验、URL 抓取
    # SSRF 拦截（内网/云元数据 169.254.169.254 等）、工具输出敏感字段清洗。
    # 关闭时保持原执行路径（零回归）。
    # v1.12.x：默认开启（OWASP Agentic Skills AG1/AG4 对照——内置工具描述均
    # 通过防投毒校验，开启无回归；见 scripts/verify_self_evolution.py 回归）。
    mcp_security_hardening_enabled: bool = True

    # ── 高 OTel GenAI SemConv 埋点对齐（MCP SEP-414 W3C Trace + OTel）──
    # 启用后 AgentTrace._meta 写入 traceparent/tracestate/baggage，
    # span 按 gen_ai.system/model/tool.name/usage.* 语义约定标注。
    # 关闭时保持原 AgentTrace 结构（零回归）。
    otel_genai_semconv_enabled: bool = False

    # ── 高 GB/Z 185 智能体身份码/ACDL 预研（元数据预埋，不硬接）──
    # 启用后 /api/agents/identity/{name} 可查询 28 位 AID 身份码 + ACDL 能力描述；
    # 关闭时端点返回 404（零回归）。
    # v1.13.2 起默认开启（身份卡为只读查询，无外部依赖）。
    gbz185_agent_card_enabled: bool = True

    # ── 中 Matter/GB-T 46456 智能家居协议兼容矩阵校验 ──
    # 启用后 smart_home 设备补协议兼容矩阵（Matter/OneConnect/GB-T 46456 物模型）；
    # 关闭时保持原协议判断（零回归）。
    smart_protocol_compliance_enabled: bool = False

    # ── 中 商业运营 Agent 记忆冲突门控（防记忆漂移/投毒）──
    # 启用后 save_memory 检测新旧值冲突时返回 conflict 标记，不静默覆盖；
    # 关闭时保持原 upsert 行为（零回归）。
    memory_conflict_gate_enabled: bool = False


@lru_cache
def get_settings() -> Settings:
    return Settings()

from functools import lru_cache

from pydantic import model_validator
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    model_config = {"env_file": ".env", "env_file_encoding": "utf-8", "extra": "allow"}

    @model_validator(mode="after")
    def _validate_paseto_key(self):
        if not self.debug and self.paseto_secret_key == "change-me-to-a-random-32-byte-key-minimum":
            raise ValueError("PASETO_SECRET_KEY 不能使用默认值。请在 .env 中设置强密钥。")
        if len(self.paseto_secret_key.encode()) < 32:
            raise ValueError("PASETO_SECRET_KEY 长度不足 32 字节。")
        return self

    app_name: str = "i-home.life"
    app_version: str = "1.1.29"
    debug: bool = True

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

    paseto_secret_key: str = "change-me-to-a-random-32-byte-key-minimum"
    paseto_token_expire_minutes: int = 60 * 24

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
    qwen_audio_ws_url: str = "wss://dashscope.aliyuncs.com/api-ws/v1/realtime"  # 百炼 WebSocket
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

    # ── Agent FunctionCall / MCP ──
    agent_function_call_enabled: bool = True           # 是否启用 FunctionCall
    agent_function_call_max_rounds: int = 5            # 单次对话最大工具调用轮数
    # MCP 工具服务器地址 (留空则仅使用内置工具)
    agent_mcp_server_url: str = ""

    # ── MCP Server 暴露（v1.1.12 新增）──
    # 启用后 /api/mcp/* 端点可用，外部 AI 客户端（Claude/Cursor/小艺）可调用 Agent 工具
    # 兼容 MCP 2026-07-28 stateless 核心，支持 Nginx round-robin 负载均衡
    mcp_enabled: bool = True

    # ── AI 渲染（v1.1.12 新增，PRD §7.x）──
    # 启用后 /api/ai-render/* 端点可用，支持 2D 效果图 / 3D 场景 / 照片重布置
    # 复用 BaseAgent._chat() 调用 LLM，注入 L4 偏好示例
    ai_render_enabled: bool = True

    # ── 语音情绪路由（v1.1.12 新增）──
    # 启用后在 _route_voice_to_agent 中根据用户情绪（anxious/angry/sad/tired/excited/happy）
    # 注入系统指令前缀，调整 Agent 语气
    # 需配合 voice_emotion_detection=True 使用
    voice_emotion_routing_enabled: bool = True

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

    # ── 在线进化闭环（v1.2.0）──
    # 轨迹驱动的 Agent 自我改进：收集执行轨迹 → 分析失败模式 → 优化 prompt/降级策略
    agent_evolution_enabled: bool = True
    agent_evolution_trace_min_samples: int = 20  # 最小轨迹样本数

    # ── API 速率限制（v1.2.1）──
    # 基于内存滑动窗口，按 IP 限流；认证端点独立配额防暴力破解
    rate_limit_enabled: bool = True              # 全局开关，关闭时直接放行
    rate_limit_per_minute: int = 60              # 普通 API：每 IP 每分钟 60 次
    rate_limit_auth_per_minute: int = 10         # 认证端点（/login、/register）：每 IP 每分钟 10 次

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

    # Qwen (阿里云百炼 / DashScope) — fallback chain 第二档
    qwen_api_key: str = ""
    qwen_api_base: str = "https://dashscope.aliyuncs.com/compatible-mode/v1"
    qwen_model: str = "qwen-plus"

    # Doubao (火山引擎 ARK) — fallback chain 末端
    doubao_api_key: str = ""
    doubao_api_base: str = "https://ark.cn-beijing.volces.com/api/v3"
    doubao_model: str = "doubao-seed-1-6-250615"

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

    # ── A2UI 协议 ──
    # 启用后 Agent 回复可输出 A2UI JSON 卡片（Flutter/Web 端渲染）
    a2ui_enabled: bool = True

    # ── 装修知识库 ──
    # 启用后 Agent RAG 可检索结构化装修知识库（材质/工艺/标准/FAQ）
    knowledge_base_enabled: bool = True
    knowledge_base_path: str = "knowledge"

    # ── 微服务模式 ──
    # 启用后启动时根据 SERVICE_ROLE 环境变量仅加载对应路由
    # 取值: auth-gateway / agent-orchestrator / design-render / project-flow / commerce / realtime
    # 留空则保持单体模式（默认）
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


@lru_cache
def get_settings() -> Settings:
    return Settings()

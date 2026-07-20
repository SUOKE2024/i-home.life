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
    app_version: str = "1.1.18"
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
    webauthn_rp_id: str = "localhost"
    webauthn_origin: str = "http://localhost:8766"
    webauthn_challenge_ttl: int = 120

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


@lru_cache
def get_settings() -> Settings:
    return Settings()

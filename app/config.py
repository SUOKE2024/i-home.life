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
    app_version: str = "1.1.0"
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
    voice_vad_threshold: float = 0.5                   # VAD 阈值 (0-1)
    voice_max_recording_seconds: int = 300             # 单次最大录音时长（秒）

    # ── Agent FunctionCall / MCP ──
    agent_function_call_enabled: bool = True           # 是否启用 FunctionCall
    agent_function_call_max_rounds: int = 5            # 单次对话最大工具调用轮数
    # MCP 工具服务器地址 (留空则仅使用内置工具)
    agent_mcp_server_url: str = ""

    cors_origins: list[str] = ["http://localhost:3000", "http://localhost:5173"]

    amap_api_key: str = ""  # 高德地图 Web API Key

    # 第三方身份核验
    aliyun_id_verify_appcode: str = ""  # 阿里云身份证实名认证 AppCode


@lru_cache
def get_settings() -> Settings:
    return Settings()

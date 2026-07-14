from functools import lru_cache

from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    model_config = {"env_file": ".env", "env_file_encoding": "utf-8", "extra": "allow"}

    app_name: str = "i-home.life"
    app_version: str = "1.0.0"
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
    # RP (Relying Party) ID: 生产环境应设置为域名，如 "i-home.life"
    webauthn_rp_id: str = "localhost"
    # Origin: 客户端来源，开发环境通常为 http://localhost:PORT
    # 生产环境为 https://i-home.life
    webauthn_origin: str = "http://localhost:8766"

    def validate_paseto_key(self):
        if not self.debug and self.paseto_secret_key == "change-me-to-a-random-32-byte-key-minimum":
            raise RuntimeError("PASETO_SECRET_KEY 不能使用默认值。请在 .env 中设置强密钥。")
        if len(self.paseto_secret_key.encode()) < 32:
            raise RuntimeError(f"PASETO_SECRET_KEY 长度不足 32 字节。")

    # DeepSeek V4
    deepseek_api_key: str = ""
    deepseek_api_base: str = "https://api.deepseek.com"
    deepseek_model: str = "deepseek-chat"

    # GLM-5.2 (智谱 AI)
    glm_api_key: str = ""
    glm_api_base: str = "https://open.bigmodel.cn/api/paas/v4"
    glm_model: str = "glm-4-plus"

    cors_origins: list[str] = ["http://localhost:3000", "http://localhost:5173"]

    amap_api_key: str = ""  # 高德地图 Web API Key

    # 第三方身份核验
    aliyun_id_verify_appcode: str = ""  # 阿里云身份证实名认证 AppCode


@lru_cache
def get_settings() -> Settings:
    return Settings()

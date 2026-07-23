import os
import sys

# 在导入 app 模块前设置测试数据库 URL，确保 engine 使用测试数据库
# 使用 PID 隔离，避免并发测试运行时 SQLite 文件锁定
os.environ["DATABASE_URL"] = f"sqlite+aiosqlite:///./data/test_{os.getpid()}.db"

# 禁用 Qwen-Audio API Key，强制语音测试走 mock 模式
# 避免测试中建立真实 WebSocket 连接导致缓慢（~5-7s/test）
os.environ["QWEN_AUDIO_API_KEY"] = ""

# 禁用 DeepSeek API Key，强制 voice agent 测试走 fallback/mock 模式
# 避免真实 LLM 调用导致超时（deepseek-v4-pro 单次调用 60-90s，pytest timeout=60s）
os.environ["DEEPSEEK_API_KEY"] = ""

# 默认禁用 API 速率限制，避免现有测试因共享 IP 配额耗尽而误失败
# test_rate_limit.py 通过 monkeypatch 显式启用限流
os.environ["RATE_LIMIT_ENABLED"] = "false"

# v1.2.1 P0-1/P1-8：测试环境 PASETO 与会话加密隔离。
# conftest 不依赖 .env（CI/fresh clone 无 .env），故显式提供：
# - PASETO_SECRET_KEY：合法 32+ 字节测试密钥，使 strict_mode 校验通过
# - PASETO_STRICT_MODE=false：放宽校验，避免任何密钥边缘条件阻断测试
# - ALLOW_PLAINTEXT_SESSION=true：Agent 会话测试关注业务逻辑而非加密，
#   显式允许明文降级（生产禁止）。相关行为由专门的单测覆盖。
os.environ.setdefault("PASETO_SECRET_KEY", "test-paseto-key-for-pytest-32-bytes!!")
os.environ.setdefault("PASETO_STRICT_MODE", "false")
os.environ.setdefault("ALLOW_PLAINTEXT_SESSION", "true")

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import pytest  # noqa: F401, E402
import pytest_asyncio  # noqa: E402
from httpx import ASGITransport, AsyncClient  # noqa: E402

from app.config import get_settings  # noqa: F401, E402
from app.database import async_session, init_db, Base, engine  # noqa: F401, E402
from app.main import app  # noqa: E402
from app.services.cache_service import cache  # noqa: E402
from app.models import (  # noqa: F401, E402
    User, Project, Floor, Room,
    MaterialCategory, Material, BOMItem,
)


@pytest_asyncio.fixture(autouse=True)
async def setup_db():
    """每个测试前: drop_all(checkfirst=True) + create_all — 不删除文件

    v1.1.12: 同时清理 _schema_migrations 元数据表，避免 skip 机制跨测试污染
    （Base.metadata.drop_all 不会清理手动创建的 _schema_migrations 表）。
    v1.1.27: 同时清理缓存单例的内存 dict，避免热点端点缓存跨测试污染
    （mat:categories 等全局 key 在 xdist 同 worker 内跨测试残留）。
    """
    cache._memory.clear()  # v1.1.27: 清理缓存防跨测试污染
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all, checkfirst=True)
        # 清理 v1.1.12 迁移版本标记表，避免后续测试触发 skip 机制
        from sqlalchemy import text
        await conn.execute(text("DROP TABLE IF EXISTS _schema_migrations"))
        await conn.run_sync(Base.metadata.create_all)
    yield
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all, checkfirst=True)


@pytest_asyncio.fixture
async def client():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac


@pytest_asyncio.fixture
async def db_session():
    async with async_session() as session:
        yield session


@pytest_asyncio.fixture
async def auth_token(client: AsyncClient) -> str:
    """注册一个用户并返回 access_token，供测试文件直接依赖。

    各测试文件无需重复定义 _register() / _register_and_login() 私有函数。
    使用 UUID 生成唯一手机号，避免并发测试冲突。
    """
    import uuid
    phone = f"139{str(uuid.uuid4().int)[:8]}"
    resp = await client.post(
        "/api/auth/register",
        json={"phone": phone, "name": "测试用户", "password": "test123456"},
    )
    assert resp.status_code == 201, f"注册失败: {resp.json()}"
    return resp.json()["access_token"]


@pytest_asyncio.fixture
async def auth_headers(auth_token: str) -> dict:
    """返回已认证的 Authorization headers，可直接用于 HTTP 请求。"""
    return {"Authorization": f"Bearer {auth_token}"}

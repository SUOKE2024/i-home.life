import os
import sys

# 在导入 app 模块前设置测试数据库 URL，确保 engine 使用测试数据库
# 使用 PID 隔离，避免并发测试运行时 SQLite 文件锁定
os.environ["DATABASE_URL"] = f"sqlite+aiosqlite:///./data/test_{os.getpid()}.db"

# 禁用 Qwen-Audio API Key，强制语音测试走 mock 模式
# 避免测试中建立真实 WebSocket 连接导致缓慢（~5-7s/test）
os.environ["QWEN_AUDIO_API_KEY"] = ""

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import pytest  # noqa: F401, E402
import pytest_asyncio  # noqa: E402
from httpx import ASGITransport, AsyncClient  # noqa: E402

from app.config import get_settings  # noqa: F401, E402
from app.database import async_session, init_db, Base, engine  # noqa: F401, E402
from app.main import app  # noqa: E402
from app.models import (  # noqa: F401, E402
    User, Project, Floor, Room,
    MaterialCategory, Material, BOMItem,
)


@pytest_asyncio.fixture(autouse=True)
async def setup_db():
    """每个测试前: drop_all(checkfirst=True) + create_all — 不删除文件"""
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all, checkfirst=True)
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

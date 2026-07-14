import asyncio
import os
import sys

# 在导入 app 模块前设置测试数据库 URL，确保 engine 使用测试数据库
# 使用 PID 隔离，避免并发测试运行时 SQLite 文件锁定
os.environ["DATABASE_URL"] = f"sqlite+aiosqlite:///./data/test_{os.getpid()}.db"

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient

from app.config import get_settings
from app.database import async_session, init_db, Base, engine
from app.main import app
from app.models import User, Project, Floor, Room, MaterialCategory, Material, BOMItem


@pytest_asyncio.fixture(scope="session")
def event_loop():
    loop = asyncio.new_event_loop()
    yield loop
    loop.close()


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

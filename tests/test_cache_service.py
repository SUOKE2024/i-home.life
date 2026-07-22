"""缓存服务单元测试 — 覆盖 cache_service.py 全部核心 API。

测试矩阵:
    - set / get / delete 基本操作
    - TTL 过期
    - incr 原子计数器
    - delete_pattern 批量删除
    - exists / touch
    - 内存模式降级（默认开发环境，Redis 未配置时走内存）
"""
import time

import pytest

from app.services.cache_service import CacheService


@pytest.fixture
def cache_service():
    """每次测试前获取新的缓存实例（内存模式，开发环境隔离）。"""
    svc = CacheService()
    # 清理可能残留的 key
    svc._memory.clear()
    return svc


class TestCacheServiceBasic:
    """基本 CRUD 操作测试。"""

    @pytest.mark.asyncio
    async def test_set_and_get_string(self, cache_service):
        await cache_service.set("test_key", "hello", ttl=60)
        val = await cache_service.get("test_key")
        assert val == "hello"

    @pytest.mark.asyncio
    async def test_set_and_get_dict(self, cache_service):
        await cache_service.set("test_dict", {"a": 1, "b": [2, 3]}, ttl=60)
        val = await cache_service.get("test_dict")
        assert val == {"a": 1, "b": [2, 3]}

    @pytest.mark.asyncio
    async def test_get_nonexistent(self, cache_service):
        val = await cache_service.get("nonexistent_key")
        assert val is None

    @pytest.mark.asyncio
    async def test_delete(self, cache_service):
        await cache_service.set("del_key", "value", ttl=60)
        await cache_service.delete("del_key")
        assert await cache_service.get("del_key") is None

    @pytest.mark.asyncio
    async def test_delete_nonexistent(self, cache_service):
        # 不应抛出异常
        await cache_service.delete("nonexistent_key")

    @pytest.mark.asyncio
    async def test_exists(self, cache_service):
        await cache_service.set("exists_key", "yes", ttl=60)
        assert await cache_service.exists("exists_key") is True
        assert await cache_service.exists("no_key") is False

    @pytest.mark.asyncio
    async def test_override_key(self, cache_service):
        await cache_service.set("override", "first", ttl=60)
        await cache_service.set("override", "second", ttl=60)
        assert await cache_service.get("override") == "second"


class TestCacheServiceTTL:
    """TTL 过期测试。"""

    @pytest.mark.asyncio
    async def test_ttl_expired(self, cache_service):
        await cache_service.set("short_ttl", "data", ttl=0)
        # 在 set 和 get 之间允许微小时间差
        cache_service._memory["short_ttl"] = ("data", time.time() - 1)
        val = await cache_service.get("short_ttl")
        assert val is None

    @pytest.mark.asyncio
    async def test_ttl_still_valid(self, cache_service):
        await cache_service.set("long_ttl", "data", ttl=3600)
        val = await cache_service.get("long_ttl")
        assert val == "data"

    @pytest.mark.asyncio
    async def test_touch_extend_ttl(self, cache_service):
        await cache_service.set("touch_key", "data", ttl=1)
        # 延长 TTL
        assert await cache_service.touch("touch_key", ttl=3600) is True
        val = await cache_service.get("touch_key")
        assert val == "data"

    @pytest.mark.asyncio
    async def test_touch_nonexistent(self, cache_service):
        assert await cache_service.touch("no_key", ttl=60) is False


class TestCacheServiceIncr:
    """原子计数器测试。"""

    @pytest.mark.asyncio
    async def test_incr_first_call(self, cache_service):
        val = await cache_service.incr("counter", 1, 60)
        assert val == 1

    @pytest.mark.asyncio
    async def test_incr_multiple(self, cache_service):
        await cache_service.incr("counter2", 1, 60)
        v2 = await cache_service.incr("counter2", 1, 60)
        v3 = await cache_service.incr("counter2", 2, 60)
        assert v2 == 2
        assert v3 == 4

    @pytest.mark.asyncio
    async def test_incr_expires(self, cache_service):
        await cache_service.incr("expire_counter", 1, ttl=0)
        # 手动设过期
        cache_service._memory["expire_counter"] = (5, time.time() - 1)
        # 过期后重新创建
        val = await cache_service.incr("expire_counter", 1, 60)
        assert val == 1


class TestCacheServicePattern:
    """批量删除测试。"""

    @pytest.mark.asyncio
    async def test_delete_pattern(self, cache_service):
        await cache_service.set("user:1", "alice", ttl=60)
        await cache_service.set("user:2", "bob", ttl=60)
        await cache_service.set("product:1", "widget", ttl=60)
        count = await cache_service.delete_pattern("user:*")
        assert count == 2
        assert await cache_service.get("user:1") is None
        assert await cache_service.get("user:2") is None
        assert await cache_service.get("product:1") == "widget"

    @pytest.mark.asyncio
    async def test_delete_pattern_no_match(self, cache_service):
        count = await cache_service.delete_pattern("nonexistent:*")
        assert count == 0


class TestCacheServiceBackend:
    """后端标识测试。"""

    def test_default_backend_is_memory(self, cache_service):
        # 开发环境默认 memory 模式
        assert cache_service.backend == "memory"

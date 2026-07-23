"""Redis 缓存服务 — 统一缓存抽象层。

生产环境使用 Redis（支持分布式多 worker），
开发/测试环境降级为内存 dict（无需额外依赖）。

使用方式:
    from app.services.cache_service import cache

    # 写入缓存 (TTL 单位: 秒)
    await cache.set("key", value, ttl=300)

    # 读取缓存
    value = await cache.get("key")

    # 删除缓存
    await cache.delete("key")

    # 批量删除 (按前缀)
    await cache.delete_pattern("material:*")

    # 检查是否存在
    exists = await cache.exists("key")

特性:
    - 自动 JSON 序列化/反序列化（非 str/bytes 值）
    - TTL 支持（精确到秒）
    - Redis 不可用时自动降级到内存模式
    - 连接池复用，避免 TCP 频繁创建
"""

from __future__ import annotations

import asyncio
import json
import time
from typing import Any, Optional

import structlog

logger = structlog.get_logger("ihome.cache")

# ── 内存降级模式最大条目数 ──
_MAX_MEMORY_ENTRIES = 10_000

# ── Redis 连接池（延迟初始化）──
_redis_pool: Any = None  # redis.asyncio.ConnectionPool | None


async def _get_redis():
    """获取 Redis 客户端实例（单例连接池，延迟连接）。"""
    global _redis_pool
    if _redis_pool is not None:
        try:
            import redis.asyncio as aioredis
            return aioredis.Redis(connection_pool=_redis_pool)
        except ImportError:
            return None

    from app.config import get_settings
    settings = get_settings()
    if not settings.redis_url:
        return None

    try:
        import redis.asyncio as aioredis
        _redis_pool = aioredis.ConnectionPool.from_url(
            settings.redis_url,
            max_connections=50,
            socket_connect_timeout=3,
            socket_keepalive=True,
            retry_on_timeout=True,
            health_check_interval=30,
        )
        # 测试连接
        client = aioredis.Redis(connection_pool=_redis_pool)
        await client.ping()
        logger.info("cache_service.redis_connected", url=settings.redis_url[:30])
        return client
    except ImportError:
        logger.warning("cache_service.redis_not_installed")
        return None
    except Exception as e:
        logger.warning("cache_service.redis_connect_failed", error=str(e))
        _redis_pool = None
        return None


class CacheService:
    """缓存服务 — 优先 Redis，降级内存 dict。"""

    def __init__(self):
        self._memory: dict[str, tuple[Any, float]] = {}  # {key: (value, expires_at)}
        self._redis_client: Any = None
        self._redis_init_lock = asyncio.Lock()
        self._init_attempted = False

    async def _ensure_redis(self) -> Any:
        """延迟初始化 Redis 连接（首次调用时完成）。"""
        if self._init_attempted:
            return self._redis_client
        async with self._redis_init_lock:
            if self._init_attempted:
                return self._redis_client
            self._redis_client = await _get_redis()
            self._init_attempted = True
            return self._redis_client

    @property
    def backend(self) -> str:
        """返回当前缓存后端类型: 'redis' | 'memory'"""
        if self._redis_client is not None:
            return "redis"
        return "memory"

    async def get(self, key: str) -> Optional[Any]:
        """读取缓存值。key 不存在返回 None。"""
        redis = await self._ensure_redis()
        if redis is not None:
            try:
                raw = await redis.get(key)
                if raw is None:
                    return None
                # 尝试 JSON 反序列化
                try:
                    return json.loads(raw)
                except (json.JSONDecodeError, TypeError):
                    return raw.decode("utf-8") if isinstance(raw, bytes) else raw
            except Exception as e:
                logger.warning("cache_service.redis_get_error", key=key, error=str(e))
                return None

        # 内存模式
        if key in self._memory:
            value, expires_at = self._memory[key]
            if expires_at > time.time():
                return value
            del self._memory[key]
        return None

    async def set(self, key: str, value: Any, ttl: int = 300) -> None:
        """写入缓存值。

        Args:
            key: 缓存键
            value: 缓存值（非 str/bytes 类型会自动 JSON 序列化）
            ttl: 过期时间（秒），默认 300s
        """
        redis = await self._ensure_redis()
        if redis is not None:
            try:
                if isinstance(value, (str, bytes)):
                    await redis.setex(key, ttl, value)
                else:
                    await redis.setex(key, ttl, json.dumps(value, ensure_ascii=False, default=str))
                return
            except Exception as e:
                logger.warning("cache_service.redis_set_error", key=key, error=str(e))

        # 内存模式
        self._memory[key] = (value, time.time() + ttl)

        # 超过最大条目数时清理过期项
        if len(self._memory) > _MAX_MEMORY_ENTRIES:
            now = time.time()
            expired = [k for k, (_, t) in self._memory.items() if t <= now]
            for k in expired:
                del self._memory[k]

    async def delete(self, key: str) -> None:
        """删除缓存键。"""
        redis = await self._ensure_redis()
        if redis is not None:
            try:
                await redis.delete(key)
            except Exception as e:
                logger.warning("cache_service.redis_delete_error", key=key, error=str(e))
            return

        self._memory.pop(key, None)

    async def delete_pattern(self, pattern: str) -> int:
        """按模式批量删除缓存键。

        示例: await cache.delete_pattern("material:*")

        v1.2.1 P1-5 修复：原 redis.keys(pattern) 是 O(N) 阻塞命令，大 key 空间下
        会卡住 Redis 主线程（生产事故常见源）。改用 scan_iter（非阻塞 SCAN 游标
        迭代）分批匹配 + 分批删除，单批 200 个键，避免主线程阻塞。

        Returns:
            删除的键数量
        """
        redis = await self._ensure_redis()
        if redis is not None:
            try:
                deleted = 0
                batch: list = []
                # SCAN 非阻塞迭代，count=200 平衡往返次数与单次负载
                async for key in redis.scan_iter(match=pattern, count=200):
                    batch.append(key)
                    if len(batch) >= 200:
                        deleted += await redis.delete(*batch)
                        batch = []
                if batch:
                    deleted += await redis.delete(*batch)
                return deleted
            except Exception as e:
                logger.warning("cache_service.redis_delete_pattern_error", pattern=pattern, error=str(e))
                return 0

        # 内存模式：前缀匹配
        prefix = pattern.rstrip("*")
        to_delete = [k for k in self._memory if k.startswith(prefix)]
        for k in to_delete:
            del self._memory[k]
        return len(to_delete)

    async def exists(self, key: str) -> bool:
        """检查缓存键是否存在。"""
        redis = await self._ensure_redis()
        if redis is not None:
            try:
                return bool(await redis.exists(key))
            except Exception as e:
                logger.warning("cache_service.redis_exists_error", key=key, error=str(e))
                return False

        if key in self._memory:
            _, expires_at = self._memory[key]
            if expires_at > time.time():
                return True
            del self._memory[key]
        return False

    async def touch(self, key: str, ttl: int = 300) -> bool:
        """延长缓存键的 TTL（不修改值）。key 不存在返回 False。"""
        redis = await self._ensure_redis()
        if redis is not None:
            try:
                return bool(await redis.expire(key, ttl))
            except Exception as e:
                logger.warning("cache_service.redis_touch_error", key=key, error=str(e))
                return False

        if key in self._memory:
            value, _ = self._memory[key]
            self._memory[key] = (value, time.time() + ttl)
            return True
        return False

    async def incr(self, key: str, amount: int = 1, ttl: int = 3600) -> int:
        """原子递增计数器。首次调用自动创建并设 TTL。"""
        redis = await self._ensure_redis()
        if redis is not None:
            try:
                value = await redis.incrby(key, amount)
                # 首次创建时设置 TTL
                if value == amount:
                    await redis.expire(key, ttl)
                return value
            except Exception as e:
                logger.warning("cache_service.redis_incr_error", key=key, error=str(e))
                return 0

        # 内存模式（非原子，但单 worker 安全）
        now = time.time()
        if key in self._memory and self._memory[key][1] > now:
            value, _ = self._memory[key]
            value = int(value) + amount
        else:
            value = amount
        self._memory[key] = (value, now + ttl)
        return value

    async def close(self) -> None:
        """关闭 Redis 连接池。"""
        global _redis_pool
        if _redis_pool is not None:
            await _redis_pool.disconnect()
            _redis_pool = None
            self._redis_client = None
            self._init_attempted = False
            logger.info("cache_service.redis_closed")


# 全局单例
cache = CacheService()

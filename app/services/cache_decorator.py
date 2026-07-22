"""缓存装饰器 — 基于 cache_service 的声明式缓存。

设计要点：
- @cached(ttl, key_prefix, key_builder) 装饰 async 函数
- 命中率统计通过 Prometheus cache_hits_total / cache_misses_total Counter
- feature flag cache_decorators_enabled 控制（关闭时直透，ttl<=0 也直透）
- invalidate(*args, **kwargs) 主动失效单个 key
- invalidate_pattern() 按前缀批量失效（需 key_prefix）
- 复用 cache_service 单例，不新建缓存层

缓存安全硬约束（防跨用户数据泄露）：
- 所有缓存 key 必须含 user_id 或为公共数据
- verify_project_access 校验在缓存读取之前，不缓存鉴权结果
- 列表端点 key_builder 必须含 user_id

使用方式:
    from app.services.cache_decorator import cached

    # 基础用法
    @cached(ttl=300, key_prefix="mat:categories")
    async def get_categories(db):
        return await db.execute(...)

    # 自定义 key_builder（含 user_id 防跨用户泄露）
    def _list_key(args, kwargs):
        user_id = kwargs.get('user_id', 'anon')
        filters = kwargs.get('filters', {})
        filters_hash = hashlib.md5(json.dumps(filters, sort_keys=True).encode()).hexdigest()[:8]
        return f"furn:list:{user_id}:{filters_hash}"

    @cached(ttl=60, key_prefix="furn:list", key_builder=_list_key)
    async def list_furniture(db, user_id, filters):
        ...

    # 主动失效
    await list_furniture.invalidate(db, user_id=user_id, filters=filters)
    await list_furniture.invalidate_pattern()  # 删除所有 furn:list:*
"""
from __future__ import annotations

import functools
import hashlib
import json
from typing import Any, Callable

import structlog

from app.config import get_settings
from app.services.cache_service import cache

logger = structlog.get_logger("ihome.cache_decorator")

# 不可序列化对象的类名黑名单（DB session / engine 等）
_UNSERIALIZABLE_TYPES = frozenset({
    "AsyncSession", "Session", "AsyncEngine", "Engine",
    "AsyncConnection", "Connection",
})


def _safe_repr(obj: Any) -> str:
    """安全序列化对象为字符串（避免 DB session 等不可序列化对象）。"""
    cls_name = obj.__class__.__name__ if hasattr(obj, "__class__") else type(obj).__name__
    if cls_name in _UNSERIALIZABLE_TYPES:
        return f"<{cls_name}:{id(obj)}>"
    return str(obj)


def _default_key(fn: Callable, args: tuple, kwargs: dict) -> str:
    """默认 key 生成器：函数名 + args + kwargs 的 hash。

    DB session 等不可序列化对象用 id() 标识，避免 pickle 失败。
    注意：默认 key 不含 user_id，跨用户端点必须用自定义 key_builder。
    """
    try:
        key_data = json.dumps(
            {
                "args": [_safe_repr(a) for a in args],
                "kwargs": {k: _safe_repr(v) for k, v in sorted(kwargs.items())},
            },
            sort_keys=True, default=str, ensure_ascii=False,
        )
    except (TypeError, ValueError):
        key_data = str(args) + str(sorted(kwargs.items()))

    key_hash = hashlib.md5(key_data.encode("utf-8")).hexdigest()[:16]
    return f"{fn.__module__}.{fn.__qualname__}:{key_hash}"


def cached(
    ttl: int = 300,
    key_prefix: str = "",
    key_builder: Callable[[tuple, dict], str] | None = None,
):
    """装饰 async 函数，自动缓存返回值。

    Args:
        ttl: 缓存 TTL（秒），默认 300；ttl<=0 时直透不缓存
        key_prefix: key 前缀（如 "mat:categories"），用于 invalidate_pattern 批量失效
        key_builder: 自定义 key 生成函数，签名 (args, kwargs) -> str
                     跨用户端点必须用 key_builder 含 user_id

    Returns:
        装饰后的函数，附带:
        - .invalidate(*args, **kwargs): 主动失效单个 key
        - .invalidate_pattern(): 按前缀批量失效（需 key_prefix）

    Feature flag:
        settings.cache_decorators_enabled = False 时直透，不缓存
    """
    def decorator(fn):
        prefix = key_prefix or fn.__qualname__

        @functools.wraps(fn)
        async def wrapper(*args, **kwargs):
            settings = get_settings()
            if not settings.cache_decorators_enabled or ttl <= 0:
                return await fn(*args, **kwargs)

            # 生成 key
            base_key = key_builder(args, kwargs) if key_builder else _default_key(fn, args, kwargs)
            key = f"{prefix}:{base_key}" if key_prefix else base_key

            # 查缓存
            cached_val = await cache.get(key)
            if cached_val is not None:
                _record_hit(prefix)
                logger.debug("cache_hit", key=key)
                return cached_val

            # 未命中，执行函数
            _record_miss(prefix)
            result = await fn(*args, **kwargs)
            await cache.set(key, result, ttl=ttl)
            logger.debug("cache_miss_set", key=key, ttl=ttl)
            return result

        async def invalidate(*args, **kwargs):
            """主动失效：用相同 key_builder 计算并删除对应缓存键。"""
            base_key = key_builder(args, kwargs) if key_builder else _default_key(fn, args, kwargs)
            key = f"{prefix}:{base_key}" if key_prefix else base_key
            await cache.delete(key)
            logger.debug("cache_invalidated", key=key)

        async def invalidate_pattern():
            """按前缀批量失效（需要 key_prefix）。"""
            count = await cache.delete_pattern(f"{prefix}*")
            logger.debug("cache_pattern_invalidated", prefix=prefix, count=count)

        wrapper.invalidate = invalidate
        wrapper.invalidate_pattern = invalidate_pattern
        return wrapper
    return decorator


def _record_hit(prefix: str) -> None:
    """记录缓存命中到 Prometheus。"""
    try:
        from app.metrics import cache_hits_total
        cache_hits_total.labels(key_prefix=prefix).inc()
    except Exception:
        pass


def _record_miss(prefix: str) -> None:
    """记录缓存未命中到 Prometheus。"""
    try:
        from app.metrics import cache_misses_total
        cache_misses_total.labels(key_prefix=prefix).inc()
    except Exception:
        pass

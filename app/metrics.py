"""Prometheus 指标定义与暴露端点。

指标:
    - http_requests_total{method, path, status}: 请求总数（Counter）
    - http_request_duration_seconds{method, path}: 请求耗时（Histogram）
    - http_requests_in_progress: 进行中请求数（Gauge）
    - db_pool_size: DB 连接池大小（Gauge）
    - db_pool_checked_out: DB 当前借出连接数（Gauge）
    - db_pool_overflow: DB 溢出连接数（Gauge）
    - redis_connected: Redis 连接状态（Gauge，0/1）
    - llm_request_total{model}: LLM API 请求总数（Counter）
    - llm_request_duration_seconds{model}: LLM API 耗时（Histogram）
    - ws_connections: WebSocket 当前连接数（Gauge）
"""
from fastapi import Response
from prometheus_client import (
    CONTENT_TYPE_LATEST,
    Counter,
    Gauge,
    Histogram,
    generate_latest,
)

# ── HTTP 指标 ──
http_requests_total = Counter(
    "http_requests_total",
    "Total HTTP requests",
    ["method", "path", "status"],
)

http_request_duration_seconds = Histogram(
    "http_request_duration_seconds",
    "HTTP request duration in seconds",
    ["method", "path"],
    buckets=(0.005, 0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1, 2.5, 5, 10),
)

http_requests_in_progress = Gauge(
    "http_requests_in_progress",
    "Number of HTTP requests in progress",
)

# ── DB 连接池指标 （v1.1.26 新增）──
db_pool_size = Gauge(
    "db_pool_size",
    "Database connection pool size",
)
db_pool_checked_out = Gauge(
    "db_pool_checked_out",
    "Database connections currently checked out",
)
db_pool_overflow = Gauge(
    "db_pool_overflow",
    "Database overflow connections",
)

# ── Redis 缓存指标 （v1.1.26 新增）──
redis_connected = Gauge(
    "redis_connected",
    "Redis connection status (1=connected, 0=disconnected)",
)

# ── LLM API 调用指标 （v1.1.26 新增）──
llm_request_total = Counter(
    "llm_request_total",
    "Total LLM API requests",
    ["model", "status"],
)
llm_request_duration_seconds = Histogram(
    "llm_request_duration_seconds",
    "LLM API request duration in seconds",
    ["model"],
    buckets=(0.5, 1, 2.5, 5, 10, 30, 60, 120, 180),
)

# ── WebSocket 指标 （v1.1.26 新增）──
ws_connections = Gauge(
    "ws_connections",
    "Current WebSocket connections",
)

# ── DB 查询性能指标（v1.1.27 新增）──
# 慢查询中间件（app/middleware/slow_query.py）使用
db_query_duration_seconds = Histogram(
    "db_query_duration_seconds",
    "DB query duration in seconds",
    ["endpoint", "operation"],
    buckets=(0.005, 0.01, 0.025, 0.05, 0.1, 0.2, 0.5, 1, 2.5, 5),
)

# ── 缓存命中率指标（v1.1.27 新增）──
# 缓存装饰器（app/services/cache_decorator.py）使用
cache_hits_total = Counter(
    "cache_hits_total",
    "Total cache hits",
    ["key_prefix"],
)
cache_misses_total = Counter(
    "cache_misses_total",
    "Total cache misses",
    ["key_prefix"],
)
cache_hit_rate = Gauge(
    "cache_hit_rate",
    "Cache hit rate (hits / (hits + misses))",
    ["key_prefix"],
)


def metrics_response() -> Response:
    """返回 Prometheus 格式的指标数据。"""
    return Response(content=generate_latest(), media_type=CONTENT_TYPE_LATEST)


# ── DB 连接池采样任务（v1.1.26）──
# 通过后台定时任务更新连接池指标，避免每次请求都查询 pool 状态

import asyncio  # noqa: E402
import logging  # noqa: E402

_logger = logging.getLogger("ihome.metrics")


async def _sample_db_pool():
    """定期采样 DB 连接池状态。"""
    while True:
        try:
            from app.database import engine

            pool = engine.pool
            if hasattr(pool, "size"):
                db_pool_size.set(pool.size())
            if hasattr(pool, "checkedout"):
                db_pool_checked_out.set(pool.checkedout())
            if hasattr(pool, "overflow"):
                db_pool_overflow.set(pool.overflow())
        except Exception:
            pass
        await asyncio.sleep(15)


async def _sample_redis_status():
    """定期采样 Redis 连接状态。"""
    while True:
        try:
            from app.services.cache_service import cache
            if cache._init_attempted:
                redis_connected.set(1 if cache.backend == "redis" else 0)
            else:
                redis_connected.set(0)
        except Exception:
            redis_connected.set(0)
        await asyncio.sleep(30)


# 后台任务注册（由 app lifespan 启动）
_background_tasks: list[asyncio.Task] = []


def start_metrics_samplers():
    """启动指标采样后台任务。"""
    global _background_tasks
    if _background_tasks:
        return
    _background_tasks = [
        asyncio.create_task(_sample_db_pool()),
        asyncio.create_task(_sample_redis_status()),
    ]
    _logger.info("metrics_samplers_started")


async def stop_metrics_samplers():
    """停止指标采样后台任务。"""
    for task in _background_tasks:
        task.cancel()
    if _background_tasks:
        await asyncio.gather(*_background_tasks, return_exceptions=True)
    _background_tasks.clear()

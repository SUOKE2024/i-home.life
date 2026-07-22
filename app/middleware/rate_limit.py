"""基于内存滑动窗口的 API 速率限制中间件。

设计要点：
- 使用 collections.defaultdict + deque 存储每个 IP 的请求时间戳，实现滑动窗口
- 默认 60 次/分钟；认证端点（/api/auth/login、/api/auth/register）10 次/分钟
- 健康检查与指标端点（/health、/api/health、/metrics）不受限
- 超限返回 429，并携带 X-RateLimit-* 与 Retry-After 响应头
- 通过 Settings.rate_limit_enabled feature flag 控制开关
- 按需清理过期条目，避免内存无限增长
"""
from __future__ import annotations

import time
from collections import defaultdict, deque

import structlog
from fastapi import Request
from starlette.responses import JSONResponse, Response

logger = structlog.get_logger("ihome")

# ── 常量 ──
_WINDOW_SECONDS: int = 60  # 滑动窗口长度（秒），与“每分钟”对齐

# 不受限的路径：健康检查、指标暴露
_EXEMPT_PATHS: frozenset[str] = frozenset({
    "/health",
    "/api/health",
    "/api/health/detail",
    "/metrics",
})

# 认证端点：更严格限制（防暴力破解）
_AUTH_PATHS: frozenset[str] = frozenset({
    "/api/auth/login",
    "/api/auth/register",
})

# 按需清理的频率：每 N 次请求触发一次过期条目清理
_CLEANUP_INTERVAL: int = 100

# ── 滑动窗口存储 ──
# 结构: {ip: {"api": deque[ts], "auth": deque[ts]}}
# 用 defaultdict 自动初始化，避免手动 setdefault
_windows: defaultdict[str, defaultdict[str, deque]] = defaultdict(
    lambda: defaultdict(deque)
)

# 全局清理计数器（非线程安全，单进程足够；多 worker 部署需替换为 Redis）
_cleanup_counter: int = 0


def reset_rate_limit_store() -> None:
    """清空速率限制存储（主要用于测试隔离）。"""
    _windows.clear()


def _cleanup_expired(now: float) -> None:
    """清理过期时间戳与空 IP 条目，避免内存无限增长。

    每次按需调用扫描全表，由于 defaultdict 已经在写入时自动初始化，
    此处只做读取与删除，复杂度 O(N)，N 为最近 60s 内活跃的 IP 数。
    """
    cutoff = now - _WINDOW_SECONDS
    empty_ips: list[str] = []
    for ip, paths in _windows.items():
        empty_path_keys: list[str] = []
        for path_key, timestamps in paths.items():
            # 从左侧（旧）弹出过期时间戳
            while timestamps and timestamps[0] < cutoff:
                timestamps.popleft()
            if not timestamps:
                empty_path_keys.append(path_key)
        for path_key in empty_path_keys:
            del paths[path_key]
        if not paths:
            empty_ips.append(ip)
    for ip in empty_ips:
        del _windows[ip]


def _get_client_ip(request: Request) -> str:
    """获取客户端真实 IP。

    优先取 X-Forwarded-For 首位（反向代理/Nginx 场景）；
    ASGITransport 测试场景下 request.client 可能为 None，降级为 "unknown"。
    """
    xff = request.headers.get("x-forwarded-for")
    if xff:
        # X-Forwarded-For: client, proxy1, proxy2 — 取第一个
        return xff.split(",")[0].strip()
    client = request.client
    return client.host if client else "unknown"


async def rate_limit_middleware(request: Request, call_next) -> Response:
    """API 速率限制中间件主入口。

    受 Settings.rate_limit_enabled 控制；关闭时直接放行。
    """
    # 延迟导入避免循环依赖
    from app.config import get_settings
    settings = get_settings()

    # Feature flag 关闭：直接放行
    if not settings.rate_limit_enabled:
        return await call_next(request)

    path: str = request.url.path

    # 健康检查 / 指标端点不受限
    if path in _EXEMPT_PATHS:
        return await call_next(request)

    # 区分认证端点（更严格）与普通 API
    if path in _AUTH_PATHS:
        limit: int = settings.rate_limit_auth_per_minute
        path_key: str = "auth"
    else:
        limit = settings.rate_limit_per_minute
        path_key = "api"

    ip = _get_client_ip(request)
    now: float = time.time()

    # 按需清理过期条目（每 _CLEANUP_INTERVAL 次请求触发一次）
    global _cleanup_counter
    _cleanup_counter += 1
    if _cleanup_counter >= _CLEANUP_INTERVAL:
        _cleanup_counter = 0
        _cleanup_expired(now)

    # 滑动窗口：弹出 60s 之前的时间戳
    window: deque = _windows[ip][path_key]
    cutoff: float = now - _WINDOW_SECONDS
    while window and window[0] < cutoff:
        window.popleft()

    # 计算剩余配额与重置时间
    current_count: int = len(window)
    remaining: int = limit - current_count
    # 重置时间 = 最早一条时间戳 + 窗口长度（窗口为空时用 now+窗口长度）
    reset_at: int = int(window[0] + _WINDOW_SECONDS) if window else int(now + _WINDOW_SECONDS)

    # 超限：返回 429（不消耗配额，不写入时间戳）
    if remaining <= 0:
        retry_after: int = max(1, int(window[0] + _WINDOW_SECONDS - now))
        logger.warning(
            "rate_limit_exceeded",
            ip=ip,
            path=path,
            method=request.method,
            limit=limit,
            path_key=path_key,
            retry_after=retry_after,
        )
        return JSONResponse(
            status_code=429,
            content={
                "error": True,
                "detail": "请求过于频繁，请稍后再试",
                "status_code": 429,
                "path": path,
            },
            headers={
                "X-RateLimit-Limit": str(limit),
                "X-RateLimit-Remaining": "0",
                "X-RateLimit-Reset": str(reset_at),
                "Retry-After": str(retry_after),
            },
        )

    # 配额未满：记录本次请求时间戳，调用下游
    window.append(now)
    response: Response = await call_next(request)

    # 附加 RateLimit 响应头（remaining 减去本次消耗的 1 次）
    response.headers["X-RateLimit-Limit"] = str(limit)
    response.headers["X-RateLimit-Remaining"] = str(max(0, remaining - 1))
    response.headers["X-RateLimit-Reset"] = str(reset_at)

    return response


__all__: list[str] = [
    "rate_limit_middleware",
    "reset_rate_limit_store",
]

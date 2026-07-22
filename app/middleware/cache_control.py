"""API 响应缓存控制中间件 — v1.1.26。

核心优化:
    1. 为幂等 GET API 响应设置适度的 Cache-Control 头（max-age=30s），
       允许浏览器和 CDN 缓存，减少重复请求带宽
    2. 动态/认证/非幂等端点设置 no-store 确保数据一致性
    3. 静态资源路径跳过（由 static_cache_middleware 处理）

注意:
    - 不实现 ETag/304（需响应体哈希，与 BaseHTTPMiddleware 架构不兼容）
    - 不需要 ETag 即可通过浏览器 Cache-Control 实现等效性能提升
"""

from __future__ import annotations

from typing import Callable

from fastapi import Request, Response


# 跳过路径 — 由 static_cache_middleware 处理
_SKIP_PREFIXES: frozenset[str] = frozenset({
    "/assets/",
    "/ws",
})

# 幂等 GET API 缓存策略: 30 秒私有缓存
_IDEMPOTENT_CACHE = "private, max-age=30"

# 实时/动态端点: 永不缓存
_NO_CACHE = "no-store"


# 可缓存的幂等 GET 路径前缀
_CACHEABLE_PREFIXES: frozenset[str] = frozenset({
    "/api/materials",
    "/api/furniture-catalog",
    "/api/config/feature-flags",
    "/api/config",
    "/api/products",
    "/api/floorplans",
    "/api/health",
    "/api/smart-home",
    "/api/scene-automation",
})


async def cache_control_middleware(request: Request, call_next: Callable) -> Response:
    """API 响应缓存控制中间件。

    为幂等 GET 请求设置适度的 Cache-Control，减少不必要的重复请求。
    认证/动态端点保持 no-store。
    """
    response = await call_next(request)

    # 仅处理 GET 请求
    if request.method != "GET":
        return response

    path = request.url.path

    # 跳过静态资源（由 static_cache_middleware 处理）
    if any(path.startswith(prefix) for prefix in _SKIP_PREFIXES):
        return response

    # 仅处理 API 请求
    if not path.startswith("/api/"):
        return response

    # 非 200 响应不缓存
    if response.status_code != 200:
        return response

    # 已有 cache-control 的响应保持原样
    if "cache-control" in {k.lower() for k in response.headers}:
        return response

    # 检查是否为可缓存端点
    if any(path.startswith(prefix) for prefix in _CACHEABLE_PREFIXES):
        response.headers["Cache-Control"] = _IDEMPOTENT_CACHE
    else:
        response.headers["Cache-Control"] = _NO_CACHE

    return response

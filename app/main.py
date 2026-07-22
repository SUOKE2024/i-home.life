import os
import time
import uuid
from collections import deque
from contextlib import asynccontextmanager

import structlog
from fastapi import APIRouter, FastAPI, WebSocket, WebSocketDisconnect, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
from starlette.exceptions import HTTPException as StarletteHTTPException
from structlog.contextvars import bind_contextvars, clear_contextvars

from starlette.middleware.gzip import GZipMiddleware

from app.config import get_settings
from app.database import init_db, engine
from app.logging_config import configure_logging
from app.middleware.rate_limit import rate_limit_middleware
from app.middleware.cache_control import cache_control_middleware
from app.middleware.slow_query import register_slow_query_logging, set_current_endpoint
from app.metrics import (
    http_request_duration_seconds,
    http_requests_in_progress,
    http_requests_total,
    metrics_response,
    start_metrics_samplers,
    stop_metrics_samplers,
)
from app.api import (
    auth, projects, materials, budgets, procurement, construction, settlements,
    floorplans, voice, voice_realtime, files, agents, surveys, location,
    change_orders, takeoff, mep, payments, chat, crews, workers, lighting,
    kitchen, bathroom, custom_furniture, soft_furnishing, vr_panorama, ai_image,
    kitchen_bath_mep, hard_decoration, door_window_waterproof, furniture_catalog,
    smart_home, scene_automation, procurement_enhanced, appliance, structural,
)
from app.api import identity, products, tasks, points
from app.api import notifications
from app.api import admin
from app.api import product_batch
from app.api import camera_scan
from app.api import config as config_api
from app.api import harness_api
from app.api import sketch_to_3d
from app.api import cad_import
from app.api import mcp as mcp_api
from app.api import ai_render
from app.api import ifc_export

settings = get_settings()
logger = structlog.get_logger("ihome")

# ── 监控常量 ──
SLOW_REQUEST_THRESHOLD = 3.0  # 慢请求阈值（秒）
_ALERT_WINDOW_SIZE = 100      # 异常率告警滑动窗口
_ALERT_ERROR_RATE = 0.10      # 5xx 比例告警阈值
_alert_status_window: deque = deque(maxlen=_ALERT_WINDOW_SIZE)


def _extract_user_id(request: Request):
    """从 Authorization 头解析 PASETO user_id，失败返回 None（不记录 token）。

    性能优化（v1.1.12）：将解析后的 payload 缓存到 request.state.paseto_payload，
    get_current_user 优先复用缓存，避免同一请求 verify_token 被调用 2 次。
    """
    # 命中缓存：get_current_user 已先调用过
    cached = getattr(request.state, "paseto_payload", None)
    if cached is not None:
        return cached.get("sub")

    auth_header = request.headers.get("Authorization", "")
    if not auth_header.startswith("Bearer "):
        return None
    try:
        from app.auth.paseto_handler import verify_token
        payload = verify_token(auth_header[7:])
        # 缓存到 request.state 供 get_current_user 复用
        request.state.paseto_payload = payload
        return payload.get("sub")
    except Exception:
        return None


def _check_error_rate(status_code: int) -> None:
    """滑动窗口异常率告警：5xx 比例超阈值且当前请求为 5xx 时输出 WARNING。"""
    _alert_status_window.append(status_code)
    if len(_alert_status_window) < 20:
        return
    error_count = sum(1 for s in _alert_status_window if s >= 500)
    error_rate = error_count / len(_alert_status_window)
    if status_code >= 500 and error_rate >= _ALERT_ERROR_RATE:
        logger.warning(
            "high_error_rate_alert",
            error_rate=round(error_rate, 4),
            window_size=len(_alert_status_window),
            error_count=error_count,
            threshold=_ALERT_ERROR_RATE,
        )


def _normalize_endpoint(path: str) -> str:
    """规范化端点路径，降低 Prometheus label 基数（v1.1.27）。

    /api/materials/123 → /api/materials/{id}
    /api/projects/456/tasks → /api/projects/{id}/tasks
    UUID 路径段也替换为 {id}。
    """
    parts = path.split("/")
    normalized = []
    for part in parts:
        if not part:
            normalized.append(part)
        elif part.isdigit() or _is_uuid(part):
            normalized.append("{id}")
        else:
            normalized.append(part)
    return "/".join(normalized)


def _is_uuid(s: str) -> bool:
    """快速判断字符串是否为 UUID 格式。"""
    return len(s) == 36 and s.count("-") == 4


@asynccontextmanager
async def lifespan(app: FastAPI):
    await init_db()
    configure_logging(debug=settings.debug)
    # 注册慢查询日志中间件（v1.1.27）— SQLAlchemy 事件监听
    register_slow_query_logging(engine)
    # 启动 Prometheus 指标采样后台任务（DB 连接池 + Redis 状态）
    start_metrics_samplers()
    # 生产环境检查: WebAuthn 挑战存储需要 Redis 实现多 worker 共享
    if not settings.redis_url and not settings.debug:
        logger.warning(
            "WebAuthn 挑战存储: 未配置 Redis (redis_url)，"
            "多 worker 部署下挑战将不共享，可能导致注册/登录失败。"
        )
    yield
    # 应用关闭时清理
    await stop_metrics_samplers()
    from app.services.cache_service import cache
    await cache.close()
    from app.services.webauthn_service import close_challenge_store
    await close_challenge_store()


app = FastAPI(
    title=settings.app_name,
    version=settings.app_version,
    lifespan=lifespan,
    # 将 docs/openapi 路径置于 /api/ 前缀下，避免被根路径 StaticFiles 拦截
    docs_url="/api/docs",
    redoc_url="/api/redoc",
    openapi_url="/api/openapi.json",
)

# CORS: 生产环境从 .env 读取白名单; DEBUG 模式下列出常用本地开发端口
_cors_origins = (
    settings.cors_origins
    if settings.cors_origins
    else (
        ["http://localhost:3000", "http://localhost:5173", "http://localhost:8084",
         "http://localhost:8085", "http://localhost:5500", "http://localhost:8000"]
        if settings.debug
        else ["http://localhost:3000"]
    )
)
app.add_middleware(
    CORSMiddleware,
    allow_origins=_cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ── GZip 压缩中间件（v1.2.1 性能优化）──
# 压缩 JSON/HTML/CSS/JS/text 响应，典型节省 60-80% 带宽
# minimum_size=500：仅压缩 ≥500B 的响应，避免小 body 压缩开销
app.add_middleware(GZipMiddleware, minimum_size=500)

# ── API 缓存控制中间件（v1.1.26 性能优化）──
# 幂等 GET 端点（materials/products/config 等）设置 max-age=30s 缓存
# 动态端点保持 no-store，确保数据一致性
# 与 static_cache_middleware 互补：静态资源 1y / HTML 5min / API 差异化
app.middleware("http")(cache_control_middleware)


# ── 静态资源缓存中间件（v1.2.1 性能优化）──
# 为 /assets/ 下的 CSS/JS/图片/字体设置长期缓存头，
# 配合前端版本号 v=YYYYMMDD 实现缓存失效
@app.middleware("http")
async def static_cache_middleware(request: Request, call_next):
    response = await call_next(request)
    path = request.url.path

    # 静态资源长期缓存（1 年），配合版本号参数触发更新
    if path.startswith("/assets/") or any(
        path.endswith(ext) for ext in (".css", ".js", ".woff2", ".png", ".jpg", ".svg", ".ico", ".webp")
    ):
        response.headers["Cache-Control"] = "public, max-age=31536000, immutable"
    # HTML 页面短期缓存（5 分钟），避免频繁加载
    elif path.endswith(".html") and not path.startswith("/api/"):
        response.headers["Cache-Control"] = "public, max-age=300, must-revalidate"
    # Service Worker 不缓存
    elif path.endswith("sw.js"):
        response.headers["Cache-Control"] = "no-cache"
    # API 响应的 Cache-Control 由 etag_middleware 统一处理（v1.1.26）
    # 非 GET API 请求不缓存
    elif path.startswith("/api/") and request.method != "GET":
        response.headers["Cache-Control"] = "no-store"

    return response


# ── API 速率限制中间件（v1.2.1）──
# 基于内存滑动窗口的 IP 限流：普通 API 60/min，认证端点 10/min
# 受 settings.rate_limit_enabled feature flag 控制；健康检查与 /metrics 不受限
# 注册顺序说明：源码中先于 request_tracking_middleware 注册，
# 使其在请求链路上位于 request_tracking 之后执行 —— request_tracking 仍能记录被限流拒绝的 429 请求
app.middleware("http")(rate_limit_middleware)


# ── 请求追踪中间件：request_id / 结构化日志 / metrics / 异常率告警 ──
@app.middleware("http")
async def request_tracking_middleware(request: Request, call_next):
    path = request.url.path
    method = request.method

    # 排除 /metrics 端点与静态文件（仅追踪 /api、/health、/ws）
    if path == "/metrics" or not (
        path.startswith("/api") or path.startswith("/health") or path.startswith("/ws")
    ):
        return await call_next(request)

    request_id = request.headers.get("X-Request-ID") or str(uuid.uuid4())
    user_id = _extract_user_id(request)

    bind_contextvars(request_id=request_id, user_id=user_id, method=method, path=path)

    # 设置慢查询中间件端点标签（v1.1.27）— 在 call_next 之前设置，
    # 确保 SQLAlchemy 事件回调能读取到当前端点
    set_current_endpoint(_normalize_endpoint(path))

    http_requests_in_progress.inc()
    start = time.perf_counter()
    status_code = 500
    try:
        response = await call_next(request)
        status_code = response.status_code
        response.headers["X-Request-ID"] = request_id
        return response
    except Exception:
        logger.error("request_unhandled_exception", exc_info=True)
        raise
    finally:
        duration = time.perf_counter() - start
        duration_ms = round(duration * 1000, 2)
        http_requests_in_progress.dec()

        # 使用路由模板降低 label 基数
        route = request.scope.get("route")
        path_label = getattr(route, "path", path) if route else path
        if not path_label or path_label == "/":
            path_label = path

        http_requests_total.labels(
            method=method, path=path_label, status=str(status_code)
        ).inc()
        http_request_duration_seconds.labels(method=method, path=path_label).observe(
            duration
        )

        logger.info(
            "request",
            duration_ms=duration_ms,
            status_code=status_code,
        )

        if duration > SLOW_REQUEST_THRESHOLD:
            logger.warning(
                "slow_request",
                duration_ms=duration_ms,
                status_code=status_code,
            )

        if status_code >= 500:
            logger.error(
                "server_error",
                duration_ms=duration_ms,
                status_code=status_code,
            )

        _check_error_rate(status_code)
        clear_contextvars()


# ── API 路由（统一 /api 前缀，与前端 JS 中 `const API = '/api'` 对齐） ──
api_router = APIRouter(prefix="/api")
api_router.include_router(auth.router)          # /api/auth/*
api_router.include_router(projects.router)      # /api/projects/*
api_router.include_router(product_batch.router)  # /api/products/batch/* (must be before products)
api_router.include_router(camera_scan.router)  # /api/products/camera/* (must be before products)
api_router.include_router(materials.router)     # /api/materials/*
api_router.include_router(budgets.router)       # /api/budgets/*
api_router.include_router(procurement.router)   # /api/procurement/*
api_router.include_router(construction.router)  # /api/construction/*
api_router.include_router(settlements.router)   # /api/settlements/*
api_router.include_router(floorplans.router)    # /api/floorplans/*
api_router.include_router(voice.router)         # /api/voice/*
api_router.include_router(voice_realtime.router)  # /api/voice/* (实时语音)
api_router.include_router(files.router)         # /api/files/*
api_router.include_router(agents.router)        # /api/agents/*
api_router.include_router(surveys.router)       # /api/surveys/*
api_router.include_router(location.router)      # /api/location/*
api_router.include_router(change_orders.router)  # /api/change-orders/*
api_router.include_router(takeoff.router)       # /api/takeoff/*
api_router.include_router(mep.router)           # /api/mep/*
api_router.include_router(payments.router)      # /api/payments/*
api_router.include_router(chat.router)          # /api/chat/*
api_router.include_router(crews.router)         # /api/crews/*
api_router.include_router(workers.router)       # /api/workers/*
api_router.include_router(lighting.router)     # /api/lighting/*
api_router.include_router(kitchen.router)      # /api/kitchen/*
api_router.include_router(bathroom.router)     # /api/bathroom/*
api_router.include_router(custom_furniture.router)  # /api/custom-furniture/*
api_router.include_router(soft_furnishing.router)   # /api/soft-furnishing/*
api_router.include_router(vr_panorama.router)  # /api/vr/*
api_router.include_router(ai_image.router)     # /api/ai-image/*
api_router.include_router(kitchen_bath_mep.router)        # /api/mep-kb/* (F18)
api_router.include_router(hard_decoration.router)         # /api/hard-decoration/* (F21)
api_router.include_router(door_window_waterproof.router)  # /api/door-window-waterproof/* (F23)
api_router.include_router(furniture_catalog.router)       # /api/furniture-catalog/* (F26)
api_router.include_router(smart_home.router)              # /api/smart-home/* (F31)
api_router.include_router(scene_automation.router)        # /api/scene-automation/* (F32)
api_router.include_router(procurement_enhanced.router)    # /api/procurement-enhanced/* (F33/F34)
api_router.include_router(appliance.router)                # /api/appliances/* (F19/F20)
api_router.include_router(structural.router)              # /api/structural/* (F8/F9)
api_router.include_router(identity.router)             # /api/identity/*
api_router.include_router(products.router)             # /api/products/*
api_router.include_router(tasks.router)                # /api/tasks/*
api_router.include_router(points.router)               # /api/points/*
api_router.include_router(notifications.router)       # /api/notifications/*
api_router.include_router(admin.router)             # /api/admin/*
api_router.include_router(config_api.router)        # /api/config/*
api_router.include_router(harness_api.router)        # /api/harness/*
api_router.include_router(sketch_to_3d.router)    # /api/sketch-to-3d/* (v1.2.0)
api_router.include_router(cad_import.router)       # /api/cad-import/*
# v1.1.12 新增：MCP Server + AI 渲染端点（受 feature flag 控制，路由始终注册但端点内部校验）
api_router.include_router(mcp_api.router)          # /api/mcp/* (MCP 2026-07-28)
api_router.include_router(ai_render.router)        # /api/ai-render/* (2D/3D/restage)
api_router.include_router(ifc_export.router)      # /api/bim/export/* (IFC 导出)
app.include_router(api_router)

# ── 全局异常处理 ──


@app.exception_handler(StarletteHTTPException)
async def http_exception_handler(request: Request, exc: StarletteHTTPException):
    """统一 HTTP 异常响应格式"""
    return JSONResponse(
        status_code=exc.status_code,
        content={
            "error": True,
            "detail": exc.detail,
            "status_code": exc.status_code,
            "path": request.url.path,
        },
    )


@app.exception_handler(Exception)
async def unhandled_exception_handler(request: Request, exc: Exception):
    """未捕获异常兜底处理 — 不泄露堆栈信息"""
    logger.error(f"Unhandled exception at {request.method} {request.url.path}: {exc}", exc_info=True)
    return JSONResponse(
        status_code=500,
        content={
            "error": True,
            "detail": "服务器内部错误，请稍后重试",
            "status_code": 500,
            "path": request.url.path,
        },
    )


@app.get("/health")
@app.get("/api/health")
async def health_check():
    return {"status": "ok", "app": settings.app_name, "version": settings.app_version, "domain": "i-home.life"}


@app.get("/api/health/detail")
async def health_check_detail():
    """详细健康检查：数据库、Redis（可选）、磁盘空间。"""
    import shutil

    from sqlalchemy import text

    from app.database import engine

    checks: dict = {}
    overall = "ok"

    # 数据库连接
    try:
        async with engine.connect() as conn:
            await conn.execute(text("SELECT 1"))
        checks["database"] = {"status": "ok"}
    except Exception as e:
        checks["database"] = {"status": "error", "detail": str(e)}
        overall = "degraded"

    # Redis 连接（仅在配置 redis_url 时检查）
    if settings.redis_url:
        try:
            import redis.asyncio as aioredis

            r = aioredis.from_url(settings.redis_url, socket_connect_timeout=2)
            await r.ping()
            await r.aclose()
            checks["redis"] = {"status": "ok"}
        except Exception as e:
            checks["redis"] = {"status": "error", "detail": str(e)}
            overall = "degraded"
    else:
        checks["redis"] = {"status": "disabled"}

    # 磁盘空间（检查项目所在分区）
    # v1.1.1: 三级阈值 — ok (>15%) / warning (5-15%) / critical (<5%)
    try:
        base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        usage = shutil.disk_usage(base_dir)
        free_percent = round(usage.free / usage.total * 100, 2)
        if free_percent < 5:
            disk_status = "critical"
            overall = "degraded"
        elif free_percent < 15:
            disk_status = "warning"
            overall = "degraded"
        else:
            disk_status = "ok"
        checks["disk"] = {
            "status": disk_status,
            "free_percent": free_percent,
            "free_gb": round(usage.free / (1024**3), 2),
            "total_gb": round(usage.total / (1024**3), 2),
        }
    except Exception as e:
        checks["disk"] = {"status": "error", "detail": str(e)}
        overall = "degraded"

    return JSONResponse(
        status_code=200 if overall == "ok" else 503,
        content={
            "status": overall,
            "app": settings.app_name,
            "version": settings.app_version,
            "checks": checks,
        },
    )


@app.get("/metrics")
async def metrics():
    """Prometheus 指标端点。"""
    return metrics_response()


@app.websocket("/ws/{project_id}")
async def websocket_endpoint(websocket: WebSocket, project_id: str):  # noqa: C901
    """WebSocket 实时通信端点 — 需 PASETO Token 认证 + 项目归属校验

    客户端通过 query 参数传递 token: ws://host/ws/{project_id}?token=xxx
    """
    import logging
    from sqlalchemy import select as sql_select
    from app.auth.paseto_handler import verify_token, TokenExpiredError, TokenInvalidError
    from app.database import async_session
    from app.models.project import Project
    from app.ws import ws_manager

    logger = logging.getLogger(__name__)

    # ── 认证: 从 query 参数获取 token ──
    token = websocket.query_params.get("token")
    if not token:
        await websocket.close(code=4001, reason="缺少认证令牌")
        return

    try:
        payload = verify_token(token)
    except TokenExpiredError:
        await websocket.close(code=4001, reason="令牌已过期")
        return
    except TokenInvalidError:
        await websocket.close(code=4001, reason="无效的令牌")
        return

    user_id = payload.get("sub")
    user_role = payload.get("role", "homeowner")
    if not user_id:
        await websocket.close(code=4001, reason="令牌格式无效")
        return

    # ── 项目归属校验: 防止越权连接任意项目 WS ──
    async with async_session() as db:
        result = await db.execute(sql_select(Project).where(Project.id == project_id))
        project = result.scalar_one_or_none()
        if not project:
            await websocket.close(code=4004, reason="项目不存在")
            return
        if user_role != "admin" and project.owner_id != user_id:
            await websocket.close(code=4003, reason="无权访问此项目")
            return

    await ws_manager.connect(websocket, project_id)
    # 认证成功后通知客户端
    await ws_manager.send_to(websocket, "connected", {
        "project_id": project_id,
        "user_id": user_id,
        "role": user_role,
    })
    try:
        import asyncio
        import json as _json
        from app.ws import RECEIVE_TIMEOUT, PONG_TIMEOUT
        while True:
            try:
                data = await asyncio.wait_for(
                    websocket.receive_text(), timeout=RECEIVE_TIMEOUT
                )
            except asyncio.TimeoutError:
                # 无活动超时：发送 ping 探测，等待 pong 或任意消息
                await ws_manager.send_ping(websocket)
                try:
                    await asyncio.wait_for(
                        websocket.receive_text(), timeout=PONG_TIMEOUT
                    )
                    # 收到任意消息（含 pong）即视为存活，继续循环
                    continue
                except asyncio.TimeoutError:
                    logger.warning(
                        f"WebSocket 心跳超时断开僵尸连接: project={project_id}, user={user_id}"
                    )
                    await websocket.close(code=4002, reason="心跳超时")
                    break
            try:
                msg = _json.loads(data)
                event = msg.get("event", "message")
                # v1.1.1: 客户端 ping 自动回复 pong（心跳保活）
                if event == "ping":
                    await ws_manager.send_to(websocket, "pong", {})
                    continue
                if event == "pong":
                    # 服务端主动 ping 的回复，无需处理
                    continue
                payload_data = msg.get("data", {})
                # 注入发送者信息
                payload_data["_sender_id"] = user_id
                payload_data["_sender_role"] = user_role
                await ws_manager.broadcast_to_project(project_id, event, payload_data)
            except _json.JSONDecodeError:
                await ws_manager.send_to(websocket, "error", {"message": "消息格式无效，需为合法 JSON"})
            except Exception as e:
                logger.warning(f"WebSocket 消息处理异常: project={project_id}, error={e}")
                await ws_manager.send_to(websocket, "error", {"message": f"处理失败: {str(e)}"})
    except WebSocketDisconnect:
        logger.info(f"WebSocket 客户端断开: project={project_id}, user={user_id}")
    except Exception as e:
        logger.error(f"WebSocket 异常断开: project={project_id}, user={user_id}, error={e}")
    finally:
        ws_manager.disconnect(websocket)


# ── 站点静态文件（挂载在根路径，确保 index.html / studio.html 直接可访问） ──
web_dir = os.path.join(os.path.dirname(__file__), "..", "web")
if os.path.isdir(web_dir):
    app.mount("/", StaticFiles(directory=web_dir, html=True), name="web")

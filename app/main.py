import asyncio
import os
import time
import uuid
from collections import deque
from contextlib import asynccontextmanager

import structlog
from fastapi import APIRouter, FastAPI, WebSocket, WebSocketDisconnect, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.openapi.docs import get_swagger_ui_html
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException
from structlog.contextvars import bind_contextvars, clear_contextvars

from starlette.middleware.gzip import GZipMiddleware

from app.config import get_settings
from app.database import init_db, engine
from app.logging_config import configure_logging
from app.observability.tracing import instrument_fastapi, setup_tracing
from app.middleware.rate_limit import rate_limit_middleware
from app.middleware.cache_control import cache_control_middleware
from app.services.change_order_service import ChangeOrderStateError
from app.services.task_service import TaskStateError
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
    floorplans, voice, voice_realtime, voice_orchestrate, files, agents, surveys, location,
    agent_memory,
    agent_approvals,
    agent_skills,
    change_orders, takeoff, mep, payments, chat, crews, workers, lighting,
    kitchen, bathroom, custom_furniture, soft_furnishing, vr_panorama, ai_image,
    kitchen_bath_mep, hard_decoration, door_window_waterproof, furniture_catalog,
    smart_home, scene_automation, procurement_enhanced, appliance, structural,
    dashboard,
)
from app.api import identity, products, tasks, points
from app.api import notifications
from app.api import admin
from app.api import product_batch
from app.api import camera_scan
from app.api import b2b_delivery  # /api/b2b/* (B2B 装企交付 v1.4.x)
from app.api import config as config_api
from app.api import harness_api
from app.api import sketch_to_3d
from app.api import cad_import
from app.api import mcp as mcp_api
from app.api import ai_render
from app.api import ifc_export
from app.api import construction_drawing
from app.api import eval as eval_api
from app.api import a2a as a2a_api
from app.api import energy
from app.api import health as health_api
from app.api import sensor_snapshot
from app.api import analytics
# v1.5.0 需求补充落地（PRD v3.1 F41-F47）
from app.api import elderly_adaptation
from app.api import partial_renovation
from app.api import escrow_trustee
from app.api import eco_materials
from app.api import solution_first
from app.api import ecosystem
from app.api import ai_qa
from app.api import agent_identity  # v1.9.0 GB/Z 185 智能体身份码/ACDL（flag 门控）
from app.api import diagnostics as diagnostics_api  # v1.10.x 全链路诊断管理端

settings = get_settings()
logger = structlog.get_logger("ihome")

# ── 监控常量 ──
SLOW_REQUEST_THRESHOLD = 3.0  # 慢请求阈值（秒）
_ALERT_WINDOW_SIZE = 100      # 异常率告警滑动窗口
_ALERT_ERROR_RATE = 0.10      # 5xx 比例告警阈值
_alert_status_window: deque = deque(maxlen=_ALERT_WINDOW_SIZE)

# v1.2.2 F4：OTel tracer provider 关闭句柄。lifespan 启动时由 setup_tracing 返回
# （tracing_enabled=False 时为 None），teardown 时调用以刷新未导出的 span。
_tracing_shutdown = None


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
    normalized: list[str] = []
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
    global _tracing_shutdown
    await init_db()
    configure_logging(debug=settings.debug)
    # 注册慢查询日志中间件（v1.1.27）— SQLAlchemy 事件监听
    register_slow_query_logging(engine)
    # 启动 Prometheus 指标采样后台任务（DB 连接池 + Redis 状态）
    start_metrics_samplers()
    # v1.10.x：启动全链路诊断后台任务（指标快照 / 异常检测+建议 / 数据清理）
    # 受 settings.diagnostics_enabled 门控；测试（ASGITransport）不触发 lifespan，
    # 故仅生产环境运行。任务内每轮 try/except，单轮失败不终止循环。
    _diagnostics_tasks: list[asyncio.Task] = []
    if settings.diagnostics_enabled:
        _diagnostics_tasks = _start_diagnostics_tasks()
    # 生产环境检查: WebAuthn 挑战存储需要 Redis 实现多 worker 共享
    _redis_valid = False
    if settings.redis_url:
        import re
        _redis_valid = bool(re.match(r'^rediss?://', settings.redis_url.strip()))
    if not _redis_valid and not settings.debug:
        logger.warning(
            "WebAuthn 挑战存储: 未配置有效的 Redis URL (redis_url)，"
            "多 worker 部署下挑战将不共享，注册/登录可能随机失败。"
            "请设置 REDIS_URL=redis://host:6379/0（TLS 用 rediss://）。"
            "单 worker 部署可忽略此警告。"
        )
    # 事件总线编排规则注册（v1.2.2）— 跨模块松耦合通信
    if settings.integration_event_bus_enabled:
        from app.services.orchestration_rules import register_all_rules
        register_all_rules()
        logger.info("Event bus orchestration rules registered")
    # v1.2.2 F4：OpenTelemetry 追踪初始化。tracing_enabled=False 时 setup_tracing
    # 返回 None（零开销），instrument_fastapi 也为 no-op。启用时为每个 HTTP 请求
    # 生成 server span，DB 查询生成 client span，trace_id/span_id 注入结构化日志。
    _tracing_shutdown = setup_tracing(settings)
    instrument_fastapi(app)
    # v1.2.3：启动施工健康主动巡检器
    if settings.health_os_enabled:
        from app.services.health_monitor import health_monitor
        from app.database import async_session
        health_monitor._db_factory = async_session
        interval = settings.health_os_check_interval_seconds
        await health_monitor.start(interval_seconds=interval)
    yield
    # 应用关闭时清理
    # v1.10.x：取消诊断后台任务
    for _task in _diagnostics_tasks:
        _task.cancel()
    # v1.2.3：停止施工健康巡检
    if settings.health_os_enabled:
        from app.services.health_monitor import health_monitor
        await health_monitor.stop()
    if _tracing_shutdown is not None:
        _tracing_shutdown()
    await stop_metrics_samplers()
    from app.services.cache_service import cache
    await cache.close()
    from app.services.webauthn_service import close_challenge_store
    await close_challenge_store()


def _start_diagnostics_tasks() -> list[asyncio.Task]:
    """启动全链路诊断后台任务：指标快照 / 异常检测+建议 / 数据清理。"""
    tasks: list[asyncio.Task] = []

    async def _snapshot_loop() -> None:
        from app.services.diagnostics_service import snapshot_metrics
        while True:
            try:
                await snapshot_metrics()
            except Exception as e:  # pragma: no cover - 防御
                logger.warning("diagnostics_snapshot_error", error=str(e))
            await asyncio.sleep(settings.diagnostics_snapshot_interval_seconds)

    async def _analysis_loop() -> None:
        from app.database import async_session
        from app.services.diagnostics_analysis import (
            generate_recommendations,
            run_anomaly_detection,
        )
        while True:
            try:
                async with async_session() as db:
                    await run_anomaly_detection(db)
                    await generate_recommendations(db)
            except Exception as e:  # pragma: no cover - 防御
                logger.warning("diagnostics_analysis_error", error=str(e))
            await asyncio.sleep(settings.diagnostics_alert_interval_seconds)

    async def _cleanup_loop() -> None:
        from app.services.diagnostics_service import cleanup_expired
        interval = max(settings.diagnostics_snapshot_interval_seconds * 10, 600)
        while True:
            try:
                await cleanup_expired()
            except Exception as e:  # pragma: no cover - 防御
                logger.warning("diagnostics_cleanup_error", error=str(e))
            await asyncio.sleep(interval)

    tasks.append(asyncio.create_task(_snapshot_loop()))
    tasks.append(asyncio.create_task(_analysis_loop()))
    tasks.append(asyncio.create_task(_cleanup_loop()))
    logger.info("diagnostics: 全链路诊断后台任务已启动（快照/分析/清理）")
    return tasks


app = FastAPI(
    title=settings.app_name,
    version=settings.app_version,
    lifespan=lifespan,
    # 将 docs/openapi 路径置于 /api/ 前缀下
    # docs_url 设为 None，手动注册以使用本地 Swagger CSS（避免 jsdelivr CDN 不可达）
    # openapi_url 设为 None，下方自定义路由返回预序列化 bytes（避免每请求重序列化 490 路由）
    docs_url=None,
    redoc_url="/api/redoc",
    openapi_url=None,
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
# v1.10.x 全链路诊断集成：采样时开启 trace 链路（begin_trace），请求结束后
# 组装全链路 Trace（HTTP→DB→LLM/Agent span）落库 + 更新内存端点统计。
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

    # v1.10.x：采样命中时开启全链路追踪，trace_id 与 X-Request-ID 对齐
    # （前端 RUM → HTTP → DB → LLM/Agent 全链路关联的唯一标识）
    try:
        from app.services.diagnostics_service import begin_trace
        trace_id = begin_trace()
        if trace_id:
            request_id = trace_id
    except Exception:
        trace_id = None

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
        # v1.10.0 修复：FastAPI 0.139 惰性 include（_IncludedRouter）下 route.path 丢失
        # 外层 APIRouter(prefix="/api") 前缀（如 /dashboard/overview），按真实请求路径
        # 补全为 /api/dashboard/overview，保证 trace / 监控 label 与前端路径一致
        if path_label.startswith("/") and not path_label.startswith("/api") and path.startswith("/api"):
            path_label = "/api" + path_label

        http_requests_total.labels(
            method=method, path=path_label, status=str(status_code)
        ).inc()
        http_request_duration_seconds.labels(method=method, path=path_label).observe(
            duration
        )

        # v1.10.x：全链路 Trace 落库（仅采样命中）+ 内存端点统计（喂快照）
        try:
            from app.services.diagnostics_service import (
                clear_trace_context,
                record_endpoint_request,
                record_trace,
            )

            record_endpoint_request(path_label, duration_ms, status_code)
            if trace_id is not None:
                await record_trace(
                    trace_id,
                    user_id=user_id,
                    method=method,
                    endpoint=path_label,
                    status_code=status_code,
                    duration_ms=duration_ms,
                )
            else:
                clear_trace_context()  # 防 contextvar 跨请求残留
        except Exception:
            pass  # 诊断采集失败不应影响业务主流程

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
api_router.include_router(dashboard.router)      # /api/dashboard/* (v1.2.9 Bento 仪表盘)
api_router.include_router(materials.router)     # /api/materials/*
api_router.include_router(budgets.router)       # /api/budgets/*
api_router.include_router(procurement.router)   # /api/procurement/*
api_router.include_router(construction.router)  # /api/construction/*
api_router.include_router(settlements.router)   # /api/settlements/*
api_router.include_router(floorplans.router)    # /api/floorplans/*
api_router.include_router(voice.router)         # /api/voice/*
api_router.include_router(voice_realtime.router)  # /api/voice/* (实时语音)
api_router.include_router(voice_orchestrate.router)  # /api/voice/orchestrate/* (语音智能体编排)
api_router.include_router(files.router)         # /api/files/*
# /api/agents/memory/* 必须先于 agents router 注册，避免路径歧义
api_router.include_router(agent_memory.router)  # /api/agents/memory/*
api_router.include_router(agent_approvals.router)  # /api/agents/approvals/* (Agent 工具批准, v1.8.0)
api_router.include_router(agent_skills.router)  # /api/agents/skills/* (Agent Skill 资产, v1.8.0)
api_router.include_router(agents.router)        # /api/agents/*
api_router.include_router(agent_identity.router)  # /api/agents/identity/* (GB/Z 185 身份卡, v1.9.0)
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
api_router.include_router(health_api.router)              # /api/health-monitor/* (A2)
api_router.include_router(identity.router)             # /api/identity/*
api_router.include_router(products.router)             # /api/products/*
api_router.include_router(tasks.router)                # /api/tasks/*
api_router.include_router(points.router)               # /api/points/*
api_router.include_router(notifications.router)       # /api/notifications/*
api_router.include_router(admin.router)             # /api/admin/*
api_router.include_router(config_api.router)        # /api/config/*
api_router.include_router(analytics.router)        # /api/analytics/* (前端埋点采集，公开)
api_router.include_router(harness_api.router)        # /api/harness/*
api_router.include_router(sketch_to_3d.router)    # /api/sketch-to-3d/* (v1.2.0)
api_router.include_router(cad_import.router)       # /api/cad-import/*
# v1.1.12 新增：MCP Server + AI 渲染端点（受 feature flag 控制，路由始终注册但端点内部校验）
api_router.include_router(mcp_api.router)          # /api/mcp/* (MCP 2026-07-28)
api_router.include_router(ai_render.router)        # /api/ai-render/* (2D/3D/restage)
api_router.include_router(ifc_export.router)      # /api/bim/export/* (IFC 导出)
api_router.include_router(construction_drawing.router)  # /api/construction-drawing/* (施工图 v1.2.0)
# v1.1.28 借鉴索克生活：评估框架 + A2A 协议端点
api_router.include_router(eval_api.router)         # /api/eval/* (Suoke-Eval1 评估)
api_router.include_router(a2a_api.router)          # /api/a2a/* (A2A 协议)
api_router.include_router(energy.router)           # /api/energy/* (A1 能耗监测)
api_router.include_router(b2b_delivery.router)     # /api/b2b/* (B2B 装企交付 v1.4.x)
api_router.include_router(sensor_snapshot.router)   # /api/sensors/* (传感器快照 v1.2.3)
# v1.5.0 需求补充落地（PRD v3.1 F41-F47）
api_router.include_router(elderly_adaptation.router)  # /api/elderly-adaptation/* (F41 适老改造)
api_router.include_router(partial_renovation.router)  # /api/partial-renovation/* (F42 局部焕新)
api_router.include_router(escrow_trustee.router)      # /api/escrow/* (F43 资金托管深化)
api_router.include_router(eco_materials.router)       # /api/eco-materials/* (F44 环保材料标签)
api_router.include_router(solution_first.router)      # /api/solution-first/* (F45 方案前置决策)
api_router.include_router(ecosystem.router)           # /api/ecosystem/* (F46 生态桥接优先级)
api_router.include_router(ai_qa.router)               # /api/ai-qa/* (F47 AI 装修问答)
api_router.include_router(diagnostics_api.router)     # /api/diagnostics/* (v1.10.x 全链路诊断)
# A2A Agent Card 公开端点（规范要求 .well-known 路径，无 /api 前缀）
app.include_router(a2a_api.public_router)
# v1.3.0: MCP Server Card 公开端点（GET /.well-known/mcp，无 /api 前缀）
app.include_router(mcp_api.public_router)
app.include_router(api_router)

# ── 自定义 Swagger UI（使用本地 CSS 替代 jsdelivr CDN） ──


@app.get("/api/docs", include_in_schema=False)
async def custom_swagger_ui_html():
    """Swagger UI 文档页面，使用本地 swagger-ui.css 避免 CDN 不可达。"""
    return get_swagger_ui_html(
        openapi_url="/api/openapi.json",
        title=settings.app_name + " - Swagger UI",
        swagger_css_url="/assets/css/swagger-ui.css",
    )


# ── OpenAPI schema 预序列化 + 预压缩缓存（性能优化）──
# 问题：FastAPI 默认每请求 json.dumps() 序列化 490 路由 schema dict（753KB），
#   再经 GZipMiddleware 压缩——并发时 GIL 争用致 p99 806ms（concurrency=10）。
# 优化：首次请求时一次性完成 序列化 + gzip 压缩，缓存两份 bytes；
#   后续请求按 Accept-Encoding 直接返回预压缩 bytes，零 CPU 开销。
#   GZipMiddleware 检测到响应已含 Content-Encoding: gzip 会跳过重复压缩。
_openapi_json_bytes: bytes | None = None
_openapi_gzip_bytes: bytes | None = None


@app.get("/api/openapi.json", include_in_schema=False)
async def cached_openapi_json(request: Request):
    """返回预序列化/预压缩的 OpenAPI JSON，避免每请求重序列化 490 路由 + 重压缩。"""
    global _openapi_json_bytes, _openapi_gzip_bytes
    if _openapi_json_bytes is None:
        import gzip
        import json

        schema = app.openapi()  # FastAPI 内部 dict 缓存
        _openapi_json_bytes = json.dumps(schema, ensure_ascii=False).encode("utf-8")
        _openapi_gzip_bytes = gzip.compress(_openapi_json_bytes)

    from fastapi.responses import Response

    accept_encoding = request.headers.get("accept-encoding", "")
    if "gzip" in accept_encoding:
        return Response(
            content=_openapi_gzip_bytes,
            media_type="application/json",
            headers={
                "Content-Encoding": "gzip",
                "Cache-Control": "public, max-age=3600",
            },
        )
    return Response(
        content=_openapi_json_bytes,
        media_type="application/json",
        headers={"Cache-Control": "public, max-age=3600"},
    )

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


@app.exception_handler(ChangeOrderStateError)
async def change_order_state_error_handler(request: Request, exc: ChangeOrderStateError):
    """变更单非法状态流转 → 409 Conflict（而非 500）"""
    return JSONResponse(
        status_code=409,
        content={
            "error": True,
            "detail": str(exc),
            "status_code": 409,
            "path": request.url.path,
        },
    )


@app.exception_handler(TaskStateError)
async def task_state_error_handler(request: Request, exc: TaskStateError):
    """任务状态机非法流转（申领/分配/完成/取消越权）→ 409 Conflict（而非 500）"""
    return JSONResponse(
        status_code=409,
        content={
            "error": True,
            "detail": str(exc),
            "status_code": 409,
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

    # v1.1.28: 密钥管理健康信息（借鉴索克生活 Vault 指纹机制）
    # 暴露 PASETO key fingerprint 供运维校验密钥轮换状态，永不泄露密钥明文
    try:
        from app.services.secret_manager import secret_manager
        checks["secret_manager"] = secret_manager.get_health_info()
    except Exception as e:
        checks["secret_manager"] = {"status": "error", "detail": str(e)}

    # v1.1.28: 意图契约校验状态
    try:
        from app.utils.intent_validator import load_contract
        contract = load_contract()
        validated_count = sum(
            1 for p in contract.get("patterns", [])
            if p.get("validation_status") == "validated"
        )
        checks["intent_contract"] = {
            "status": "ok",
            "validated_patterns": validated_count,
            "total_patterns": len(contract.get("patterns", [])),
        }
    except Exception as e:
        checks["intent_contract"] = {"status": "error", "detail": str(e)}

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

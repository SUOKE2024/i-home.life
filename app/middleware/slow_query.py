"""慢查询日志中间件 — 基于 SQLAlchemy 事件。

设计要点：
- 基于 before_cursor_execute / after_cursor_execute 事件，精准记录每条 SQL
- 阈值可配（slow_query_threshold_ms，默认 200ms）
- 超阈值时记录 WARNING 到 structlog；所有查询记录到 Prometheus 直方图
- feature flag slow_query_log_enabled 控制（运行时检查，重启生效）
- EXPLAIN 可选（slow_query_explain_enabled，默认 False，仅调试开启）
- 通过 register_slow_query_logging(engine) 在 main.py lifespan 注册

使用方式:
    from app.middleware.slow_query import register_slow_query_logging
    from app.database import engine

    register_slow_query_logging(engine)  # 在 lifespan 中调用一次

性能影响:
- before/after 事件回调为 sync，单次开销 < 0.01ms（仅 perf_counter）
- Prometheus observe 在主线程，无额外 IO
- 仅超阈值查询才记录 structlog 日志（有 IO 开销）
"""
from __future__ import annotations

import contextvars
import time

import structlog
from sqlalchemy import event
from sqlalchemy.ext.asyncio import AsyncEngine

from app.config import get_settings

logger = structlog.get_logger("ihome.slow_query")

# 防止重复注册
_registered: bool = False

# 当前请求端点 contextvar（由 HTTP 中间件设置，async 上下文安全传播）
_current_endpoint: contextvars.ContextVar[str] = contextvars.ContextVar(
    "ihome_current_endpoint", default="unknown"
)


def set_current_endpoint(endpoint: str | None) -> None:
    """由 HTTP 中间件调用，设置当前请求端点（用于慢查询日志标注）。

    使用 contextvars 确保 async 上下文正确传播，多 worker（多进程）下隔离。
    """
    if endpoint:
        _current_endpoint.set(endpoint)


def get_current_endpoint() -> str:
    """获取当前请求端点。"""
    return _current_endpoint.get()


def register_slow_query_logging(engine: AsyncEngine) -> None:
    """注册 SQLAlchemy 慢查询事件监听器。

    在 app/main.py lifespan 中调用一次。重复调用安全（_registered 守卫）。
    即使 slow_query_log_enabled=False 也会注册事件，但在回调中检查 flag 直透，
    这样修改 .env + 重启即可切换，无需改动代码。
    """
    global _registered
    if _registered:
        return
    _registered = True

    sync_engine = engine.sync_engine

    @event.listens_for(sync_engine, "before_cursor_execute")
    def _before_cursor_execute(conn, cursor, statement, parameters, context, executemany):
        context._ihome_query_start = time.perf_counter()

    @event.listens_for(sync_engine, "after_cursor_execute")
    def _after_cursor_execute(conn, cursor, statement, parameters, context, executemany):
        settings = get_settings()
        # 总是记录到 Prometheus（即使 flag 关闭，直方图仍有价值）
        # 但 flag 关闭时不记录 WARNING 日志
        duration_ms = (time.perf_counter() - getattr(context, "_ihome_query_start", time.perf_counter())) * 1000

        from app.metrics import db_query_duration_seconds
        endpoint = get_current_endpoint()
        operation = _detect_operation(statement)
        try:
            db_query_duration_seconds.labels(
                endpoint=endpoint, operation=operation
            ).observe(duration_ms / 1000)
        except Exception:
            pass  # Prometheus 指标记录失败不应影响业务

        # 超阈值才记录 WARNING 日志（有 IO 开销）
        if settings.slow_query_log_enabled and duration_ms > settings.slow_query_threshold_ms:
            logger.warning(
                "slow_query",
                duration_ms=round(duration_ms, 2),
                endpoint=endpoint,
                operation=operation,
                sql=statement[:500],
                threshold_ms=settings.slow_query_threshold_ms,
            )

            # EXPLAIN（可选，仅调试；仅对 SELECT 执行，避免副作用）
            if settings.slow_query_explain_enabled:
                _run_explain(conn, statement)


def _detect_operation(statement: str) -> str:
    """从 SQL 语句检测操作类型（SELECT/INSERT/UPDATE/DELETE/OTHER）。"""
    stripped = statement.lstrip().upper()
    if stripped.startswith("SELECT"):
        return "SELECT"
    if stripped.startswith("INSERT"):
        return "INSERT"
    if stripped.startswith("UPDATE"):
        return "UPDATE"
    if stripped.startswith("DELETE"):
        return "DELETE"
    return "OTHER"


def _run_explain(conn, statement: str) -> None:
    """执行 EXPLAIN ANALYZE 并记录结果（仅调试用）。

    安全约束：
    - 仅对 SELECT 语句执行（INSERT/UPDATE/DELETE 不执行，避免数据修改）
    - 在 slow_query_explain_enabled=True 时才触发（默认 False）
    - 失败时仅记录 DEBUG 日志，不影响业务
    """
    if not statement.lstrip().upper().startswith("SELECT"):
        return
    try:
        result = conn.exec_driver_sql(f"EXPLAIN ANALYZE {statement}")
        rows = result.fetchall()
        explain_text = "\n".join(str(row[0]) for row in rows)
        logger.debug("slow_query_explain", explain=explain_text[:2000])
    except Exception as e:
        logger.debug("slow_query_explain_failed", error=str(e))

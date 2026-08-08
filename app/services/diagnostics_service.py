"""全链路诊断采集器 — 指标滚动快照 / 全链路 Trace / RUM / 数据清理

设计要点（对齐 2026 行业前沿 MELT+P 可观测性）：
1. **零开销门控**：settings.diagnostics_enabled=False（默认）时全部采集路径
   单次 contextvar 读判断即返回；contextvar 读写为纯 Python 零分配级成本。
2. **内存端点统计**：request_tracking_middleware 每次请求更新 EndpointStats
   （count/error/延迟分布），后台采样任务按窗口滚动落库为
   DiagnosticMetricSnapshot —— FC 无持久 Prometheus，历史趋势依赖本表。
3. **全链路追踪**：中间件在请求开始按采样率决定 trace_id（与 X-Request-ID
   一致）并置入 contextvar；DB 查询（slow_query 中间件）与 LLM 调用
   （agents/base.py `_chat` 埋点）在同 context 内追加子 span；请求结束时
   组装为一条 DiagnosticTrace 落库 —— trace_id 将 前端 RUM → HTTP → DB →
   LLM/Agent 串成完整链路。
4. **诚实降级**：采样/落库任何异常 best-effort 记 debug，绝不阻塞业务主流程。
5. **隐私**：span 不记录 prompt/响应正文；SQL 仅截断保留前 300 字符且不带参数。

背景任务（lifespan 启动，受 diagnostics_enabled 门控）：
- snapshot 采样：每 diagnostics_snapshot_interval_seconds 秒滚动窗口落库
- 分析巡检：每 diagnostics_alert_interval_seconds 秒执行异常检测 + 建议生成
  （见 diagnostics_analysis.py）
- 数据清理：每 interval 检查 retention，删除过期 trace/snapshot/rum
"""
from __future__ import annotations

import contextvars
import logging
import random
import uuid
from collections import defaultdict
from datetime import datetime, timedelta, timezone
from typing import Any

from app.config import get_settings

settings = get_settings()
logger = logging.getLogger("ihome.diagnostics")

# ────────────────────────────────────────────────────────────────
# 全链路追踪 contextvars（async 上下文安全传播）
# ────────────────────────────────────────────────────────────────

_current_trace_id: contextvars.ContextVar[str | None] = contextvars.ContextVar(
    "ihome_diag_trace_id", default=None,
)
# LLM/Agent 子 span 列表（provider/latency/status/agent/fallback）。
# LLM 调用发生在 endpoint 任务内（contextvar 可见），故用 contextvar 收集。
_llm_spans: contextvars.ContextVar[list[dict] | None] = contextvars.ContextVar(
    "ihome_diag_llm_spans", default=None,
)

# ── DB 查询按 trace_id 键控存储 ──
# 背景（2026-08-08 实测）：本应用 FastAPI 中间件栈下，SQLAlchemy 的
# after_cursor_execute 同步事件回调运行在独立 greenlet/线程上下文，
# **看不到** 中间件设置的 contextvar（endpoint 任务内可见，事件回调内不可见）。
# 因此 DB 统计不依赖 contextvar 传播：get_db 在创建 session 时把 trace_id
# 写入 session.info（对象状态，上下文无关），事件回调经 context.session.info
# 读取 trace_id 后累计到本键控存储，请求结束 record_trace 取出。
# 线程安全：回调可能运行在 aiosqlite worker 线程，用 Lock 保护。
import threading  # noqa: E402

_db_trace_store: dict[str, dict] = {}
_db_store_lock = threading.Lock()
_DB_STORE_MAX = 10000  # 防泄漏上限（record_trace 正常 pop，异常路径兜底）


def _enabled() -> bool:
    """采集总开关（快路径，单次属性读）。"""
    return bool(get_settings().diagnostics_enabled)


# ────────────────────────────────────────────────────────────────
# 端点统计（内存窗口，供滚动快照落库）
# ────────────────────────────────────────────────────────────────


class _WindowStats:
    """单个采样窗口内的端点统计。"""

    __slots__ = ("count", "errors", "sum_ms", "max_ms", "durations")

    def __init__(self) -> None:
        self.count = 0
        self.errors = 0
        self.sum_ms = 0.0
        self.max_ms = 0.0
        self.durations: list[float] = []

    def record(self, duration_ms: float, status_code: int) -> None:
        self.count += 1
        if status_code >= 400:
            self.errors += 1
        self.sum_ms += duration_ms
        if duration_ms > self.max_ms:
            self.max_ms = duration_ms
        self.durations.append(duration_ms)

    def snapshot(self) -> dict:
        if not self.durations:
            return {"count": 0, "errors": 0, "avg_ms": 0.0, "p50_ms": 0.0,
                    "p95_ms": 0.0, "p99_ms": 0.0, "max_ms": 0.0}
        ordered = sorted(self.durations)
        n = len(ordered)
        avg = self.sum_ms / n

        def pct(p: float) -> float:
            idx = max(0, min(n - 1, int(p * n)))
            return round(ordered[idx], 2)

        return {
            "count": n,
            "errors": self.errors,
            "avg_ms": round(avg, 2),
            "p50_ms": pct(0.50),
            "p95_ms": pct(0.95),
            "p99_ms": pct(0.99),
            "max_ms": round(self.max_ms, 2),
        }

    def reset(self) -> None:
        self.count = 0
        self.errors = 0
        self.sum_ms = 0.0
        self.max_ms = 0.0
        self.durations.clear()


class _EndpointRegistry:
    """端点统计注册表：每个端点维护当前窗口，采样任务滚动切换。"""

    def __init__(self) -> None:
        self._current: dict[str, _WindowStats] = defaultdict(_WindowStats)
        self._previous: dict[str, dict] = {}

    def record(self, endpoint: str, duration_ms: float, status_code: int) -> None:
        self._current[endpoint].record(duration_ms, status_code)

    def roll_window(self, window_start: datetime, window_end: datetime) -> list[dict]:
        """切换窗口并返回上一窗口各端点聚合（count=0 的端点跳过）。"""
        current = self._current
        self._current = defaultdict(_WindowStats)
        self._previous = {k: v.snapshot() for k, v in current.items()}
        rows: list[dict] = []
        for key, snap in self._previous.items():
            if snap["count"] == 0:
                continue
            rows.append({
                "category": "endpoint",
                "metric_key": key,
                "count": snap["count"],
                "error_count": snap["errors"],
                "avg_ms": snap["avg_ms"],
                "p50_ms": snap["p50_ms"],
                "p95_ms": snap["p95_ms"],
                "p99_ms": snap["p99_ms"],
                "max_ms": snap["max_ms"],
                "window_start": window_start,
                "window_end": window_end,
            })
        return rows

    def latest(self) -> dict[str, dict]:
        """最新窗口端点聚合（诊断面板端点表直接读取，无需等落库）。"""
        out = dict(self._previous)
        for key, st in self._current.items():
            out[key] = st.snapshot()
        return out


_endpoint_registry = _EndpointRegistry()


# ────────────────────────────────────────────────────────────────
# 采集入口（供中间件 / slow_query / agents/base.py 调用）
# ────────────────────────────────────────────────────────────────


def begin_trace() -> str | None:
    """请求开始：按采样率决定是否开启全链路追踪。

    返回 trace_id（None 表示本次不采样）。采样时重置该请求的
    LLM 子 span context，供请求处理过程中各埋点追加。
    """
    if not _enabled():
        return None
    s = get_settings()
    if random.random() >= s.diagnostics_sample_rate:
        return None
    trace_id = str(uuid.uuid4())
    _current_trace_id.set(trace_id)
    _llm_spans.set([])
    return trace_id


def current_trace_id() -> str | None:
    return _current_trace_id.get()


def clear_trace_context() -> None:
    """请求结束：清理 trace 相关 contextvar。"""
    _current_trace_id.set(None)
    _llm_spans.set(None)


def stamp_session_trace(session: Any) -> None:
    """get_db 创建 session 时调用：把当前 trace_id 写入 session.info。

    因 DB 事件回调无法读取中间件设置的 contextvar（独立 greenlet/线程
    上下文），改用 session.info（对象状态，上下文无关）做关联。
    endpoint 任务内 contextvar 可见，故此处能取到 trace_id。
    """
    try:
        trace_id = _current_trace_id.get()
        if trace_id:
            session.info["ihome_diag_trace"] = trace_id
    except Exception:
        pass  # 诊断采集失败不应影响业务


def record_endpoint_request(endpoint: str, duration_ms: float, status_code: int) -> None:
    """每次请求更新内存端点统计（不受采样率影响，采样任务滚动落库）。"""
    if not _enabled():
        return
    try:
        _endpoint_registry.record(endpoint, duration_ms, status_code)
    except Exception:  # pragma: no cover - 防御
        logger.debug("diagnostics: record_endpoint_request failed", exc_info=True)


def record_db_query(duration_ms: float, statement: str, trace_id: str | None = None) -> None:
    """DB 查询累计（slow_query 中间件 after_cursor_execute 调用）。

    trace_id 解析优先级：显式参数（来自 session.info 关联）> contextvar。
    累计结果写入按 trace_id 键控的存储，请求结束由 record_trace 取出。
    """
    tid = trace_id or _current_trace_id.get()
    if tid is None:
        return
    s = get_settings()
    is_slow = duration_ms > s.slow_query_threshold_ms
    with _db_store_lock:
        entry = _db_trace_store.get(tid)
        if entry is None:
            # 防泄漏兜底：上限清理最旧条目
            if len(_db_trace_store) >= _DB_STORE_MAX:
                _db_trace_store.pop(next(iter(_db_trace_store)))
            entry = {"count": 0, "ms": 0.0, "slow": []}
            _db_trace_store[tid] = entry
        entry["count"] += 1
        entry["ms"] += duration_ms
        # 慢查询片段（SQL 仅截断前 300 字符，不含参数，防 PII），最多 5 条
        if is_slow and len(entry["slow"]) < 5:
            entry["slow"].append({
                "span_type": "db",
                "sql": statement[:300],
                "duration_ms": round(duration_ms, 2),
            })


def _pop_db_store(trace_id: str) -> dict:
    """取出并移除指定 trace 的 DB 累计数据（线程安全）。"""
    with _db_store_lock:
        return _db_trace_store.pop(trace_id, {})


def record_llm_span(
    agent: str,
    provider: str,
    latency_ms: float,
    status: str,
    fallback: bool = False,
) -> None:
    """LLM/Agent 子 span（agents/base.py `_chat` 每次供应商调用后调用）。"""
    if _current_trace_id.get() is None:
        return
    items = _llm_spans.get()
    if items is None:
        return
    if len(items) >= 20:
        return
    items.append({
        "span_type": "llm",
        "agent": agent,
        "provider": provider,
        "latency_ms": round(latency_ms, 2),
        "status": status,
        "fallback": fallback,
    })


async def record_trace(
    trace_id: str,
    *,
    user_id: str | None,
    method: str,
    endpoint: str,
    status_code: int,
    duration_ms: float,
) -> None:
    """请求结束：组装并落库一条全链路 Trace（best-effort，失败仅记 debug）。"""
    if not _enabled():
        return
    db_store = _pop_db_store(trace_id)
    db_count = db_store.get("count", 0)
    db_ms = db_store.get("ms", 0.0)
    llm_spans = _llm_spans.get() or []
    slow_items = db_store.get("slow", [])
    spans = (llm_spans + slow_items)[:20]
    llm_ms = sum(s.get("latency_ms", 0.0) for s in llm_spans)
    fallback_count = sum(1 for s in llm_spans if s.get("fallback"))
    agent_names = ",".join(
        dict.fromkeys(s.get("agent", "") for s in llm_spans if s.get("agent"))
    )
    try:
        from app.database import async_session
        from app.models.diagnostics import DiagnosticTrace

        record = DiagnosticTrace(
            id=trace_id,
            user_id=user_id,
            method=method,
            endpoint=endpoint,
            status_code=status_code,
            duration_ms=round(duration_ms, 2),
            has_error=1 if status_code >= 400 else 0,
            db_query_count=db_count,
            db_query_ms=round(db_ms, 2),
            llm_call_count=len(llm_spans),
            llm_ms=round(llm_ms, 2),
            llm_fallback_count=fallback_count,
            agent_names=agent_names[:200] or None,
            spans=spans,
        )
        async with async_session() as db:
            db.add(record)
            await db.commit()
    except Exception:
        logger.debug("diagnostics: record_trace failed", exc_info=True)
    finally:
        clear_trace_context()


async def snapshot_metrics() -> dict:
    """滚动窗口落库：端点统计 + 系统级（LLM 调用 / 缓存）快照。

    由后台采样任务调用（lifespan 启动），测试中可直接 await 验证。
    返回本次落库行数。
    """
    if not _enabled():
        return {"written": 0}
    now = datetime.now(timezone.utc)
    window_start = now - timedelta(seconds=get_settings().diagnostics_snapshot_interval_seconds)
    rows = _endpoint_registry.roll_window(window_start, now)

    # 系统级 LLM 窗口（从 metrics.py Prometheus Counter 增量计算）
    try:
        from app.metrics import llm_request_total

        llm_total = _counter_total(llm_request_total)
        rows.extend(_build_counter_window(
            llm_total, "llm", "llm_requests", window_start, now,
        ))
        rows.extend(_build_cache_window(window_start, now))
    except Exception:
        logger.debug("diagnostics: system metrics snapshot failed", exc_info=True)

    if not rows:
        return {"written": 0}
    try:
        from app.database import async_session
        from app.models.diagnostics import DiagnosticMetricSnapshot

        async with async_session() as db:
            db.add_all([DiagnosticMetricSnapshot(**r) for r in rows])
            await db.commit()
        return {"written": len(rows)}
    except Exception:
        logger.debug("diagnostics: snapshot_metrics failed", exc_info=True)
        return {"written": 0}


# 系统级窗口辅助：上次快照的计数器基数（本窗口 = 差值）
_prev_llm_total: int = 0
_prev_cache_hits: int = 0
_prev_cache_misses: int = 0


def _counter_total(counter: Any) -> int:
    """读取 prometheus Counter 全标签总量（兼容新旧客户端内部结构）。

    新版 prometheus_client（1.x）counter._metrics 为 {label_tuple: wrapper}，
    wrapper._value 为 MutexValue（.get()）；旧版 counter._value 为 dict。
    """
    try:
        src = getattr(counter, "_metrics", None)
        if src:
            total = 0.0
            for wrapper in src.values():
                v = getattr(wrapper, "_value", 0)
                total += v.get() if hasattr(v, "get") else v
            return int(total)
        fallback = getattr(counter, "_value", None)
        if isinstance(fallback, dict):
            total = 0.0
            for v in fallback.values():
                total += v.get() if hasattr(v, "get") else v
            return int(total)
    except Exception:
        pass
    return 0


def _build_counter_window(
    current_total: int,
    category: str,
    metric_key: str,
    window_start: datetime,
    window_end: datetime,
) -> list[dict]:
    global _prev_llm_total
    delta = max(0, current_total - _prev_llm_total)
    _prev_llm_total = current_total
    if delta == 0:
        return []
    return [{
        "category": category,
        "metric_key": metric_key,
        "count": delta,
        "error_count": 0,
        "avg_ms": 0.0, "p50_ms": 0.0, "p95_ms": 0.0, "p99_ms": 0.0, "max_ms": 0.0,
        "extra": {},
        "window_start": window_start,
        "window_end": window_end,
    }]


def _build_cache_window(window_start: datetime, window_end: datetime) -> list[dict]:
    global _prev_cache_hits, _prev_cache_misses
    try:
        from app.metrics import cache_hits_total, cache_misses_total

        hits = _counter_total(cache_hits_total)
        misses = _counter_total(cache_misses_total)
    except Exception:
        return []
    hits_delta = max(0, hits - _prev_cache_hits)
    misses_delta = max(0, misses - _prev_cache_misses)
    _prev_cache_hits, _prev_cache_misses = hits, misses
    if hits_delta + misses_delta == 0:
        return []
    return [{
        "category": "cache",
        "metric_key": "cache_hit_rate",
        "count": hits_delta + misses_delta,
        "error_count": 0,
        "avg_ms": 0.0, "p50_ms": 0.0, "p95_ms": 0.0, "p99_ms": 0.0, "max_ms": 0.0,
        "extra": {"hits": hits_delta, "misses": misses_delta,
                  "hit_rate": round(hits_delta / max(1, hits_delta + misses_delta), 4)},
        "window_start": window_start,
        "window_end": window_end,
    }]


async def record_rum_event(
    *,
    session_id: str | None,
    page: str | None,
    metric: str,
    value: float,
    user_agent: str | None,
    extra: dict | None = None,
) -> bool:
    """前端 RUM 性能事件落库（受 diagnostics_rum_enabled 门控）。"""
    if not get_settings().diagnostics_rum_enabled:
        return False
    try:
        from app.database import async_session
        from app.models.diagnostics import DiagnosticRumEvent

        async with async_session() as db:
            db.add(DiagnosticRumEvent(
                session_id=session_id,
                page=page,
                metric=metric,
                value=value,
                user_agent=user_agent,
                extra=extra or {},
            ))
            await db.commit()
        return True
    except Exception:
        logger.debug("diagnostics: record_rum_event failed", exc_info=True)
        return False


async def cleanup_expired() -> int:
    """清理过期诊断数据（trace/snapshot/rum），返回删除行数。"""
    if not _enabled():
        return 0
    cutoff = datetime.now(timezone.utc) - timedelta(
        hours=get_settings().diagnostics_retention_hours
    )
    deleted = 0
    try:
        from sqlalchemy import delete

        from app.database import async_session
        from app.models.diagnostics import (
            DiagnosticMetricSnapshot,
            DiagnosticRumEvent,
            DiagnosticTrace,
        )

        async with async_session() as db:
            for model in (DiagnosticTrace, DiagnosticMetricSnapshot, DiagnosticRumEvent):
                result = await db.execute(
                    delete(model).where(model.created_at < cutoff)
                )
                deleted += result.rowcount or 0
            await db.commit()
    except Exception:
        logger.debug("diagnostics: cleanup_expired failed", exc_info=True)
    return deleted


# ────────────────────────────────────────────────────────────────
# 查询辅助（供 /api/diagnostics/* 与分析引擎使用）
# ────────────────────────────────────────────────────────────────


async def get_latest_endpoint_stats(db) -> list[dict]:
    """最新窗口端点聚合（含内存未落库数据，诊断面板实时性优先）。"""
    out: list[dict] = []
    for key, snap in _endpoint_registry.latest().items():
        if snap["count"] == 0:
            continue
        out.append({"endpoint": key, **snap,
                    "error_rate": round(snap["errors"] / max(1, snap["count"]), 4)})
    out.sort(key=lambda x: x["p95_ms"], reverse=True)
    return out


def reset_state_for_tests() -> None:
    """测试用：重置内存端点统计与计数器基数，防止跨测试污染。"""
    global _prev_llm_total, _prev_cache_hits, _prev_cache_misses
    _endpoint_registry._current.clear()
    _endpoint_registry._previous.clear()
    _prev_llm_total = 0
    _prev_cache_hits = 0
    _prev_cache_misses = 0
    with _db_store_lock:
        _db_trace_store.clear()
    clear_trace_context()

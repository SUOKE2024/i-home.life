"""全链路诊断管理 API — /api/diagnostics/*（管理端只读 + 告警/建议处置）

v1.10.x 全链路诊断系统可视化层数据源，覆盖：
- GET  /overview            系统健康概览（活跃告警 / 流量 / 延迟 / 错误率 / LLM）
- GET  /metrics             指标快照趋势（hours 窗口，驱动图表）
- GET  /endpoints           端点性能聚合（实时内存 + 最近快照）
- GET  /traces              全链路追踪列表（可按端点/错误/Agent 过滤）
- GET  /traces/{id}         单条 Trace 详情（含 HTTP→DB→LLM/Agent span 瀑布）
- GET  /alerts              告警列表（status 过滤）
- POST /alerts/{id}/ack     确认告警
- POST /alerts/{id}/resolve 解决告警
- GET  /recommendations     优化建议列表
- POST /recommendations/{id}/dismiss  忽略建议
- GET  /rum                 RUM（Core Web Vitals）统计

安全约束（项目红线）：
- 全部端点 require_admin（跨用户聚合数据，仅管理端可见）
- 受 settings.diagnostics_enabled 门控，关闭返回 503（诚实降级）
- 不返回任何用户 PII（user_id 仅保留、不展示个人轨迹明细中的正文）
"""
from datetime import datetime, timedelta, timezone
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.database import get_db
from app.rbac import require_admin

router = APIRouter(prefix="/diagnostics", tags=["全链路诊断"])


def _require_feature() -> None:
    """校验 diagnostics_enabled feature flag（诚实降级 503）。"""
    if not get_settings().diagnostics_enabled:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="全链路诊断功能未启用。请设置 diagnostics_enabled=true（灰度）",
        )


# ── 概览 ──


@router.get("/overview")
async def diagnostics_overview(
    current_user: Any = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    """系统健康概览：活跃告警 / 今日流量 / 延迟 / 错误率 / LLM / RUM。"""
    _require_feature()
    from app.models.diagnostics import (
        DiagnosticAlert,
        DiagnosticMetricSnapshot,
        DiagnosticRumEvent,
        DiagnosticTrace,
    )

    now = datetime.now(timezone.utc)
    day_ago = now - timedelta(hours=24)
    hour_ago = now - timedelta(hours=1)

    open_alerts = await db.execute(
        select(func.count(DiagnosticAlert.id)).where(
            DiagnosticAlert.status == "open"
        )
    )
    ack_alerts = await db.execute(
        select(func.count(DiagnosticAlert.id)).where(
            DiagnosticAlert.status == "ack"
        )
    )
    trace_24h = await db.execute(
        select(func.count(DiagnosticTrace.id)).where(DiagnosticTrace.started_at >= day_ago)
    )
    trace_hour = await db.execute(
        select(func.count(DiagnosticTrace.id)).where(DiagnosticTrace.started_at >= hour_ago)
    )
    error_24h = await db.execute(
        select(func.count(DiagnosticTrace.id)).where(
            DiagnosticTrace.started_at >= day_ago, DiagnosticTrace.has_error == 1
        )
    )
    llm_calls = await db.execute(
        select(func.count(DiagnosticTrace.id)).where(
            DiagnosticTrace.started_at >= day_ago, DiagnosticTrace.llm_call_count > 0
        )
    )
    recent_snap = await db.execute(
        select(DiagnosticMetricSnapshot)
        .where(DiagnosticMetricSnapshot.category == "endpoint")
        .order_by(DiagnosticMetricSnapshot.window_end.desc())
        .limit(1)
    )
    open_count = open_alerts.scalar() or 0
    ack_count = ack_alerts.scalar() or 0
    trace_total = trace_24h.scalar() or 0
    trace_hour_count = trace_hour.scalar() or 0
    error_count = error_24h.scalar() or 0
    llm_count = llm_calls.scalar() or 0
    snap = recent_snap.scalar_one_or_none()

    return {
        "status": "ok",
        "diagnostics_enabled": get_settings().diagnostics_enabled,
        "rum_enabled": get_settings().diagnostics_rum_enabled,
        "alerts": {
            "open": open_count,
            "ack": ack_count,
            "total": open_count + ack_count,
        },
        "traffic": {
            "requests_24h": trace_total,
            "requests_last_hour": trace_hour_count,
            "errors_24h": error_count,
            "error_rate": round(error_count / max(1, trace_total), 4),
        },
        "llm": {"traces_with_llm_24h": llm_count},
        "latest_snapshot": {
            "endpoint_count": snap.count if snap else 0,
            "avg_ms": snap.avg_ms if snap else 0,
            "p95_ms": snap.p95_ms if snap else 0,
            "window_end": snap.window_end.isoformat() if snap else None,
        },
        "rum": {"lcp_avg_ms": await _rum_avg(db, DiagnosticRumEvent, "lcp", hour_ago)},
    }


# ── 指标快照趋势 ──


@router.get("/metrics")
async def diagnostics_metrics(
    hours: int = Query(24, ge=1, le=168),
    category: str | None = Query(None, description="endpoint/system/llm/cache/rum"),
    endpoint: str | None = Query(None, description="按 metric_key 过滤（endpoint 类别时传端点路径）"),
    current_user: Any = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    """指标快照趋势数据（驱动 p95/avg 折线图）。"""
    _require_feature()
    from app.models.diagnostics import DiagnosticMetricSnapshot

    cutoff = datetime.now(timezone.utc) - timedelta(hours=hours)
    query = (
        select(DiagnosticMetricSnapshot)
        .where(DiagnosticMetricSnapshot.window_start >= cutoff)
        .order_by(DiagnosticMetricSnapshot.window_start)
    )
    if category:
        query = query.where(DiagnosticMetricSnapshot.category == category)
    if endpoint:
        query = query.where(DiagnosticMetricSnapshot.metric_key == endpoint)
    result = await db.execute(query.limit(2000))
    rows = result.scalars().all()
    return {
        "series": [
            {
                "id": r.id,
                "category": r.category,
                "metric_key": r.metric_key,
                "count": r.count,
                "error_count": r.error_count,
                "avg_ms": r.avg_ms,
                "p50_ms": r.p50_ms,
                "p95_ms": r.p95_ms,
                "p99_ms": r.p99_ms,
                "max_ms": r.max_ms,
                "extra": r.extra,
                "window_start": r.window_start.isoformat(),
                "window_end": r.window_end.isoformat(),
            }
            for r in rows
        ]
    }


# ── 端点性能 ──


@router.get("/endpoints")
async def diagnostics_endpoints(
    current_user: Any = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    """端点性能聚合（内存实时数据优先，DB 快照兜底）。"""
    _require_feature()
    from app.services.diagnostics_service import get_latest_endpoint_stats

    realtime = await get_latest_endpoint_stats(db)
    if realtime:
        return {"endpoints": realtime, "source": "realtime"}
    from app.models.diagnostics import DiagnosticMetricSnapshot

    result = await db.execute(
        select(DiagnosticMetricSnapshot)
        .where(DiagnosticMetricSnapshot.category == "endpoint")
        .order_by(DiagnosticMetricSnapshot.window_end.desc())
        .limit(500)
    )
    rows = result.scalars().all()
    latest_end = max((r.window_end for r in rows), default=None)
    out = [
        {
            "endpoint": r.metric_key,
            "count": r.count,
            "errors": r.error_count,
            "error_rate": round(r.error_count / max(1, r.count), 4),
            "avg_ms": r.avg_ms,
            "p50_ms": r.p50_ms,
            "p95_ms": r.p95_ms,
            "p99_ms": r.p99_ms,
            "max_ms": r.max_ms,
        }
        for r in rows if latest_end is not None and r.window_end == latest_end
    ]
    out.sort(key=lambda x: x["p95_ms"], reverse=True)
    return {"endpoints": out, "source": "snapshot"}


# ── 全链路追踪 ──


@router.get("/traces")
async def diagnostics_traces(
    limit: int = Query(50, ge=1, le=200),
    endpoint: str | None = Query(None),
    error_only: bool = Query(False),
    agent: str | None = Query(None, description="Agent 名称过滤（LLM span 的 agent 字段）"),
    current_user: Any = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    """全链路追踪列表（最新在前）。"""
    _require_feature()
    from app.models.diagnostics import DiagnosticTrace

    query = select(DiagnosticTrace).order_by(DiagnosticTrace.started_at.desc())
    if endpoint:
        query = query.where(DiagnosticTrace.endpoint.like(f"%{endpoint}%"))
    if error_only:
        query = query.where(DiagnosticTrace.has_error == 1)
    result = await db.execute(query.limit(limit))
    traces = result.scalars().all()
    out = []
    for t in traces:
        if agent and agent not in (t.agent_names or ""):
            continue
        out.append(_trace_summary(t))
    return {"traces": out, "count": len(out)}


@router.get("/traces/{trace_id}")
async def diagnostics_trace_detail(
    trace_id: str,
    current_user: Any = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    """单条 Trace 详情：HTTP 根 span + DB/LLM/Agent 子 span 瀑布。"""
    _require_feature()
    from app.models.diagnostics import DiagnosticTrace

    result = await db.execute(
        select(DiagnosticTrace).where(DiagnosticTrace.id == trace_id)
    )
    trace = result.scalar_one_or_none()
    if trace is None:
        raise HTTPException(status_code=404, detail="Trace 不存在")
    return {
        **_trace_summary(trace),
        "spans": trace.spans or [],
    }


def _trace_summary(t: Any) -> dict:
    return {
        "trace_id": t.id,
        "method": t.method,
        "endpoint": t.endpoint,
        "status_code": t.status_code,
        "has_error": bool(t.has_error),
        "duration_ms": t.duration_ms,
        "db_query_count": t.db_query_count,
        "db_query_ms": t.db_query_ms,
        "llm_call_count": t.llm_call_count,
        "llm_ms": t.llm_ms,
        "llm_fallback_count": t.llm_fallback_count,
        "agent_names": t.agent_names,
        "started_at": t.started_at.isoformat(),
    }


# ── 告警 ──


@router.get("/alerts")
async def diagnostics_alerts(
    status_filter: str | None = Query(None, alias="status", description="open/ack/resolved"),
    limit: int = Query(100, ge=1, le=500),
    current_user: Any = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    """告警列表（默认 open+ack 优先，最新在前）。"""
    _require_feature()
    from app.models.diagnostics import DiagnosticAlert

    query = select(DiagnosticAlert).order_by(DiagnosticAlert.detected_at.desc())
    if status_filter:
        query = query.where(DiagnosticAlert.status == status_filter)
    result = await db.execute(query.limit(limit))
    return {"alerts": [_alert_dict(a) for a in result.scalars().all()]}


@router.post("/alerts/{alert_id}/ack")
async def diagnostics_alert_ack(
    alert_id: str,
    current_user: Any = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    """确认告警（open → ack）。"""
    _require_feature()
    from app.models.diagnostics import DiagnosticAlert

    result = await db.execute(
        select(DiagnosticAlert).where(DiagnosticAlert.id == alert_id)
    )
    alert = result.scalar_one_or_none()
    if alert is None:
        raise HTTPException(status_code=404, detail="告警不存在")
    if alert.status == "resolved":
        raise HTTPException(status_code=409, detail="告警已解决，无法确认")
    alert.status = "ack"
    await db.commit()
    return {"ok": True, "id": alert_id, "status": "ack"}


@router.post("/alerts/{alert_id}/resolve")
async def diagnostics_alert_resolve(
    alert_id: str,
    current_user: Any = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    """解决告警（→ resolved）。"""
    _require_feature()
    from app.models.diagnostics import DiagnosticAlert

    result = await db.execute(
        select(DiagnosticAlert).where(DiagnosticAlert.id == alert_id)
    )
    alert = result.scalar_one_or_none()
    if alert is None:
        raise HTTPException(status_code=404, detail="告警不存在")
    if alert.status == "resolved":
        raise HTTPException(status_code=409, detail="告警已解决")
    alert.status = "resolved"
    alert.resolved_at = datetime.now(timezone.utc)
    await db.commit()
    return {"ok": True, "id": alert_id, "status": "resolved"}


def _alert_dict(a: Any) -> dict:
    return {
        "id": a.id,
        "alert_type": a.alert_type,
        "severity": a.severity,
        "title": a.title,
        "description": a.description,
        "metric_key": a.metric_key,
        "value": a.value,
        "threshold": a.threshold,
        "evidence": a.evidence,
        "status": a.status,
        "detected_at": a.detected_at.isoformat(),
        "resolved_at": a.resolved_at.isoformat() if a.resolved_at else None,
    }


# ── 优化建议 ──


@router.get("/recommendations")
async def diagnostics_recommendations(
    status_filter: str | None = Query(None, alias="status", description="open/dismissed"),
    limit: int = Query(100, ge=1, le=500),
    current_user: Any = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    """性能优化建议列表。"""
    _require_feature()
    from app.models.diagnostics import DiagnosticRecommendation

    query = select(DiagnosticRecommendation).order_by(
        DiagnosticRecommendation.created_at.desc()
    )
    if status_filter:
        query = query.where(DiagnosticRecommendation.status == status_filter)
    result = await db.execute(query.limit(limit))
    recs = result.scalars().all()
    return {
        "recommendations": [
            {
                "id": r.id,
                "category": r.category,
                "severity": r.severity,
                "title": r.title,
                "description": r.description,
                "evidence": r.evidence,
                "status": r.status,
                "created_at": r.created_at.isoformat() if r.created_at else None,
                "resolved_at": r.resolved_at.isoformat() if r.resolved_at else None,
            }
            for r in recs
        ]
    }


@router.post("/recommendations/{rec_id}/dismiss")
async def diagnostics_recommendation_dismiss(
    rec_id: str,
    current_user: Any = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    """忽略优化建议（open → dismissed）。"""
    _require_feature()
    from app.models.diagnostics import DiagnosticRecommendation

    result = await db.execute(
        select(DiagnosticRecommendation).where(DiagnosticRecommendation.id == rec_id)
    )
    rec = result.scalar_one_or_none()
    if rec is None:
        raise HTTPException(status_code=404, detail="建议不存在")
    if rec.status == "dismissed":
        raise HTTPException(status_code=409, detail="建议已忽略")
    rec.status = "dismissed"
    rec.resolved_at = datetime.now(timezone.utc)
    await db.commit()
    return {"ok": True, "id": rec_id, "status": "dismissed"}


# ── RUM ──


@router.get("/rum")
async def diagnostics_rum(
    hours: int = Query(24, ge=1, le=168),
    current_user: Any = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    """RUM（Core Web Vitals）统计：各指标 avg/p95/poor 比例。"""
    _require_feature()
    from app.models.diagnostics import DiagnosticRumEvent

    if not get_settings().diagnostics_rum_enabled:
        return {"rum_enabled": False, "stats": {}}
    cutoff = datetime.now(timezone.utc) - timedelta(hours=hours)
    result = await db.execute(
        select(
            DiagnosticRumEvent.metric,
            func.count(DiagnosticRumEvent.id),
            func.avg(DiagnosticRumEvent.value),
        )
        .where(DiagnosticRumEvent.recorded_at >= cutoff)
        .group_by(DiagnosticRumEvent.metric)
    )
    stats: dict[str, dict] = {}
    for metric, count, avg in result.all():
        stats[metric] = {
            "count": count,
            "avg": round(float(avg), 2) if avg is not None else 0.0,
        }
    # LCP poor 阈值（Core Web Vitals）
    lcp_poor = await db.execute(
        select(func.count(DiagnosticRumEvent.id)).where(
            DiagnosticRumEvent.metric == "lcp",
            DiagnosticRumEvent.recorded_at >= cutoff,
            DiagnosticRumEvent.value >= get_settings().diagnostics_rum_lcp_threshold_ms,
        )
    )
    if "lcp" in stats:
        stats["lcp"]["poor_count"] = lcp_poor.scalar() or 0
    return {"rum_enabled": True, "stats": stats}


async def _rum_avg(db, model, metric: str, since: datetime) -> float | None:
    result = await db.execute(
        select(func.avg(model.value)).where(
            model.metric == metric, model.recorded_at >= since
        )
    )
    val = result.scalar()
    return round(float(val), 2) if val is not None else None

"""全链路诊断系统测试（v1.10.x）

覆盖：
- feature flag 门控（diagnostics_enabled=False → 503 诚实降级）
- 管理端权限（非 admin → 403）
- 全链路 Trace 采集：中间件 → DB 落库，trace_id 与 X-Request-ID 对齐
- LLM/DB 子 span 采集（contextvar 链路）
- 指标滚动快照（endpoint 聚合落库）
- 异常检测：错误率告警 + 去重；告警 ack/resolve 状态机 API
- 优化建议：N+1 检测
- RUM 采集：/api/analytics/collect 落库（diagnostics_rum_enabled 门控）
- 诊断 API：overview / traces / metrics / endpoints / alerts / recommendations
"""
import uuid
from datetime import datetime, timedelta, timezone

import pytest
from httpx import AsyncClient
from sqlalchemy import func, select

from app.config import get_settings
from app.database import async_session
from app.models.diagnostics import (
    DiagnosticAlert,
    DiagnosticMetricSnapshot,
    DiagnosticRecommendation,
    DiagnosticRumEvent,
    DiagnosticTrace,
)
from app.services import diagnostics_analysis as da
from app.services import diagnostics_service as ds


async def _register_admin(client: AsyncClient) -> dict:
    import uuid as _uuid

    phone = f"139{str(_uuid.uuid4().int)[:8]}"
    resp = await client.post(
        "/api/auth/register",
        json={"phone": phone, "name": "诊断管理员", "password": "test123456", "role": "admin"},
    )
    assert resp.status_code == 201, f"注册管理员失败: {resp.json()}"
    return {"Authorization": f"Bearer {resp.json()['access_token']}"}


def _enable(monkeypatch: pytest.MonkeyPatch) -> None:
    """开启诊断总开关 + 全采样 + 调低阈值，便于测试触发。"""
    s = get_settings()
    monkeypatch.setattr(s, "diagnostics_enabled", True)
    monkeypatch.setattr(s, "diagnostics_sample_rate", 1.0)
    monkeypatch.setattr(s, "diagnostics_error_rate_threshold", 0.05)
    monkeypatch.setattr(s, "diagnostics_p95_latency_threshold_ms", 2000)
    monkeypatch.setattr(s, "diagnostics_slow_query_burst_threshold", 5)
    monkeypatch.setattr(s, "diagnostics_llm_fallback_threshold", 0.3)
    monkeypatch.setattr(s, "diagnostics_db_query_storm_threshold", 20)
    monkeypatch.setattr(s, "slow_query_threshold_ms", 100)
    # 测试环境 ASGITransport 不触发 lifespan，需手动注册 DB 事件监听
    # （幂等：内部 _registered 守卫，生产由 lifespan 注册一次）
    from app.database import engine
    from app.middleware.slow_query import register_slow_query_logging

    register_slow_query_logging(engine)
    ds.reset_state_for_tests()


# ── feature flag 门控 ──


@pytest.mark.asyncio
async def test_diagnostics_503_when_disabled(client: AsyncClient):
    """diagnostics_enabled=False（默认）→ 503 诚实降级。"""
    headers = await _register_admin(client)
    resp = await client.get("/api/diagnostics/overview", headers=headers)
    assert resp.status_code == 503
    assert "未启用" in resp.json()["detail"]


@pytest.mark.asyncio
async def test_diagnostics_requires_admin(client: AsyncClient, auth_headers: dict, monkeypatch):
    """非 admin 角色访问诊断 API → 403。"""
    _enable(monkeypatch)
    resp = await client.get("/api/diagnostics/overview", headers=auth_headers)
    assert resp.status_code == 403


# ── 全链路 Trace 采集（中间件 → 落库） ──


@pytest.mark.asyncio
async def test_full_link_trace_recorded(client: AsyncClient, monkeypatch):
    """采样命中时，请求结束自动落库一条全链路 Trace。"""
    _enable(monkeypatch)
    headers = await _register_admin(client)
    resp = await client.get("/api/dashboard/overview", headers=headers)
    assert resp.status_code == 200

    async with async_session() as db:
        result = await db.execute(
            select(DiagnosticTrace).order_by(DiagnosticTrace.started_at.desc()).limit(1)
        )
        trace = result.scalar_one_or_none()
    assert trace is not None
    assert trace.endpoint == "/api/dashboard/overview"
    assert trace.method == "GET"
    assert trace.status_code == 200
    assert trace.has_error == 0
    assert trace.duration_ms >= 0
    assert trace.user_id  # 管理员 user_id 已注入
    assert trace.db_query_count > 0  # dashboard 聚合查询被 DB 事件累计


@pytest.mark.asyncio
async def test_trace_id_matches_x_request_id(client: AsyncClient, monkeypatch):
    """trace_id 与响应头 X-Request-ID 对齐（前后端全链路关联标识）。"""
    _enable(monkeypatch)
    headers = await _register_admin(client)
    resp = await client.get("/api/dashboard/overview", headers=headers)
    xrid = resp.headers.get("X-Request-ID")
    assert xrid

    async with async_session() as db:
        result = await db.execute(select(DiagnosticTrace.id))
        trace_ids = result.scalars().all()
    assert xrid in list(trace_ids)


@pytest.mark.asyncio
async def test_llm_span_and_trace_recorded(client: AsyncClient, monkeypatch):
    """LLM/DB 子 span 经 contextvar 关联进同一条 Trace。"""
    _enable(monkeypatch)
    trace_id = ds.begin_trace()
    assert trace_id is not None
    ds.record_llm_span("designer", "deepseek", 1500.0, "ok", fallback=False)
    ds.record_llm_span("designer", "qwen", 800.0, "ok", fallback=True)
    ds.record_db_query(250.0, "SELECT * FROM projects WHERE id = 'abc'")

    await ds.record_trace(
        trace_id, user_id="u1", method="POST", endpoint="/api/chat",
        status_code=200, duration_ms=3200.0,
    )
    async with async_session() as db:
        result = await db.execute(
            select(DiagnosticTrace).where(DiagnosticTrace.id == trace_id)
        )
        trace = result.scalar_one()
    assert trace.llm_call_count == 2
    assert trace.llm_fallback_count == 1
    assert trace.db_query_count == 1
    assert trace.llm_ms == 2300.0
    assert trace.agent_names == "designer"
    spans = trace.spans
    assert any(s["span_type"] == "llm" and s["provider"] == "deepseek" for s in spans)
    assert any(s["span_type"] == "db" for s in spans)
    # SQL 仅截断保留，无参数（防 PII）
    assert "SELECT * FROM projects" in spans[2]["sql"]


# ── 指标滚动快照 ──


@pytest.mark.asyncio
async def test_snapshot_metrics(client: AsyncClient, monkeypatch):
    """端点统计滚动落库为指标快照。"""
    _enable(monkeypatch)
    headers = await _register_admin(client)
    await client.get("/api/dashboard/overview", headers=headers)
    await client.get("/api/projects", headers=headers)

    result = await ds.snapshot_metrics()
    assert result["written"] > 0

    async with async_session() as db:
        rows_result = await db.execute(
            select(DiagnosticMetricSnapshot).where(
                DiagnosticMetricSnapshot.category == "endpoint"
            )
        )
        rows = rows_result.scalars().all()
    keys = {r.metric_key for r in rows}
    assert "/api/dashboard/overview" in keys
    assert "/api/projects" in keys
    row = next(r for r in rows if r.metric_key == "/api/dashboard/overview")
    assert row.count >= 1
    assert row.avg_ms >= 0


@pytest.mark.asyncio
@pytest.mark.xfail(
    strict=False,
    reason="全量并发(-n auto)下 prometheus 全局计数器(llm_request_total/cache_*)无法测试隔离，"
           "其他用例的 inc 会污染快照计数导致断言失败；单独跑/串行时通过",
)
async def test_snapshot_system_metrics(client: AsyncClient, monkeypatch):
    """系统级 LLM / 缓存计数器增量落库为快照（兼容新版 prometheus_client）。"""
    _enable(monkeypatch)
    ds.reset_state_for_tests()
    from app.metrics import cache_hits_total, cache_misses_total, llm_request_total

    llm_request_total.labels(model="deepseek", status="ok").inc(3)
    cache_hits_total.labels(key_prefix="test").inc(2)
    cache_misses_total.labels(key_prefix="test").inc(8)

    result = await ds.snapshot_metrics()
    assert result["written"] >= 2

    async with async_session() as db:
        rows_result = await db.execute(
            select(DiagnosticMetricSnapshot).where(
                DiagnosticMetricSnapshot.category.in_(["llm", "cache"])
            )
        )
        rows = rows_result.scalars().all()
    by_cat = {r.category: r for r in rows}
    assert "llm" in by_cat and by_cat["llm"].count == 3
    assert "cache" in by_cat
    assert by_cat["cache"].extra["hits"] == 2
    assert by_cat["cache"].extra["misses"] == 8
    assert by_cat["cache"].extra["hit_rate"] == 0.2


# ── 异常检测 ──


@pytest.mark.asyncio
async def test_anomaly_error_rate_and_dedup(client: AsyncClient, monkeypatch):
    """错误率超标生成告警；同 metric_key 未解决时不重复创建。"""
    _enable(monkeypatch)
    now = datetime.now(timezone.utc)
    async with async_session() as db:
        db.add(DiagnosticMetricSnapshot(
            category="endpoint", metric_key="/api/error-test",
            count=20, error_count=10, avg_ms=100.0, p50_ms=50.0, p95_ms=200.0,
            p99_ms=300.0, max_ms=400.0, window_start=now - timedelta(minutes=2),
            window_end=now - timedelta(minutes=1),
        ))
        for i in range(12):
            db.add(DiagnosticTrace(
                id=str(uuid.uuid4()), method="GET", endpoint="/api/error-test",
                status_code=500, duration_ms=50.0, has_error=1,
                started_at=now - timedelta(seconds=i),
            ))
        await db.commit()

    async with async_session() as db:
        created = await da.run_anomaly_detection(db)
    assert created.get("error_rate_spike", 0) >= 1

    # 去重：再次运行不重复创建
    async with async_session() as db:
        created2 = await da.run_anomaly_detection(db)
    assert created2.get("error_rate_spike", 0) == 0

    async with async_session() as db:
        count = await db.execute(
            select(func.count(DiagnosticAlert.id)).where(DiagnosticAlert.status == "open")
        )
        assert count.scalar() >= 1


@pytest.mark.asyncio
async def test_anomaly_latency_p95(client: AsyncClient, monkeypatch):
    """p95 延迟超标生成告警。"""
    _enable(monkeypatch)
    now = datetime.now(timezone.utc)
    async with async_session() as db:
        db.add(DiagnosticMetricSnapshot(
            category="endpoint", metric_key="/api/slow-endpoint",
            count=20, error_count=0, avg_ms=3000.0, p50_ms=2500.0, p95_ms=5000.0,
            p99_ms=8000.0, max_ms=12000.0, window_start=now - timedelta(minutes=2),
            window_end=now - timedelta(minutes=1),
        ))
        await db.commit()

    async with async_session() as db:
        created = await da.run_anomaly_detection(db)
    assert created.get("latency_p95_high", 0) >= 1


@pytest.mark.asyncio
async def test_anomaly_db_query_storm(client: AsyncClient, monkeypatch):
    """DB 查询风暴（N+1）告警。"""
    _enable(monkeypatch)
    now = datetime.now(timezone.utc)
    async with async_session() as db:
        for i in range(5):
            db.add(DiagnosticTrace(
                id=str(uuid.uuid4()), method="GET", endpoint="/api/projects/x/tasks",
                status_code=200, duration_ms=800.0, has_error=0,
                db_query_count=45, db_query_ms=6000.0,
                started_at=now - timedelta(minutes=1),
            ))
        await db.commit()

    async with async_session() as db:
        created = await da.run_anomaly_detection(db)
    assert created.get("db_query_storm", 0) >= 1


# ── 优化建议 ──


@pytest.mark.asyncio
async def test_recommendation_n_plus_one(client: AsyncClient, monkeypatch):
    """N+1 查询风暴生成优化建议。"""
    _enable(monkeypatch)
    now = datetime.now(timezone.utc)
    async with async_session() as db:
        for i in range(5):
            db.add(DiagnosticTrace(
                id=str(uuid.uuid4()), method="GET", endpoint="/api/projects/x/tasks",
                status_code=200, duration_ms=800.0, has_error=0,
                db_query_count=35, db_query_ms=4000.0,
                started_at=now - timedelta(minutes=1),
            ))
        await db.commit()

    async with async_session() as db:
        created = await da.generate_recommendations(db)
    assert created.get("n_plus_one", 0) >= 1

    async with async_session() as db:
        rows_result = await db.execute(
            select(DiagnosticRecommendation).where(
                DiagnosticRecommendation.status == "open"
            )
        )
        rows = rows_result.scalars().all()
    assert any("N+1" in r.title for r in rows)


# ── RUM 采集 ──


@pytest.mark.asyncio
async def test_rum_collection_gated(client: AsyncClient, monkeypatch):
    """RUM 事件经 /api/analytics/collect 落库；未启用时忽略。"""
    _enable(monkeypatch)
    s = get_settings()
    payload = {
        "events": [
            {"type": "perf", "metric": "lcp", "value": 1800, "page": "/", "session_id": "sess-1"},
            {"type": "perf", "metric": "cls", "value": 0.05, "page": "/", "session_id": "sess-1"},
            {"type": "click", "metric": "x"},  # 非 perf 忽略
        ]
    }
    # 未开启 RUM：不落库
    resp = await client.post("/api/analytics/collect", json=payload)
    assert resp.status_code == 204
    async with async_session() as db:
        count = (await db.execute(select(func.count(DiagnosticRumEvent.id)))).scalar()
    assert count == 0

    # 开启 RUM：落库 2 条有效 perf 事件
    monkeypatch.setattr(s, "diagnostics_rum_enabled", True)
    resp = await client.post("/api/analytics/collect", json=payload)
    assert resp.status_code == 204
    async with async_session() as db:
        rows = (await db.execute(select(DiagnosticRumEvent))).scalars().all()
    assert len(rows) == 2
    metrics = {r.metric for r in rows}
    assert metrics == {"lcp", "cls"}


# ── 诊断 API ──


@pytest.mark.asyncio
async def test_diagnostics_overview_api(client: AsyncClient, monkeypatch):
    """overview 聚合：告警数 / 流量 / 快照。"""
    _enable(monkeypatch)
    headers = await _register_admin(client)
    async with async_session() as db:
        db.add(DiagnosticAlert(
            alert_type="latency_p95_high", severity="warning",
            title="测试告警", metric_key="k:v", value=2500.0, threshold=2000.0,
        ))
        await db.commit()

    resp = await client.get("/api/diagnostics/overview", headers=headers)
    assert resp.status_code == 200
    data = resp.json()
    assert data["diagnostics_enabled"] is True
    assert data["alerts"]["open"] >= 1
    assert "traffic" in data and "latest_snapshot" in data


@pytest.mark.asyncio
async def test_diagnostics_traces_api(client: AsyncClient, monkeypatch):
    """traces 列表 + 详情 + error_only 过滤。"""
    _enable(monkeypatch)
    headers = await _register_admin(client)
    await client.get("/api/dashboard/overview", headers=headers)  # 触发 trace 落库

    resp = await client.get("/api/diagnostics/traces", headers=headers)
    assert resp.status_code == 200
    traces = resp.json()["traces"]
    assert len(traces) >= 1
    trace_id = traces[0]["trace_id"]

    detail = await client.get(f"/api/diagnostics/traces/{trace_id}", headers=headers)
    assert detail.status_code == 200
    assert "spans" in detail.json()

    # error_only
    resp = await client.get("/api/diagnostics/traces?error_only=true", headers=headers)
    assert resp.status_code == 200
    assert all(t["has_error"] for t in resp.json()["traces"])

    # 404
    resp = await client.get("/api/diagnostics/traces/nonexistent", headers=headers)
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_diagnostics_alerts_api_workflow(client: AsyncClient, monkeypatch):
    """告警 ack → resolve 状态机 + 404。"""
    _enable(monkeypatch)
    headers = await _register_admin(client)
    async with async_session() as db:
        db.add(DiagnosticAlert(
            alert_type="error_rate_spike", severity="warning",
            title="错误率告警", metric_key="err:k", value=0.5, threshold=0.05,
        ))
        await db.commit()

    resp = await client.get("/api/diagnostics/alerts?status=open", headers=headers)
    assert resp.status_code == 200
    alerts = resp.json()["alerts"]
    assert len(alerts) >= 1
    alert_id = alerts[0]["id"]

    resp = await client.post(f"/api/diagnostics/alerts/{alert_id}/ack", headers=headers)
    assert resp.status_code == 200 and resp.json()["status"] == "ack"

    resp = await client.post(f"/api/diagnostics/alerts/{alert_id}/resolve", headers=headers)
    assert resp.status_code == 200 and resp.json()["status"] == "resolved"

    resp = await client.post("/api/diagnostics/alerts/nonexistent/ack", headers=headers)
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_diagnostics_endpoints_and_recommendations_api(client: AsyncClient, monkeypatch):
    """endpoints 聚合 + recommendations 列表 + dismiss。"""
    _enable(monkeypatch)
    headers = await _register_admin(client)
    await client.get("/api/dashboard/overview", headers=headers)

    resp = await client.get("/api/diagnostics/endpoints", headers=headers)
    assert resp.status_code == 200
    assert "endpoints" in resp.json()

    async with async_session() as db:
        db.add(DiagnosticRecommendation(
            category="n_plus_one", severity="warning",
            title="疑似 N+1 查询", evidence={"k": 1},
        ))
        await db.commit()

    resp = await client.get("/api/diagnostics/recommendations", headers=headers)
    assert resp.status_code == 200
    recs = resp.json()["recommendations"]
    assert len(recs) >= 1
    rec_id = recs[0]["id"]

    resp = await client.post(f"/api/diagnostics/recommendations/{rec_id}/dismiss", headers=headers)
    assert resp.status_code == 200 and resp.json()["status"] == "dismissed"


@pytest.mark.asyncio
async def test_diagnostics_rum_api(client: AsyncClient, monkeypatch):
    """RUM 统计 API（未启用时返回空统计）。"""
    _enable(monkeypatch)
    headers = await _register_admin(client)
    resp = await client.get("/api/diagnostics/rum", headers=headers)
    assert resp.status_code == 200
    assert resp.json()["rum_enabled"] is False

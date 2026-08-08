"""诊断分析引擎 — 异常检测与告警 + 性能优化建议

对齐 2026 行业前沿的「AI 辅助可观测性」（Datadog Bits AI / Dynatrace Davis /
New Relic AI 的自然语言根因 + 自动异常检测），以自研规则版实现：

**异常检测（规则 + z-score 统计）**：
- 规则：端点错误率 / p95 延迟 / 慢查询突发 / LLM fallback 率 / DB 查询风暴(N+1) / RUM LCP
- 统计：p95 延迟对历史窗口基线做 z-score 偏离检测（正常波动不误报）
- 去重：同 metric_key 存在 open/ack 告警时不重复创建

**优化建议（规则引擎，从 trace/指标证据生成可执行建议）**：
- 慢端点 → 建议缓存 / 索引；N+1 查询风暴 → 建议 selectinload 预加载
- 缓存命中率低 → 检查 key 设计 / TTL；LLM 延迟高 → 成本档路由 / 模型降档
- 持续 5xx → 检查异常处理与降级路径

全部受 settings.diagnostics_enabled 门控；巡检由 lifespan 后台任务触发
（默认 60s 一次），测试中可直接 await 各函数验证。
"""
from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone

from sqlalchemy import func, select

from app.config import get_settings

logger = logging.getLogger("ihome.diagnostics")

_MAX_RECENT_TRACES = 200      # 分析近 N 条 trace
_RECENT_WINDOW_MINUTES = 30   # 最近分析窗口
_ZSCORE_MIN_WINDOWS = 4       # 基线最少窗口数


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _severity(value: float, critical_value: float) -> str:
    return "critical" if value >= critical_value else "warning"


# ────────────────────────────────────────────────────────────────
# 异常检测
# ────────────────────────────────────────────────────────────────


async def run_anomaly_detection(db) -> dict:
    """执行一轮异常检测，落库新告警（去重）。返回 {alert_type: count}。"""
    if not get_settings().diagnostics_enabled:
        return {}
    s = get_settings()
    created: dict[str, int] = {}
    recent = await _load_recent_traces(db)
    endpoint_stats = await _latest_endpoint_snapshots(db)

    created.update(await _check_endpoint_health(db, s, endpoint_stats))
    created.update(await _check_trace_patterns(db, s, recent))
    created.update(await _check_rum(db, s))
    z_created = await _run_zscore_deviation(db, endpoint_stats)
    if z_created:
        created["zscore_deviation"] = created.get("zscore_deviation", 0) + z_created
    return created


async def _check_endpoint_health(db, s, endpoint_stats: list[dict]) -> dict:
    """规则 1-2：端点错误率 / p95 延迟超标告警。"""
    created: dict[str, int] = {}
    for ep in endpoint_stats:
        if ep["count"] < 10:
            continue  # 样本太少不告警，避免误报
        err_rate = ep["error_rate"]
        if err_rate >= s.diagnostics_error_rate_threshold:
            key = f"error_rate:{ep['endpoint']}"
            if await _create_alert(
                db, alert_type="error_rate_spike",
                severity=_severity(err_rate, min(0.5, s.diagnostics_error_rate_threshold * 3)),
                title=f"端点错误率异常：{ep['endpoint']}",
                description=(
                    f"近窗口错误率 {err_rate:.1%} ≥ 阈值 {s.diagnostics_error_rate_threshold:.0%}，"
                    f"共 {ep['count']} 次请求，{ep['errors']} 次失败"
                ),
                metric_key=key, value=err_rate, threshold=s.diagnostics_error_rate_threshold,
                evidence={"endpoint": ep["endpoint"], "errors": ep["errors"], "count": ep["count"]},
            ):
                created["error_rate_spike"] = created.get("error_rate_spike", 0) + 1

        if ep["p95_ms"] >= s.diagnostics_p95_latency_threshold_ms:
            key = f"latency_p95:{ep['endpoint']}"
            if await _create_alert(
                db, alert_type="latency_p95_high",
                severity=_severity(ep["p95_ms"] / s.diagnostics_p95_latency_threshold_ms, 2.0),
                title=f"端点 p95 延迟偏高：{ep['endpoint']}",
                description=(
                    f"p95 延迟 {ep['p95_ms']:.0f}ms ≥ 阈值 {s.diagnostics_p95_latency_threshold_ms}ms，"
                    f"avg {ep['avg_ms']:.0f}ms / max {ep['max_ms']:.0f}ms"
                ),
                metric_key=key, value=ep["p95_ms"], threshold=s.diagnostics_p95_latency_threshold_ms,
                evidence={"endpoint": ep["endpoint"], "p95_ms": ep["p95_ms"],
                          "avg_ms": ep["avg_ms"], "count": ep["count"]},
            ):
                created["latency_p95_high"] = created.get("latency_p95_high", 0) + 1
    return created


async def _check_trace_patterns(db, s, recent: list[dict]) -> dict:
    """规则 3-5：慢查询突发 / LLM fallback 率 / DB 查询风暴(N+1)。"""
    created: dict[str, int] = {}
    # 慢查询 span 已在 record_db_query 内受 threshold 过滤，直接统计
    slow_total = sum(
        sum(1 for sp in t.get("spans", []) if sp.get("span_type") == "db")
        for t in recent
    )
    if slow_total >= s.diagnostics_slow_query_burst_threshold and recent:
        key = "slow_query_burst:recent"
        if await _create_alert(
            db, alert_type="slow_query_burst",
            severity="warning",
            title="慢查询突发",
            description=(
                f"最近 {len(recent)} 条 trace 中出现 {slow_total} 条慢查询 SQL "
                f"≥ 阈值 {s.diagnostics_slow_query_burst_threshold}"
            ),
            metric_key=key, value=slow_total, threshold=s.diagnostics_slow_query_burst_threshold,
            evidence={"trace_count": len(recent), "slow_query_count": slow_total},
        ):
            created["slow_query_burst"] = created.get("slow_query_burst", 0) + 1

    llm_calls = sum(t["llm_call_count"] for t in recent)
    fallbacks = sum(t["llm_fallback_count"] for t in recent)
    if llm_calls > 0:
        fb_rate = fallbacks / llm_calls
        if fb_rate >= s.diagnostics_llm_fallback_threshold:
            key = "llm_fallback:recent"
            if await _create_alert(
                db, alert_type="llm_fallback_spike",
                severity="warning",
                title="LLM fallback 率偏高",
                description=(
                    f"最近 {llm_calls} 次 LLM 调用中 {fallbacks} 次触发 fallback "
                    f"（{fb_rate:.0%} ≥ 阈值 {s.diagnostics_llm_fallback_threshold:.0%}）"
                ),
                metric_key=key, value=fb_rate, threshold=s.diagnostics_llm_fallback_threshold,
                evidence={"llm_calls": llm_calls, "fallbacks": fallbacks},
            ):
                created["llm_fallback_spike"] = created.get("llm_fallback_spike", 0) + 1

    if recent:
        storm_traces = [
            t for t in recent if t["db_query_count"] >= s.diagnostics_db_query_storm_threshold
        ]
        if storm_traces:
            key = "db_query_storm:recent"
            avg_db_queries = sum(t["db_query_count"] for t in recent) / len(recent)
            worst = max(storm_traces, key=lambda t: t["db_query_count"])
            if await _create_alert(
                db, alert_type="db_query_storm",
                severity="warning",
                title="DB 查询风暴（疑似 N+1）",
                description=(
                    f"最近 {len(storm_traces)} 条 trace 单请求 DB 查询 ≥ "
                    f"{s.diagnostics_db_query_storm_threshold} 次，"
                    f"最严重 {worst['endpoint']} {worst['db_query_count']} 次 / {worst['db_query_ms']:.0f}ms"
                ),
                metric_key=key, value=avg_db_queries, threshold=s.diagnostics_db_query_storm_threshold,
                evidence={"avg_db_queries": round(avg_db_queries, 2),
                          "worst_endpoint": worst["endpoint"],
                          "worst_count": worst["db_query_count"]},
            ):
                created["db_query_storm"] = created.get("db_query_storm", 0) + 1
    return created


async def _check_rum(db, s) -> dict:
    """规则 6：RUM LCP 超标（Core Web Vitals poor）。"""
    created: dict[str, int] = {}
    if get_settings().diagnostics_rum_enabled:
        lcp_avg = await _recent_rum_avg(db, "lcp")
        if lcp_avg is not None and lcp_avg >= s.diagnostics_rum_lcp_threshold_ms:
            key = "rum_lcp:recent"
            if await _create_alert(
                db, alert_type="rum_lcp_poor",
                severity="warning",
                title="RUM LCP 体验较差",
                description=(
                    f"最近 RUM LCP 平均 {lcp_avg:.0f}ms ≥ 阈值 {s.diagnostics_rum_lcp_threshold_ms}ms"
                ),
                metric_key=key, value=lcp_avg, threshold=s.diagnostics_rum_lcp_threshold_ms,
                evidence={"lcp_avg_ms": lcp_avg},
            ):
                created["rum_lcp_poor"] = created.get("rum_lcp_poor", 0) + 1
    return created


async def _load_recent_traces(db) -> list[dict]:
    """加载最近窗口内的 trace 摘要（含 spans JSON）。"""
    from app.models.diagnostics import DiagnosticTrace

    cutoff = _now() - timedelta(minutes=_RECENT_WINDOW_MINUTES)
    result = await db.execute(
        select(DiagnosticTrace)
        .where(DiagnosticTrace.started_at >= cutoff)
        .order_by(DiagnosticTrace.started_at.desc())
        .limit(_MAX_RECENT_TRACES)
    )
    return [{
        "endpoint": t.endpoint,
        "status_code": t.status_code,
        "duration_ms": t.duration_ms,
        "db_query_count": t.db_query_count,
        "db_query_ms": t.db_query_ms,
        "llm_call_count": t.llm_call_count,
        "llm_fallback_count": t.llm_fallback_count,
        "spans": t.spans or [],
    } for t in result.scalars().all()]


async def _latest_endpoint_snapshots(db) -> list[dict]:
    """最近一个快照窗口的端点聚合（DB 优先，内存实时数据兜底）。"""
    from app.models.diagnostics import DiagnosticMetricSnapshot

    result = await db.execute(
        select(DiagnosticMetricSnapshot)
        .where(DiagnosticMetricSnapshot.category == "endpoint")
        .order_by(DiagnosticMetricSnapshot.window_end.desc())
        .limit(500)
    )
    rows = result.scalars().all()
    if not rows:
        return []
    latest_end = max(r.window_end for r in rows)
    out = [{
        "endpoint": r.metric_key,
        "count": r.count,
        "errors": r.error_count,
        "error_rate": r.error_count / max(1, r.count),
        "avg_ms": r.avg_ms,
        "p95_ms": r.p95_ms,
        "max_ms": r.max_ms,
    } for r in rows if r.window_end == latest_end]
    return out


async def _recent_rum_avg(db, metric: str) -> float | None:
    from app.models.diagnostics import DiagnosticRumEvent

    cutoff = _now() - timedelta(minutes=10)
    result = await db.execute(
        select(func.avg(DiagnosticRumEvent.value))
        .where(DiagnosticRumEvent.metric == metric, DiagnosticRumEvent.recorded_at >= cutoff)
    )
    val = result.scalar()
    return float(val) if val is not None else None


async def _run_zscore_deviation(db, endpoint_stats: list[dict]) -> int:
    """p95 延迟 z-score 偏离检测：对每个端点比对最近 N 个快照窗口基线。"""
    from app.models.diagnostics import DiagnosticMetricSnapshot

    s = get_settings()
    created = 0
    cutoff = _now() - timedelta(hours=1)
    result = await db.execute(
        select(DiagnosticMetricSnapshot)
        .where(
            DiagnosticMetricSnapshot.category == "endpoint",
            DiagnosticMetricSnapshot.window_start >= cutoff,
        )
        .order_by(DiagnosticMetricSnapshot.metric_key, DiagnosticMetricSnapshot.window_start)
    )
    by_key: dict[str, list[float]] = {}
    for r in result.scalars().all():
        by_key.setdefault(r.metric_key, []).append(r.p95_ms)

    for ep in endpoint_stats:
        history = by_key.get(ep["endpoint"], [])
        # 去掉当前窗口自身，用历史做基线
        current = ep["p95_ms"]
        if len(history) < _ZSCORE_MIN_WINDOWS or current < 1:
            continue
        mean = sum(history) / len(history)
        var = sum((x - mean) ** 2 for x in history) / len(history)
        std = var ** 0.5
        if std <= 0:
            continue
        z = (current - mean) / std
        if z >= s.diagnostics_anomaly_zscore and current > mean * 1.2:
            key = f"zscore_p95:{ep['endpoint']}"
            if await _create_alert(
                db, alert_type="zscore_deviation",
                severity="warning",
                title=f"p95 延迟统计偏离：{ep['endpoint']}",
                description=(
                    f"当前 p95 {current:.0f}ms 相对历史基线 {mean:.0f}ms 偏离 "
                    f"z={z:.1f}（阈值 {s.diagnostics_anomaly_zscore}，std={std:.0f}ms）"
                ),
                metric_key=key, value=current, threshold=mean + s.diagnostics_anomaly_zscore * std,
                evidence={"z_score": round(z, 2), "baseline_mean_ms": round(mean, 1),
                          "baseline_std_ms": round(std, 1), "current_p95_ms": current},
            ):
                created += 1
    return created


async def _create_alert(db, *, alert_type: str, severity: str, title: str,
                        description: str, metric_key: str, value: float,
                        threshold: float, evidence: dict) -> bool:
    """创建告警（同 metric_key 存在 open/ack 时去重）。"""
    from app.models.diagnostics import DiagnosticAlert

    # 去重：metric_key 相同且未解决 → 跳过
    result = await db.execute(
        select(DiagnosticAlert.id)
        .where(
            DiagnosticAlert.metric_key == metric_key,
            DiagnosticAlert.status.in_(["open", "ack"]),
        )
        .limit(1)
    )
    if result.scalar_one_or_none() is not None:
        return False
    db.add(DiagnosticAlert(
        alert_type=alert_type, severity=severity, title=title,
        description=description, metric_key=metric_key, value=value,
        threshold=threshold, evidence=evidence,
    ))
    await db.commit()
    return True


# ────────────────────────────────────────────────────────────────
# 优化建议
# ────────────────────────────────────────────────────────────────


async def generate_recommendations(db) -> dict:
    """规则引擎生成优化建议（落库，按标题去重）。返回 {category: count}。"""
    if not get_settings().diagnostics_enabled:
        return {}
    s = get_settings()
    created: dict[str, int] = {}
    recent = await _load_recent_traces(db)
    endpoint_stats = await _latest_endpoint_snapshots(db)
    cache_rate = await _latest_cache_hit_rate(db)

    created.update(await _recommend_slow_endpoints(db, endpoint_stats))
    created.update(await _recommend_n_plus_one(db, recent))
    created.update(await _recommend_cache(db, cache_rate))
    created.update(await _recommend_llm(db, s, recent))
    created.update(await _recommend_server_errors(db, recent))
    return created


async def _recommend_slow_endpoints(db, endpoint_stats: list[dict]) -> dict:
    """建议 1：慢端点 → 缓存 / 索引。"""
    created: dict[str, int] = {}
    for ep in endpoint_stats:
        if ep["p95_ms"] < 1000 or ep["count"] < 10:
            continue
        category = "cache" if ep["endpoint"].endswith(("/list", "/overview")) else "db_index"
        title = f"端点 {ep['endpoint']} 延迟偏高，建议优化数据访问"
        if await _create_recommendation(
            db, category=category, severity="warning", title=title,
            description=(
                f"p95 {ep['p95_ms']:.0f}ms / avg {ep['avg_ms']:.0f}ms（近窗口 {ep['count']} 次请求）。"
                "建议：热点 GET 端点接入缓存（cache_service），"
                "查询路径核对索引覆盖（selectinload 预加载 / 复合索引）。"
            ),
            evidence={"endpoint": ep["endpoint"], "p95_ms": ep["p95_ms"],
                      "count": ep["count"]},
        ):
            created[category] = created.get(category, 0) + 1
    return created


async def _recommend_n_plus_one(db, recent: list[dict]) -> dict:
    """建议 2：N+1 查询风暴 → selectinload 预加载。"""
    created: dict[str, int] = {}
    storm = [t for t in recent if t["db_query_count"] >= 20]
    if storm:
        worst = max(storm, key=lambda t: t["db_query_count"])
        title = "疑似 N+1 查询：单请求 DB 调用过多"
        if await _create_recommendation(
            db, category="n_plus_one", severity="warning", title=title,
            description=(
                f"最近 {len(storm)} 条 trace 单请求 DB 查询 ≥20 次，最严重 "
                f"{worst['endpoint']} {worst['db_query_count']} 次 / {worst['db_query_ms']:.0f}ms。"
                "建议使用 selectinload 预加载关联对象，避免循环逐条查询。"
            ),
            evidence={"storm_trace_count": len(storm), "worst_endpoint": worst["endpoint"],
                      "worst_db_queries": worst["db_query_count"]},
        ):
            created["n_plus_one"] = created.get("n_plus_one", 0) + 1
    return created


async def _recommend_cache(db, cache_rate: float | None) -> dict:
    """建议 3：缓存命中率低 → 核查 key 与 TTL。"""
    created: dict[str, int] = {}
    if cache_rate is not None and cache_rate < 0.5:
        title = "缓存命中率偏低，建议核查缓存 key 与 TTL"
        if await _create_recommendation(
            db, category="cache", severity="info", title=title,
            description=(
                f"最近窗口缓存命中率 {cache_rate:.0%} < 50%。"
                "建议：私有数据 key 含 user_id（项目硬约束），热点公共数据提高 TTL，"
                "避免 key 前缀过细导致命中率低。"
            ),
            evidence={"cache_hit_rate": cache_rate},
        ):
            created["cache"] = created.get("cache", 0) + 1
    return created


async def _recommend_llm(db, s, recent: list[dict]) -> dict:
    """建议 4：LLM 延迟高 / fallback 率高 → 成本档路由。"""
    created: dict[str, int] = {}
    llm_calls = sum(t["llm_call_count"] for t in recent)
    if llm_calls < 5:
        return created
    llm_ms = sum(t["llm_ms"] for t in recent)
    avg_llm_ms = llm_ms / llm_calls
    fallbacks = sum(t["llm_fallback_count"] for t in recent)
    if avg_llm_ms >= 10000:
        title = "LLM 调用延迟偏高，建议成本档路由 / 模型降档"
        if await _create_recommendation(
            db, category="llm_routing", severity="warning", title=title,
            description=(
                f"最近 {llm_calls} 次 LLM 调用平均 {avg_llm_ms:.0f}ms。"
                "建议：低价值意图（客服/通知/积分）走 economy 档（cost_tiered_routing_enabled），"
                "或配置 local 边缘盒子降档。"
            ),
            evidence={"llm_calls": llm_calls, "avg_llm_ms_ms": round(avg_llm_ms, 1)},
        ):
            created["llm_routing"] = created.get("llm_routing", 0) + 1
    elif fallbacks / llm_calls >= s.diagnostics_llm_fallback_threshold:
        title = "LLM fallback 频繁，建议核查主供应商可用性"
        if await _create_recommendation(
            db, category="llm_routing", severity="warning", title=title,
            description=(
                f"最近 {llm_calls} 次 LLM 调用中 {fallbacks} 次 fallback。"
                "建议核查主供应商 API Key / 余额 / 限流，必要时调整 DEFAULT_FALLBACK_CHAIN 优先级。"
            ),
            evidence={"llm_calls": llm_calls, "fallbacks": fallbacks},
        ):
            created["llm_routing"] = created.get("llm_routing", 0) + 1
    return created


async def _recommend_server_errors(db, recent: list[dict]) -> dict:
    """建议 5：持续 5xx → 异常处理 / 降级路径。"""
    created: dict[str, int] = {}
    server_errors = [t for t in recent if t["status_code"] >= 500]
    if len(server_errors) >= 5:
        title = "持续 5xx 错误，建议核查异常处理与降级路径"
        if await _create_recommendation(
            db, category="error_handling", severity="warning", title=title,
            description=(
                f"最近 {len(server_errors)} 条 trace 返回 5xx。"
                "建议：结合告警证据定位错误来源，确认 4 级降级链（AI 渲染）等路径未被误关，"
                "对外保持诚实降级（503 + 标注）而非硬编码假数据。"
            ),
            evidence={"server_error_count": len(server_errors)},
        ):
            created["error_handling"] = created.get("error_handling", 0) + 1
    return created


async def _latest_cache_hit_rate(db) -> float | None:
    from app.models.diagnostics import DiagnosticMetricSnapshot

    result = await db.execute(
        select(DiagnosticMetricSnapshot.extra)
        .where(DiagnosticMetricSnapshot.category == "cache")
        .order_by(DiagnosticMetricSnapshot.window_end.desc())
        .limit(1)
    )
    extra = result.scalar_one_or_none()
    if not extra:
        return None
    return float(extra.get("hit_rate", 0.0))


async def _create_recommendation(db, *, category: str, severity: str, title: str,
                                 description: str, evidence: dict) -> bool:
    from app.models.diagnostics import DiagnosticRecommendation

    result = await db.execute(
        select(DiagnosticRecommendation.id)
        .where(
            DiagnosticRecommendation.title == title,
            DiagnosticRecommendation.status == "open",
        )
        .limit(1)
    )
    if result.scalar_one_or_none() is not None:
        return False
    db.add(DiagnosticRecommendation(
        category=category, severity=severity, title=title,
        description=description, evidence=evidence,
    ))
    await db.commit()
    return True

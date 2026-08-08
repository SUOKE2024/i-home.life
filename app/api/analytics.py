"""前端埋点采集 API — 接收 web/assets/js/analytics.js 上报的事件批量。

v1.2.7 新增：此前 analytics.js 调用 /api/analytics/collect 但后端无对应端点，
导致每次页面加载（含登录页）产生 404 噪声。本端点公开（不带 Authorization），
仅接收并丢弃（后续可接入持久化/分析管道），消除全链路 404。

v1.10.x 扩展：接收 webapp RUM 性能事件（type=perf 的 Core Web Vitals），
受 settings.diagnostics_rum_enabled 门控持久化到 diagnostic_rum_events，
对齐 2026 行业前沿 RUM（Real User Monitoring）能力。

设计：
  - 公开端点（analytics.js 不附带 token，且需在登录前采集页面访问）
  - 容错：任意 JSON 体均接受，仅校验为数组/对象，避免前端格式异常导致 5xx
  - 204 No Content：前端 fetch 不解析响应体，204 最省带宽
"""
import logging
from typing import Any

from fastapi import APIRouter, Request, status
from fastapi.responses import Response

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/analytics", tags=["埋点采集"])


@router.post("/collect", status_code=status.HTTP_204_NO_CONTENT)
async def collect_events(request: Request) -> Response:
    """接收前端埋点事件批量。

    analytics.js 上报格式：{"events": [...], "v": "1.0.0"}
    本端点仅接收不持久化（预留接入点），始终返回 204。

    RUM 事件格式：{"events": [{"type": "perf", "metric": "lcp",
    "value": 1234, "page": "/", "session_id": "..."}]}
    diagnostics_rum_enabled=True 时 type=perf 事件落库。
    """
    try:
        body: Any = await request.json()
        events = body.get("events") if isinstance(body, dict) else body
        if isinstance(events, list):
            await _persist_rum_events(events)
        count = len(events) if isinstance(events, list) else 1
        logger.debug("[analytics] 收到 %s 条事件", count)
    except Exception:
        # 非 JSON 或空体：忽略，仍返回 204（埋点不应阻塞前端）
        logger.debug("[analytics] 收到非 JSON 体，已忽略")
    return Response(status_code=status.HTTP_204_NO_CONTENT)


async def _persist_rum_events(events: list[dict]) -> None:
    """best-effort 落库 RUM 性能事件（受 diagnostics_rum_enabled 门控）。"""
    try:
        from app.config import get_settings
        if not get_settings().diagnostics_rum_enabled:
            return
        from app.services.diagnostics_service import record_rum_event

        valid_metrics = {"lcp", "cls", "inp", "fcp", "ttfb"}
        user_agent = None
        for ev in events:
            if not isinstance(ev, dict) or ev.get("type") != "perf":
                continue
            metric = ev.get("metric", "")
            if metric not in valid_metrics:
                continue
            value = ev.get("value")
            if not isinstance(value, (int, float)) or value < 0:
                continue
            await record_rum_event(
                session_id=str(ev.get("session_id") or "")[:64] or None,
                page=str(ev.get("page") or "")[:200] or None,
                metric=metric,
                value=float(value),
                user_agent=user_agent,
                extra=ev.get("extra") if isinstance(ev.get("extra"), dict) else None,
            )
    except Exception:
        logger.debug("[analytics] RUM 落库失败（忽略）", exc_info=True)

"""Prometheus 指标定义与暴露端点。

指标:
    - http_requests_total{method, path, status}: 请求总数（Counter）
    - http_request_duration_seconds{method, path}: 请求耗时（Histogram）
    - http_requests_in_progress: 进行中请求数（Gauge）
"""
from fastapi import Response
from prometheus_client import (
    CONTENT_TYPE_LATEST,
    Counter,
    Gauge,
    Histogram,
    generate_latest,
)

http_requests_total = Counter(
    "http_requests_total",
    "Total HTTP requests",
    ["method", "path", "status"],
)

http_request_duration_seconds = Histogram(
    "http_request_duration_seconds",
    "HTTP request duration in seconds",
    ["method", "path"],
    buckets=(0.005, 0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1, 2.5, 5, 10),
)

http_requests_in_progress = Gauge(
    "http_requests_in_progress",
    "Number of HTTP requests in progress",
)


def metrics_response() -> Response:
    """返回 Prometheus 格式的指标数据。"""
    return Response(content=generate_latest(), media_type=CONTENT_TYPE_LATEST)

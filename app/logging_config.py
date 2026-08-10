"""结构化 JSON 日志配置。

使用 structlog + stdlib logging 的 ProcessorFormatter 桥接，使现有
``logging.getLogger(__name__)`` 调用与 structlog 原生日志均输出统一 JSON。

标准字段: timestamp, level, logger, message, request_id, user_id,
path, method, duration_ms（后四个由 contextvars 在中间件中注入），
trace_id, span_id（v1.2.2 F4：由 inject_trace_context 从活跃 OTel span 注入，
tracing 未启用或无活跃 span 时缺失，不影响日志）。
"""
import logging
from typing import Any

import structlog

from app.observability.tracing import inject_trace_context

# 需脱敏的字段名（小写匹配）
_SENSITIVE_KEYS = frozenset(
    {
        "token",
        "password",
        "secret",
        "authorization",
        "api_key",
        "apikey",
        "paseto_secret_key",
        "cookie",
        "credentials",
    }
)


def _redact_sensitive(_logger, _method_name, event_dict: dict) -> dict:
    """脱敏处理器：将敏感字段值替换为 ***REDACTED***。"""
    for key in list(event_dict.keys()):
        if key.lower() in _SENSITIVE_KEYS:
            event_dict[key] = "***REDACTED***"
    return event_dict


# 共享处理器链 —— structlog 原生日志与 stdlib foreign 记录共用
_shared_processors: list[Any] = [
    structlog.contextvars.merge_contextvars,
    structlog.stdlib.add_logger_name,
    structlog.stdlib.add_log_level,
    structlog.processors.TimeStamper(fmt="iso", utc=True),
    structlog.processors.StackInfoRenderer(),
    structlog.processors.format_exc_info,
    _redact_sensitive,
    # v1.2.2 F4：日志-追踪关联。注入活跃 OTel span 的 trace_id/span_id；
    # tracing 未启用或无活跃 span 时为 no-op，零开销。
    inject_trace_context,
]


def configure_logging(debug: bool = False, log_level: str = "") -> None:
    """配置全局结构化 JSON 日志。

    Args:
        debug: True 时使用 DEBUG 级别，否则 WARNING（与原有配置保持一致）。
        log_level: 显式日志级别（DEBUG/INFO/WARNING/ERROR），优先于 debug。
            用于生产在默认 WARNING 下按需放行编排/Agent 链路的 INFO 事件日志。
    """
    if log_level:
        _level_name = log_level.strip().upper()
        level = getattr(logging, _level_name, None)
        if not isinstance(level, int):
            level = logging.WARNING
    else:
        level = logging.DEBUG if debug else logging.WARNING

    structlog.configure(
        processors=_shared_processors
        + [
            structlog.stdlib.ProcessorFormatter.wrap_for_formatter,
        ],
        logger_factory=structlog.stdlib.LoggerFactory(),
        wrapper_class=structlog.stdlib.BoundLogger,
        cache_logger_on_first_use=True,
    )

    formatter = structlog.stdlib.ProcessorFormatter(
        foreign_pre_chain=_shared_processors,
        processors=[
            structlog.processors.EventRenamer("message"),
            structlog.stdlib.ProcessorFormatter.remove_processors_meta,
            structlog.processors.JSONRenderer(ensure_ascii=False),
        ],
    )

    handler = logging.StreamHandler()
    handler.setFormatter(formatter)

    root_logger = logging.getLogger()
    root_logger.handlers.clear()
    root_logger.addHandler(handler)
    root_logger.setLevel(level)

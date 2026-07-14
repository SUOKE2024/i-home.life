"""结构化 JSON 日志配置。

使用 structlog + stdlib logging 的 ProcessorFormatter 桥接，使现有
``logging.getLogger(__name__)`` 调用与 structlog 原生日志均输出统一 JSON。

标准字段: timestamp, level, logger, message, request_id, user_id,
path, method, duration_ms（后四个由 contextvars 在中间件中注入）。
"""
import logging

import structlog

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
_shared_processors = [
    structlog.contextvars.merge_contextvars,
    structlog.stdlib.add_logger_name,
    structlog.stdlib.add_log_level,
    structlog.processors.TimeStamper(fmt="iso", utc=True),
    structlog.processors.StackInfoRenderer(),
    structlog.processors.format_exc_info,
    _redact_sensitive,
]


def configure_logging(debug: bool = False) -> None:
    """配置全局结构化 JSON 日志。

    Args:
        debug: True 时使用 DEBUG 级别，否则 WARNING（与原有配置保持一致）。
    """
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

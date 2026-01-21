"""Structured logging configuration for Anavibe.

Provides secure, structured logging with:
- JSON formatting for production
- Sensitive data filtering
- Request correlation IDs
- Performance tracking
"""

import logging
import sys
from contextvars import ContextVar
from typing import TYPE_CHECKING, Any

import structlog
from structlog.typing import EventDict


if TYPE_CHECKING:
    from anavibe.core.config import Settings


# Context variable for request correlation ID
correlation_id_var: ContextVar[str | None] = ContextVar("correlation_id", default=None)


# Sensitive fields that should never be logged
SENSITIVE_FIELDS = frozenset({
    "password",
    "secret",
    "token",
    "api_key",
    "apikey",
    "authorization",
    "auth",
    "credential",
    "private_key",
    "secret_key",
    "access_token",
    "refresh_token",
    "bearer",
    "jwt",
    "session_id",
    "cookie",
    "ssn",
    "credit_card",
    "card_number",
    "cvv",
    "pin",
})


def filter_sensitive_data(
    _: Any,
    __: str,
    event_dict: EventDict,
) -> EventDict:
    """Filter sensitive data from log events.

    Replaces sensitive field values with '[REDACTED]'.

    Args:
        _: Logger instance (unused).
        __: Method name (unused).
        event_dict: Log event dictionary.

    Returns:
        Filtered event dictionary.
    """

    def _filter_dict(d: dict[str, Any]) -> dict[str, Any]:
        filtered = {}
        for key, value in d.items():
            lower_key = key.lower()
            # Check if key contains any sensitive field name
            if any(sensitive in lower_key for sensitive in SENSITIVE_FIELDS):
                filtered[key] = "[REDACTED]"
            elif isinstance(value, dict):
                filtered[key] = _filter_dict(value)
            elif isinstance(value, list):
                filtered[key] = [
                    _filter_dict(item) if isinstance(item, dict) else item
                    for item in value
                ]
            else:
                filtered[key] = value
        return filtered

    return _filter_dict(event_dict)


def add_correlation_id(
    _: Any,
    __: str,
    event_dict: EventDict,
) -> EventDict:
    """Add correlation ID to log events.

    Args:
        _: Logger instance (unused).
        __: Method name (unused).
        event_dict: Log event dictionary.

    Returns:
        Event dictionary with correlation ID.
    """
    correlation_id = correlation_id_var.get()
    if correlation_id:
        event_dict["correlation_id"] = correlation_id
    return event_dict


def add_service_info(
    _: Any,
    __: str,
    event_dict: EventDict,
) -> EventDict:
    """Add service information to log events.

    Args:
        _: Logger instance (unused).
        __: Method name (unused).
        event_dict: Log event dictionary.

    Returns:
        Event dictionary with service info.
    """
    event_dict["service"] = "anavibe"
    return event_dict


def configure_logging(settings: "Settings") -> None:
    """Configure structured logging for the application.

    Args:
        settings: Application settings.
    """
    # Determine log level
    log_level = getattr(logging, settings.log_level.value)

    # Common processors
    processors: list[structlog.typing.Processor] = [
        structlog.contextvars.merge_contextvars,
        structlog.stdlib.add_log_level,
        structlog.stdlib.add_logger_name,
        structlog.stdlib.PositionalArgumentsFormatter(),
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.processors.StackInfoRenderer(),
        add_correlation_id,
        add_service_info,
        filter_sensitive_data,
        structlog.processors.UnicodeDecoder(),
    ]

    # Format-specific processors
    if settings.log_format == "json":
        processors.append(structlog.processors.JSONRenderer())
    else:
        processors.append(structlog.dev.ConsoleRenderer(colors=True))

    # Configure structlog
    structlog.configure(
        processors=processors,
        wrapper_class=structlog.stdlib.BoundLogger,
        context_class=dict,
        logger_factory=structlog.stdlib.LoggerFactory(),
        cache_logger_on_first_use=True,
    )

    # Configure standard logging
    logging.basicConfig(
        format="%(message)s",
        stream=sys.stdout,
        level=log_level,
    )

    # Set third-party library log levels
    logging.getLogger("uvicorn").setLevel(log_level)
    logging.getLogger("uvicorn.access").setLevel(log_level)
    logging.getLogger("sqlalchemy.engine").setLevel(logging.WARNING)
    logging.getLogger("httpx").setLevel(logging.WARNING)


def get_logger(name: str | None = None) -> structlog.stdlib.BoundLogger:
    """Get a structured logger instance.

    Args:
        name: Logger name (defaults to caller module).

    Returns:
        Bound logger instance.
    """
    return structlog.get_logger(name)


class LogContext:
    """Context manager for adding temporary log context."""

    def __init__(self, **kwargs: Any) -> None:
        """Initialize with context key-value pairs.

        Args:
            **kwargs: Context values to bind.
        """
        self._context = kwargs
        self._token: Any = None

    def __enter__(self) -> "LogContext":
        """Enter context and bind values."""
        self._token = structlog.contextvars.bind_contextvars(**self._context)
        return self

    def __exit__(self, *args: Any) -> None:
        """Exit context and unbind values."""
        structlog.contextvars.unbind_contextvars(*self._context.keys())

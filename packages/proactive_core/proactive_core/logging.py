"""Structured logging with sensitive-data redaction."""

import logging
import re
import sys
from collections.abc import MutableMapping
from typing import Any, cast

import structlog

SECRET_PATTERN = re.compile(r"(?i)(authorization|password|secret|token|api[_-]?key)(\s*[:=]\s*)([^\s,;}]+)")


def redact_secrets(_: Any, __: str, event: MutableMapping[str, Any]) -> MutableMapping[str, Any]:
    """Remove common credentials from every rendered field."""
    for key, value in tuple(event.items()):
        if any(word in key.lower() for word in ("password", "secret", "token", "authorization")):
            event[key] = "[REDACTED]"
        elif isinstance(value, str):
            event[key] = SECRET_PATTERN.sub(r"\1\2[REDACTED]", value)
    return event


def configure_logging(level: int = logging.INFO) -> None:
    """Configure JSON logs for application and dependency loggers."""
    shared = [
        structlog.contextvars.merge_contextvars,
        structlog.processors.add_log_level,
        structlog.processors.TimeStamper(fmt="iso", utc=True),
        redact_secrets,
        structlog.processors.JSONRenderer(),
    ]
    logging.basicConfig(stream=sys.stdout, level=level, format="%(message)s", force=True)
    structlog.configure(
        processors=cast(Any, shared),
        wrapper_class=structlog.make_filtering_bound_logger(level),
        logger_factory=structlog.stdlib.LoggerFactory(),
        cache_logger_on_first_use=True,
    )

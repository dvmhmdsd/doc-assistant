"""Structured logging configuration using structlog."""
from __future__ import annotations

import logging
import re
from typing import Any

import structlog

_SECRET_PATTERNS = ("api_key", "authorization", "app_shared_token")
REDACT_KEYS = [re.compile(k, re.IGNORECASE) for k in _SECRET_PATTERNS]


def _redact_processor(
    logger: logging.Logger, name: str, event_dict: dict[str, Any]
) -> dict[str, Any]:
    # Redact any keys that match known secret patterns
    out = {}
    for k, v in event_dict.items():
        if any(p.search(k) for p in REDACT_KEYS):
            out[k] = "[REDACTED]"
        else:
            out[k] = v
    return out


def configure_logging(level: str = "INFO") -> None:
    logging.basicConfig(level=getattr(logging, level.upper(), logging.INFO), format="%(message)s")

    processors = [
        structlog.contextvars.merge_contextvars,
        _redact_processor,
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.processors.JSONRenderer()
    ]

    level_int = getattr(logging, level.upper(), logging.INFO)
    structlog.configure(
        processors=processors,
        context_class=dict,
        logger_factory=structlog.stdlib.LoggerFactory(),
        wrapper_class=structlog.make_filtering_bound_logger(level_int),
        cache_logger_on_first_use=True,
    )


def get_logger(name: str | None = None):
    return structlog.get_logger(name)

"""Structured logging configuration using structlog."""
from __future__ import annotations

import logging
import re
from collections.abc import Callable, MutableMapping
from typing import Any

import structlog

_SECRET_PATTERNS = ("api_key", "authorization")
REDACT_KEYS = [re.compile(k, re.IGNORECASE) for k in _SECRET_PATTERNS]


def _redact_processor(
    logger: Any, name: str, event_dict: MutableMapping[str, Any]
) -> MutableMapping[str, Any]:
    # Redact any keys that match known secret patterns
    out: MutableMapping[str, Any] = {}
    for k, v in event_dict.items():
        if any(p.search(k) for p in REDACT_KEYS):
            out[k] = "[REDACTED]"
        else:
            out[k] = v
    return out


_Processor = Callable[[Any, str, MutableMapping[str, Any]], Any]


def configure_logging(level: str = "INFO") -> None:
    logging.basicConfig(level=getattr(logging, level.upper(), logging.INFO), format="%(message)s")

    processors: list[_Processor] = [
        structlog.contextvars.merge_contextvars,
        _redact_processor,
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.processors.JSONRenderer(),
    ]

    level_int = getattr(logging, level.upper(), logging.INFO)
    structlog.configure(
        processors=processors,
        context_class=dict,
        logger_factory=structlog.stdlib.LoggerFactory(),
        wrapper_class=structlog.make_filtering_bound_logger(level_int),
        cache_logger_on_first_use=True,
    )


def get_logger(name: str | None = None) -> structlog.stdlib.BoundLogger:
    return structlog.get_logger(name)  # type: ignore[no-any-return]

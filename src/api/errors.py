"""Application error types and FastAPI exception handler.

Each ``AppError`` subclass declares its own HTTP status code so the
exception handler can render the OpenAPI ``Error`` schema with the right
status without per-error branching. Bodies never include stack traces or
secrets (FR-011, FR-015).
"""
from __future__ import annotations

from fastapi import Request
from fastapi.responses import JSONResponse


class AppError(Exception):
    code: str = "internal_error"
    status_code: int = 500

    def __init__(self, message: str, *, code: str | None = None, status_code: int | None = None):
        self.message = message
        if code is not None:
            self.code = code
        if status_code is not None:
            self.status_code = status_code


class BadRequest(AppError):
    code = "bad_request"
    status_code = 400


class NotFoundError(AppError):
    code = "not_found"
    status_code = 404


class PayloadTooLarge(AppError):
    code = "payload_too_large"
    status_code = 413


class UnsupportedMediaType(AppError):
    code = "unsupported_media_type"
    status_code = 415


class UpstreamUnavailable(AppError):
    code = "upstream_unavailable"
    status_code = 502


async def app_exception_handler(request: Request, exc: AppError) -> JSONResponse:
    request_id = getattr(request.state, "request_id", None)
    payload = {"code": exc.code, "message": exc.message, "request_id": request_id}
    return JSONResponse(status_code=exc.status_code, content=payload)

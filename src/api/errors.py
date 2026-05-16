"""Application error types and FastAPI exception handler."""
from __future__ import annotations

from fastapi import Request
from fastapi.responses import JSONResponse


class AppError(Exception):
    def __init__(self, code: str, message: str):
        self.code = code
        self.message = message


class NotFoundError(AppError):
    pass


class UnauthorizedError(AppError):
    pass


async def app_exception_handler(request: Request, exc: AppError):
    payload = {"code": exc.code, "message": exc.message, "request_id": request.state.request_id if hasattr(request.state, "request_id") else None}
    return JSONResponse(status_code=400 if exc.code != "unauthorized" else 401, content=payload)

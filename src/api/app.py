"""FastAPI application factory wiring error handlers, middleware, and routes."""
from __future__ import annotations

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

from ..observability.logging import configure_logging, get_logger
from ..observability import metrics
from .errors import app_exception_handler, AppError
from .routes.metrics import router as metrics_router


def create_app() -> FastAPI:
    configure_logging()
    log = get_logger("doc-assistant")

    app = FastAPI(title="Doc Assistant")

    # Exception handler for AppError
    app.add_exception_handler(AppError, app_exception_handler)

    # Simple middleware to attach request_id
    @app.middleware("http")
    async def add_request_id(request: Request, call_next):
        request.state.request_id = request.headers.get("X-Request-Id") or "req-" + __import__("uuid").uuid4().hex
        log.info("request.start", path=request.url.path, request_id=request.state.request_id)
        response = await call_next(request)
        log.info("request.end", path=request.url.path, request_id=request.state.request_id, status_code=response.status_code)
        return response

    # Healthz route
    @app.get("/healthz", include_in_schema=False)
    async def healthz():
        return JSONResponse({"status": "ok", "version": "0.1.0"})

    # Metrics route (mounted under /metrics)
    app.include_router(metrics_router)

    return app

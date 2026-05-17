"""FastAPI application factory."""
from __future__ import annotations

import os
import uuid
from collections.abc import Awaitable, Callable

import structlog
from fastapi import FastAPI, Request, Response
from fastapi.staticfiles import StaticFiles

from ..observability.logging import configure_logging, get_logger
from .errors import AppError, app_exception_handler
from .routes.ask import router as ask_router
from .routes.history import router as history_router
from .routes.metrics import router as metrics_router
from .routes.session import router as session_router
from .routes.upload import router as upload_router


def create_app() -> FastAPI:
    configure_logging()
    log = get_logger("doc-assistant")

    app = FastAPI(title="Doc Assistant", version="0.1.0")

    # Typed-error → OpenAPI Error schema renderer.
    app.add_exception_handler(AppError, app_exception_handler)  # type: ignore[arg-type]

    @app.middleware("http")
    async def request_context(
        request: Request, call_next: Callable[[Request], Awaitable[Response]]
    ) -> Response:
        request_id = request.headers.get("X-Request-Id") or uuid.uuid4().hex
        request.state.request_id = request_id
        # Bind the contextvar so every structlog event from this task
        # auto-includes request_id (FR-022).
        structlog.contextvars.clear_contextvars()
        structlog.contextvars.bind_contextvars(request_id=request_id)
        log.info("request.start", path=request.url.path, method=request.method)
        response = await call_next(request)
        log.info(
            "request.end",
            path=request.url.path,
            method=request.method,
            status_code=response.status_code,
        )
        return response

    @app.get("/healthz", include_in_schema=False)
    async def healthz() -> dict[str, str]:
        return {"status": "ok", "version": "0.1.0"}

    app.include_router(metrics_router)
    app.include_router(upload_router)
    app.include_router(ask_router)
    app.include_router(session_router)
    app.include_router(history_router)

    # SPA static mount comes AFTER API routers so API paths take precedence.
    # Missing dist is non-fatal (e.g., backend-only dev runs) but surfaced.
    spa_dir = os.environ.get("SPA_DIST_DIR", "/app/frontend_dist")
    if os.path.isdir(spa_dir):
        app.mount("/", StaticFiles(directory=spa_dir, html=True), name="spa")
    else:
        log.warning("spa.dist.missing", path=spa_dir)

    return app

"""Uvicorn entrypoint.

Exposes ``app`` so ``uvicorn src.main:app`` (the Dockerfile CMD) resolves to a
running FastAPI application. As Phase 3 concrete implementations (T040–T053)
land, additional routes and services will be wired into ``create_app()`` —
this file stays a thin export.
"""
from __future__ import annotations

from .api.app import create_app

app = create_app()

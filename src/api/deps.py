"""Dependency utilities for FastAPI routes: auth, request id, session registry."""
from __future__ import annotations

import secrets
import uuid
from contextvars import ContextVar
from fastapi import Header, HTTPException

from ..config import get_settings


request_id_ctx: ContextVar[str] = ContextVar("request_id", default="")


def request_id_dep() -> str:
    rid = str(uuid.uuid4())
    request_id_ctx.set(rid)
    return rid


def require_bearer_token(authorization: str | None = Header(None)) -> None:
    settings = get_settings()
    if not authorization or not authorization.lower().startswith("bearer "):
        raise HTTPException(status_code=401, detail={"code": "unauthorized", "message": "Missing Authorization header"})
    token = authorization.split(None, 1)[1]
    if not secrets.compare_digest(token, settings.app_shared_token):
        raise HTTPException(status_code=401, detail={"code": "unauthorized", "message": "Invalid token"})


class SessionRegistry:
    """Placeholder session registry. Implemented later."""
    def __init__(self):
        self._store = {}

    def create(self, session_id: str):
        self._store[session_id] = {}

    def exists(self, session_id: str) -> bool:
        return session_id in self._store


def get_session_registry() -> SessionRegistry:
    # Simple per-process registry; services will replace with real implementation
    global _REG
    try:
        return _REG
    except NameError:
        _REG = SessionRegistry()
        return _REG

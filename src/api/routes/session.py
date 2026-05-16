"""POST /session/end route (T052).

Explicitly ends a session and purges its data. Returns 204 on success.
Idempotent: a second call on the same handle returns 404 (the session
no longer exists).
"""
from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends
from fastapi.responses import Response
from pydantic import BaseModel, Field

from ...services.sessions import SessionService
from ..deps import get_session_service, require_bearer_token

router = APIRouter()


class EndSessionRequest(BaseModel):
    session_id: str = Field(..., min_length=1)


@router.post("/session/end", status_code=204)
async def end_session(
    body: EndSessionRequest,
    _auth: Annotated[None, Depends(require_bearer_token)] = None,
    session_svc: Annotated[SessionService, Depends(get_session_service)] = None,  # type: ignore[assignment]
) -> Response:
    assert session_svc is not None
    await session_svc.end(body.session_id)
    return Response(status_code=204)

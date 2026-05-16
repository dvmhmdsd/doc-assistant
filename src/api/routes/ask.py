"""POST /ask route (T051).

Returns a ``text/event-stream`` SSE response with the four frame types
defined in ``contracts/openapi.yaml``:
    event: token       data: {"text": "<delta>"}
    event: citations   data: Citation[]
    event: done        data: {"turn_id": "...", "stopped": false}
    event: error       data: {"code": "...", "message": "..."}

Errors raised by the QA service mid-stream are caught and emitted as a
single ``event: error`` frame so the client transcript can render the
failure inline instead of seeing the connection drop (FR-011 + T051).
"""
from __future__ import annotations

import json
from collections.abc import AsyncIterator
from typing import Annotated

import structlog
from fastapi import APIRouter, Depends
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field

from ...services.qa import QAEvent, QAService
from ...services.sessions import SessionService
from ..deps import get_qa_service, get_session_service, require_bearer_token
from ..errors import AppError, BadRequest

router = APIRouter()
_log = structlog.get_logger(__name__)


class AskRequest(BaseModel):
    session_id: str = Field(..., min_length=1)
    question: str = Field(..., min_length=1, max_length=4000)


def _sse_frame(event: str, data: object) -> bytes:
    return f"event: {event}\ndata: {json.dumps(data)}\n\n".encode("utf-8")


async def _wrap_stream(events: AsyncIterator[QAEvent]) -> AsyncIterator[bytes]:
    try:
        async for ev in events:
            yield _sse_frame(ev.type, ev.payload)
    except AppError as exc:
        _log.warning("ask.stream_error", code=exc.code, message=exc.message)
        yield _sse_frame("error", {"code": exc.code, "message": exc.message})
    except Exception as exc:  # noqa: BLE001 - bounded conversion at the stream boundary
        _log.exception("ask.stream_internal_error")
        yield _sse_frame(
            "error",
            {"code": "internal_error", "message": "stream terminated unexpectedly"},
        )
        # Do not re-raise: the SSE response body is already partial; raising
        # would corrupt the framing on its way out.


@router.post("/ask")
async def ask(
    body: AskRequest,
    _auth: Annotated[None, Depends(require_bearer_token)] = None,
    session_svc: Annotated[SessionService, Depends(get_session_service)] = None,  # type: ignore[assignment]
    qa_svc: Annotated[QAService, Depends(get_qa_service)] = None,  # type: ignore[assignment]
) -> StreamingResponse:
    assert session_svc is not None and qa_svc is not None

    if not body.question.strip():
        raise BadRequest("question must be non-empty")
    await session_svc.resolve(body.session_id)

    events = qa_svc.answer(session_id=body.session_id, question=body.question)
    return StreamingResponse(_wrap_stream(events), media_type="text/event-stream")

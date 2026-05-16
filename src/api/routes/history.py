"""GET /history/{session_id} route (T056, FR-009).

Returns the ordered conversation transcript for a session. Auth is the
shared bearer token (anyone holding both the token AND the session
handle can read the history — by v1 design, per the FR-018
clarification). Missing or ended sessions return 404 via the typed
NotFoundError raised by SessionService.resolve.
"""
from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends

from ...history.base import ConversationStore
from ...services.sessions import SessionService
from ..deps import get_history_store, get_session_service, require_bearer_token

router = APIRouter()


@router.get("/history/{session_id}")
async def get_history(
    session_id: str,
    _auth: Annotated[None, Depends(require_bearer_token)] = None,
    sessions: Annotated[SessionService, Depends(get_session_service)] = None,  # type: ignore[assignment]
    history: Annotated[ConversationStore, Depends(get_history_store)] = None,  # type: ignore[assignment]
) -> dict:
    assert sessions is not None and history is not None

    # Will raise NotFoundError → 404 via the global handler if missing/ended.
    await sessions.resolve(session_id)
    turns = await history.get(session_id)

    return {
        "session_id": session_id,
        "turns": [
            {
                "turn_id": t.turn_id,
                "role": t.role,
                "content": t.content,
                "citations": (
                    [
                        {
                            "chunk_id": c.chunk_id,
                            "document_id": c.document_id,
                            "locator": c.locator,
                            "score": c.score,
                        }
                        for c in t.citations
                    ]
                    if t.citations
                    else None
                ),
                "created_at": t.created_at.isoformat(),
                "state": t.state,
            }
            for t in turns
        ],
    }

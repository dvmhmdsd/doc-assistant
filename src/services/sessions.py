"""Session lifecycle (T047).

``create_session`` mints an unguessable handle (``secrets.token_urlsafe``).
``resolve`` raises :class:`NotFoundError` for missing or ended sessions
so the FastAPI handler returns 404 (FR-018). ``end`` drops the session's
chunks and history and removes the registry entry so memory stays
bounded for long-running deployments (FR-019).
"""
from __future__ import annotations

import asyncio
import secrets
from dataclasses import dataclass
from datetime import UTC, datetime

from ..api.errors import NotFoundError
from ..history.base import ConversationStore
from ..vector_store.base import VectorStore


@dataclass
class _SessionState:
    created_at: datetime
    last_activity_at: datetime


class SessionService:
    def __init__(
        self,
        vector_store: VectorStore,
        conversation_store: ConversationStore,
    ) -> None:
        self._vector_store = vector_store
        self._conversation_store = conversation_store
        self._registry: dict[str, _SessionState] = {}
        self._lock = asyncio.Lock()

    async def create_session(self) -> str:
        handle = secrets.token_urlsafe(32)
        now = datetime.now(UTC)
        async with self._lock:
            # 256-bit token collision probability is negligible; loop only
            # for absolute safety.
            while handle in self._registry:
                handle = secrets.token_urlsafe(32)
            self._registry[handle] = _SessionState(created_at=now, last_activity_at=now)
        return handle

    async def resolve(self, session_id: str) -> None:
        async with self._lock:
            state = self._registry.get(session_id)
            if state is None:
                raise NotFoundError("session not found")
            state.last_activity_at = datetime.now(UTC)

    async def end(self, session_id: str) -> None:
        # Remove the registry entry FIRST under the lock so a concurrent
        # `resolve` cannot succeed while data is being purged. After this
        # block the handle is gone — drop_session calls are idempotent
        # against missing collections.
        async with self._lock:
            if session_id not in self._registry:
                raise NotFoundError("session not found")
            del self._registry[session_id]

        await self._vector_store.drop_session(session_id)
        await self._conversation_store.drop_session(session_id)

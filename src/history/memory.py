"""In-memory :class:`ConversationStore` implementation.

- Per-session ``asyncio.Lock`` held in a ``WeakValueDictionary`` so the
  lock is GC'd once no coroutine holds a strong reference. This keeps
  the lock table from growing without bound across long-running
  deployments (T045 spec).
- ``append`` and ``get`` both acquire the per-session lock so a
  concurrent reader cannot observe a partially-mutated turn list.
- ``drop_session`` removes the store entry; idempotent.
"""
from __future__ import annotations

import asyncio
from weakref import WeakValueDictionary

from .base import ConversationStore, ConversationTurn


class InMemoryConversationStore(ConversationStore):
    def __init__(self) -> None:
        self._store: dict[str, list[ConversationTurn]] = {}
        # WeakValueDictionary: the lock object is kept alive only while
        # SOME coroutine holds a strong ref (e.g., inside `async with`).
        # Once everyone releases, the lock disappears and the entry is
        # collected — bounded memory.
        self._locks: WeakValueDictionary[str, asyncio.Lock] = WeakValueDictionary()

    def _lock_for(self, session_id: str) -> asyncio.Lock:
        # `setdefault` is atomic per-key on WeakValueDictionary; the
        # second argument's strong reference keeps the new lock alive
        # at least until the caller binds it.
        return self._locks.setdefault(session_id, asyncio.Lock())

    async def append(self, session_id: str, turn: ConversationTurn) -> None:
        if turn.session_id != session_id:
            # Defense-in-depth against FR-018 cross-session leakage.
            raise ValueError(
                f"turn.session_id {turn.session_id!r} does not match {session_id!r}"
            )
        lock = self._lock_for(session_id)
        async with lock:
            self._store.setdefault(session_id, []).append(turn)

    async def get(self, session_id: str) -> list[ConversationTurn]:
        lock = self._lock_for(session_id)
        async with lock:
            # Snapshot under the lock so callers see a consistent view.
            return list(self._store.get(session_id, ()))

    async def drop_session(self, session_id: str) -> None:
        lock = self._lock_for(session_id)
        async with lock:
            self._store.pop(session_id, None)

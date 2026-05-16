"""ConversationStore contract — every implementation must satisfy these."""
from __future__ import annotations

import asyncio
from collections.abc import Callable
from datetime import datetime, timezone

import pytest

from src.history.base import ConversationStore, ConversationTurn
from src.history.memory import InMemoryConversationStore


# Parameterised registry — when additional ConversationStore impls land
# (e.g., Redis-backed), add them here and the entire suite runs against
# each one without duplication.
_FACTORIES: list[Callable[[], ConversationStore]] = [InMemoryConversationStore]


def _turn(session_id: str, turn_id: str, *, role: str = "user", content: str = "x") -> ConversationTurn:
    return ConversationTurn(
        turn_id=turn_id,
        session_id=session_id,
        role=role,
        content=content,
        citations=None,
        created_at=datetime.now(timezone.utc),
    )


@pytest.mark.asyncio
@pytest.mark.parametrize("factory", _FACTORIES)
async def test_append_then_get_preserves_order(factory: Callable[[], ConversationStore]) -> None:
    store = factory()
    for i in range(5):
        await store.append("s", _turn("s", f"t{i}"))
    assert [t.turn_id for t in await store.get("s")] == [f"t{i}" for i in range(5)]


@pytest.mark.asyncio
@pytest.mark.parametrize("factory", _FACTORIES)
async def test_drop_session_empties_session(factory: Callable[[], ConversationStore]) -> None:
    store = factory()
    await store.append("s", _turn("s", "t0"))
    await store.drop_session("s")
    assert await store.get("s") == []


@pytest.mark.asyncio
@pytest.mark.parametrize("factory", _FACTORIES)
async def test_drop_session_is_idempotent(factory: Callable[[], ConversationStore]) -> None:
    store = factory()
    await store.drop_session("never-existed")  # must not raise


@pytest.mark.asyncio
@pytest.mark.parametrize("factory", _FACTORIES)
async def test_concurrent_appends_serialize_per_session(
    factory: Callable[[], ConversationStore],
) -> None:
    store = factory()

    async def push(i: int) -> None:
        await store.append("s", _turn("s", f"t{i}"))

    await asyncio.gather(*(push(i) for i in range(20)))
    turns = await store.get("s")
    assert len(turns) == 20
    assert {t.turn_id for t in turns} == {f"t{i}" for i in range(20)}

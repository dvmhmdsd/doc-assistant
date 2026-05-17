"""Unit tests for :class:`InMemoryConversationStore` (T045)."""
from __future__ import annotations

import asyncio
from datetime import UTC, datetime

import pytest

from src.history.base import Citation, ConversationTurn
from src.history.memory import InMemoryConversationStore


def _turn(
    session_id: str, turn_id: str, role: str = "user", *, content: str = "x"
) -> ConversationTurn:
    return ConversationTurn(
        turn_id=turn_id,
        session_id=session_id,
        role=role,
        content=content,
        citations=None,
        created_at=datetime.now(UTC),
    )


@pytest.mark.asyncio
async def test_append_and_get_preserves_order() -> None:
    store = InMemoryConversationStore()
    for i in range(10):
        await store.append("s", _turn("s", f"t{i}"))
    turns = await store.get("s")
    assert [t.turn_id for t in turns] == [f"t{i}" for i in range(10)]


@pytest.mark.asyncio
async def test_get_unknown_session_returns_empty_list() -> None:
    store = InMemoryConversationStore()
    assert await store.get("never-existed") == []


@pytest.mark.asyncio
async def test_drop_session_is_idempotent() -> None:
    store = InMemoryConversationStore()
    await store.append("s", _turn("s", "t0"))
    await store.drop_session("s")
    await store.drop_session("s")  # second call must not raise
    assert await store.get("s") == []


@pytest.mark.asyncio
async def test_drop_clears_only_target_session() -> None:
    store = InMemoryConversationStore()
    await store.append("a", _turn("a", "t-a-0"))
    await store.append("b", _turn("b", "t-b-0"))
    await store.drop_session("a")
    assert await store.get("a") == []
    assert [t.turn_id for t in await store.get("b")] == ["t-b-0"]


@pytest.mark.asyncio
async def test_cross_session_isolation_on_append() -> None:
    store = InMemoryConversationStore()
    # Turn whose payload claims session "b" but caller routes to "a".
    rogue = _turn("b", "rogue")
    with pytest.raises(ValueError, match="does not match"):
        await store.append("a", rogue)
    assert await store.get("a") == []
    assert await store.get("b") == []


@pytest.mark.asyncio
async def test_concurrent_appends_serialize_per_session() -> None:
    store = InMemoryConversationStore()

    async def push(i: int) -> None:
        await store.append("s", _turn("s", f"t{i}"))

    # Fire 50 appends concurrently. Per-session lock guarantees no dropped writes.
    await asyncio.gather(*(push(i) for i in range(50)))
    turns = await store.get("s")
    assert len(turns) == 50
    assert {t.turn_id for t in turns} == {f"t{i}" for i in range(50)}


@pytest.mark.asyncio
async def test_get_returns_snapshot_not_internal_list() -> None:
    store = InMemoryConversationStore()
    await store.append("s", _turn("s", "t0"))
    turns = await store.get("s")
    turns.clear()  # external mutation must not affect the store
    assert [t.turn_id for t in await store.get("s")] == ["t0"]


@pytest.mark.asyncio
async def test_assistant_turn_carries_citations() -> None:
    store = InMemoryConversationStore()
    cite = Citation(chunk_id="c1", document_id="d1", locator="page 1", score=0.9)
    turn = ConversationTurn(
        turn_id="ta",
        session_id="s",
        role="assistant",
        content="answer",
        citations=[cite],
        created_at=datetime.now(UTC),
        state="complete",
    )
    await store.append("s", turn)
    got = (await store.get("s"))[0]
    assert got.citations == [cite]
    assert got.state == "complete"

"""QA service facade (T049).

Pipeline:
    1. Resolve prior turns (history threading).
    2. Embed the question.
    3. Vector-search top-K chunks scoped to the session.
    4. Build the prompt (system + prior turns + question + context).
    5. Stream LLM token deltas → yield ``QAEvent("token", {"text": ...})``.
    6. After the stream completes, emit one ``QAEvent("citations", [...])``.
    7. Persist user + assistant turns to history.
    8. Emit ``QAEvent("done", {...})``.

Records ``time_to_first_token_seconds``, ``retrieval_seconds``, and
``stream_total_seconds`` (FR-023). The user's question is persisted to
history BEFORE token streaming starts so a concurrent ``GET /history``
during streaming sees a coherent transcript.
"""
from __future__ import annotations

import time
import uuid
from collections.abc import AsyncIterator
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any

from ..api.errors import BadRequest
from ..config import get_settings
from ..embeddings.base import EmbeddingProvider
from ..history.base import Citation, ConversationStore, ConversationTurn
from ..llm.base import ChatMessage, LLMClient
from ..models.chunk import Chunk
from ..observability.metrics import (
    retrieval_seconds,
    stream_total_seconds,
    time_to_first_token_seconds,
)
from ..vector_store.base import VectorStore
from .prompts import SYSTEM_PROMPT, build_user_prompt, format_citations, locator_for

# Cap on prior turns threaded into the LLM context. Conservative ceiling
# to keep total prompt tokens bounded; tune per model context window.
_MAX_PRIOR_TURNS = 20


@dataclass(frozen=True)
class QAEvent:
    type: str  # 'token' | 'citations' | 'done' | 'error'
    payload: Any


class QAService:
    def __init__(
        self,
        *,
        embedder: EmbeddingProvider,
        vector_store: VectorStore,
        llm: LLMClient,
        history_store: ConversationStore,
    ) -> None:
        self._embedder = embedder
        self._store = vector_store
        self._llm = llm
        self._history = history_store
        self._cfg = get_settings()

    async def answer(self, *, session_id: str, question: str) -> AsyncIterator[QAEvent]:
        if not question.strip():
            raise BadRequest("question must be non-empty")

        prior = (await self._history.get(session_id))[-_MAX_PRIOR_TURNS:]

        q_emb = await self._embedder.embed([question])
        if not q_emb:
            raise BadRequest("embedding provider returned no vectors")

        retrieval_start = time.perf_counter()
        retrieved = await self._store.search(
            session_id=session_id, query_embedding=q_emb[0], k=self._cfg.top_k
        )
        retrieval_seconds.observe(time.perf_counter() - retrieval_start)

        chunks: list[Chunk] = [c for c, _ in retrieved]
        messages: list[ChatMessage] = [ChatMessage(role="system", content=SYSTEM_PROMPT)]
        for turn in prior:
            messages.append(ChatMessage(role=turn.role, content=turn.content))
        messages.append(ChatMessage(role="user", content=build_user_prompt(question, chunks)))

        # Persist the user turn up front so concurrent /history reads are coherent.
        now = datetime.now(timezone.utc)
        user_turn = ConversationTurn(
            turn_id=str(uuid.uuid4()),
            session_id=session_id,
            role="user",
            content=question,
            citations=None,
            created_at=now,
        )
        await self._history.append(session_id, user_turn)

        stream_start = time.perf_counter()
        first_token_recorded = False
        assistant_parts: list[str] = []
        try:
            async for delta in self._llm.stream_chat(messages):
                if not first_token_recorded:
                    time_to_first_token_seconds.observe(time.perf_counter() - stream_start)
                    first_token_recorded = True
                assistant_parts.append(delta)
                yield QAEvent(type="token", payload={"text": delta})
        finally:
            stream_total_seconds.observe(time.perf_counter() - stream_start)

        yield QAEvent(type="citations", payload=format_citations(retrieved))

        assistant_turn = ConversationTurn(
            turn_id=str(uuid.uuid4()),
            session_id=session_id,
            role="assistant",
            content="".join(assistant_parts),
            citations=[
                Citation(
                    chunk_id=c.chunk_id,
                    document_id=c.document_id,
                    locator=locator_for(c),
                    score=float(score),
                )
                for c, score in retrieved
            ],
            created_at=datetime.now(timezone.utc),
            state="complete",
        )
        await self._history.append(session_id, assistant_turn)

        yield QAEvent(type="done", payload={"turn_id": assistant_turn.turn_id, "stopped": False})

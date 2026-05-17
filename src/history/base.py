from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import datetime


@dataclass(frozen=True)
class Citation:
    chunk_id: str
    document_id: str
    locator: str
    score: float


@dataclass
class ConversationTurn:
    turn_id: str
    session_id: str
    role: str  # 'user' | 'assistant'
    content: str
    citations: list[Citation] | None
    created_at: datetime
    state: str | None = None


class ConversationStore(ABC):
    @abstractmethod
    async def append(self, session_id: str, turn: ConversationTurn) -> None:
        raise NotImplementedError()

    @abstractmethod
    async def get(self, session_id: str) -> list[ConversationTurn]:
        raise NotImplementedError()

    @abstractmethod
    async def drop_session(self, session_id: str) -> None:
        raise NotImplementedError()

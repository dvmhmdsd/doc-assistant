from __future__ import annotations

from abc import ABC, abstractmethod
from collections.abc import AsyncIterator
from dataclasses import dataclass


@dataclass(frozen=True)
class ChatMessage:
    role: str  # 'system' | 'user' | 'assistant'
    content: str


class LLMClient(ABC):
    @property
    @abstractmethod
    def model_name(self) -> str: ...

    @abstractmethod
    def stream_chat(self, messages: list[ChatMessage]) -> AsyncIterator[str]:
        """Yield string deltas from the model as they arrive.

        Implementations are async generator functions (``async def`` with
        ``yield``); calling one returns an ``AsyncIterator[str]``. They
        MUST NOT buffer the full response.
        """
        ...

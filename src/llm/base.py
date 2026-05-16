from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import AsyncIterator, List


@dataclass(frozen=True)
class ChatMessage:
    role: str
    content: str


class LLMClient(ABC):
    @property
    @abstractmethod
    def model_name(self) -> str:
        raise NotImplementedError()

    @abstractmethod
    async def stream_chat(self, messages: List[ChatMessage]) -> AsyncIterator[str]:
        """Yield string deltas from the model as they arrive (token-level or delta strings)."""
        raise NotImplementedError()

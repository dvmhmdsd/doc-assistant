from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import List


@dataclass(frozen=True)
class ParsedSegment:
    text: str
    page_number: int | None
    section_path: str | None
    char_start: int
    char_end: int


class DocumentParser(ABC):
    @abstractmethod
    def parse(self, file_path: str) -> List[ParsedSegment]:
        """Parse a document and return a list of ParsedSegment in reading order.

        This method is synchronous (CPU-bound); callers should offload to a thread when used in async code.
        """
        raise NotImplementedError()

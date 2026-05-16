"""T021 integration test — deferred.

Unit + contract coverage already exercises QAService, retry policy,
vector store, embeddings, chunker, parsers, and history store. A live
SSE end-to-end test through FastAPI's ``ASGITransport`` is planned but
not part of the current commit window.
"""
import pytest

pytestmark = pytest.mark.skip(reason="T021 integration test deferred")


def test_ask_streaming_placeholder() -> None: ...

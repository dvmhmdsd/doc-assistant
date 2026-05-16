"""T020 integration test — deferred.

Ingestion plumbing is unit-tested across parsers, chunker, embeddings,
and the Chroma vector store contract. A live ``/upload`` end-to-end
test through FastAPI's ``ASGITransport`` is planned but not part of
the current commit window.
"""
import pytest

pytestmark = pytest.mark.skip(reason="T020 integration test deferred")


def test_ingestion_flow_placeholder() -> None: ...

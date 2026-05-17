"""Unit tests for :class:`LocalEmbeddingProvider` with the model fully mocked.

Real ``sentence-transformers`` model loading downloads ~90 MB and is slow,
flaky, and network-dependent. These tests verify only the *provider's
contract* (ordering, batching, dimension caching, async offload) by
substituting a stub model.
"""
from __future__ import annotations

import sys
import types
from typing import Any

import pytest


class _StubSentenceTransformer:
    """Deterministic stand-in for sentence_transformers.SentenceTransformer."""

    DIM = 4

    def __init__(self, model_name: str) -> None:
        self.model_name = model_name
        self.encode_calls: list[list[str]] = []

    def get_sentence_embedding_dimension(self) -> int:
        return self.DIM

    def encode(self, batch: list[str], **kwargs: Any) -> list[list[float]]:
        self.encode_calls.append(list(batch))
        # encode each text to [hash%10, len, len/2, 1.0] — deterministic and
        # different per text so order-preservation is observable.
        return [[float(hash(t) % 10), float(len(t)), float(len(t)) / 2, 1.0] for t in batch]


@pytest.fixture
def stub_st(monkeypatch: pytest.MonkeyPatch) -> type[_StubSentenceTransformer]:
    """Install a fake `sentence_transformers` module exposing the stub class."""
    fake = types.ModuleType("sentence_transformers")
    fake.SentenceTransformer = _StubSentenceTransformer  # type: ignore[attr-defined]
    monkeypatch.setitem(sys.modules, "sentence_transformers", fake)
    return _StubSentenceTransformer


@pytest.mark.asyncio
async def test_embed_preserves_order_and_dimensions(
    stub_st: type[_StubSentenceTransformer],
) -> None:
    from src.embeddings.local import LocalEmbeddingProvider

    provider = LocalEmbeddingProvider(model_name="any/stub")
    texts = ["hello world", "another", "third entry"]
    vectors = await provider.embed(texts)

    assert len(vectors) == len(texts)
    for v in vectors:
        assert len(v) == stub_st.DIM
        assert all(isinstance(x, float) for x in v)

    # Order-preservation: the deterministic stub encodes len(text) at index 1.
    assert [v[1] for v in vectors] == [float(len(t)) for t in texts]

    # Dimension is cached and matches the stub's reported dimensionality.
    assert provider.dimensions == stub_st.DIM


@pytest.mark.asyncio
async def test_embed_batches_to_configured_size(stub_st: type[_StubSentenceTransformer]) -> None:
    from src.embeddings.local import LocalEmbeddingProvider

    provider = LocalEmbeddingProvider(model_name="any/stub", batch_size=2)
    texts = [f"t{i}" for i in range(5)]
    vectors = await provider.embed(texts)

    assert len(vectors) == 5
    # 5 texts at batch_size=2 → batches of [2, 2, 1]
    underlying = provider._model  # type: ignore[attr-defined]
    assert underlying is not None
    assert [len(b) for b in underlying.encode_calls] == [2, 2, 1]


@pytest.mark.asyncio
async def test_dimensions_raises_before_first_embed(
    stub_st: type[_StubSentenceTransformer],
) -> None:
    from src.embeddings.local import LocalEmbeddingProvider

    provider = LocalEmbeddingProvider(model_name="any/stub")
    with pytest.raises(RuntimeError, match="dimensions unknown"):
        _ = provider.dimensions

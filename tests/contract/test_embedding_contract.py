"""EmbeddingProvider contract — same suite must hold for every impl.

Both implementations are exercised without network I/O:
- LocalEmbeddingProvider: ``sentence_transformers`` stubbed via
  ``monkeypatch.setitem(sys.modules, ...)``.
- OpenAIEmbeddingProvider: HTTP mocked via ``respx``.
"""
from __future__ import annotations

import json
import sys
import types
from typing import Any

import httpx
import pytest
import respx

from src.embeddings.base import EmbeddingProvider


_OPENAI_URL = "https://api.openai.com/v1/embeddings"


# ---- local stub ----------------------------------------------------

class _StubST:
    DIM = 4

    def __init__(self, model_name: str) -> None:  # noqa: D401
        self.model_name = model_name

    def get_sentence_embedding_dimension(self) -> int:
        return self.DIM

    def encode(self, batch: list[str], **_: Any) -> list[list[float]]:
        return [[float(len(t)), 0.1, 0.2, 0.3] for t in batch]


@pytest.fixture
def local_provider(monkeypatch: pytest.MonkeyPatch) -> EmbeddingProvider:
    fake = types.ModuleType("sentence_transformers")
    fake.SentenceTransformer = _StubST  # type: ignore[attr-defined]
    monkeypatch.setitem(sys.modules, "sentence_transformers", fake)
    from src.embeddings.local import LocalEmbeddingProvider

    return LocalEmbeddingProvider(model_name="stub/model")


# ---- openai stub ---------------------------------------------------

def _openai_response(req: httpx.Request) -> httpx.Response:
    inputs = json.loads(req.content)["input"]
    return httpx.Response(
        200,
        json={
            "object": "list",
            "data": [
                {"object": "embedding", "index": i, "embedding": [float(len(t)), 0.1, 0.2, 0.3]}
                for i, t in enumerate(inputs)
            ],
            "model": "text-embedding-3-small",
            "usage": {"prompt_tokens": 0, "total_tokens": 0},
        },
    )


@pytest.fixture
def openai_provider(respx_mock: respx.MockRouter) -> EmbeddingProvider:
    respx_mock.post(_OPENAI_URL).mock(side_effect=_openai_response)
    from src.embeddings.openai_client import OpenAIEmbeddingProvider

    return OpenAIEmbeddingProvider(api_key="sk-test", model_name="text-embedding-3-small")


# ---- contract suite -------------------------------------------------

@pytest.mark.asyncio
@pytest.mark.parametrize("fixture_name", ["local_provider", "openai_provider"])
async def test_embed_preserves_order_and_returns_fixed_dim_floats(
    fixture_name: str, request: pytest.FixtureRequest
) -> None:
    provider: EmbeddingProvider = request.getfixturevalue(fixture_name)
    texts = ["alpha", "betas", "g"]
    embs = await provider.embed(texts)

    assert len(embs) == len(texts)
    assert all(isinstance(vec, list) for vec in embs)
    assert all(all(isinstance(x, float) for x in vec) for vec in embs)
    # len(text) lives at index 0 in both stubs — order preservation observable.
    assert [v[0] for v in embs] == [float(len(t)) for t in texts]


@pytest.mark.asyncio
@pytest.mark.parametrize("fixture_name", ["local_provider", "openai_provider"])
async def test_dimensions_consistent_across_calls(
    fixture_name: str, request: pytest.FixtureRequest
) -> None:
    provider: EmbeddingProvider = request.getfixturevalue(fixture_name)
    embs1 = await provider.embed(["one"])
    embs2 = await provider.embed(["two", "three"])
    assert provider.dimensions == len(embs1[0]) == len(embs2[0]) == len(embs2[1])

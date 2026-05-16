"""Unit tests for :class:`OpenAIEmbeddingProvider` with HTTP fully mocked.

Hits the OpenAI REST endpoint through ``respx`` so the test runs offline
and deterministically. Verifies the provider's contract (ordering,
batching, dimension caching, request shape).
"""
from __future__ import annotations

import json

import httpx
import pytest
import respx

from src.embeddings.openai_client import OpenAIEmbeddingProvider

_EMBEDDINGS_URL = "https://api.openai.com/v1/embeddings"


def _fake_response(inputs: list[str], dim: int = 4) -> httpx.Response:
    """Build an OpenAI-shaped embeddings response preserving input order."""
    data = [
        {
            "object": "embedding",
            "index": i,
            # Put len(text) at index 1 so order-preservation is observable.
            "embedding": [float(i), float(len(t)), 0.0, 1.0][:dim],
        }
        for i, t in enumerate(inputs)
    ]
    return httpx.Response(
        200,
        json={
            "object": "list",
            "data": data,
            "model": "text-embedding-3-small",
            "usage": {"prompt_tokens": 0, "total_tokens": 0},
        },
    )


def _inputs_from(request: httpx.Request) -> list[str]:
    return list(json.loads(request.content)["input"])


@pytest.mark.asyncio
@respx.mock
async def test_embed_preserves_order_and_known_dim() -> None:
    route = respx.post(_EMBEDDINGS_URL).mock(
        side_effect=lambda request: _fake_response(_inputs_from(request))
    )
    provider = OpenAIEmbeddingProvider(api_key="sk-test", model_name="text-embedding-3-small")
    texts = ["a", "bb", "ccc"]
    vectors = await provider.embed(texts)

    assert route.called
    assert len(vectors) == len(texts)
    # len(text) was placed at index 1 — verifies order preservation.
    assert [v[1] for v in vectors] == [float(len(t)) for t in texts]
    # Known model dim populated up-front from the lookup table.
    assert provider.dimensions == 1536


@pytest.mark.asyncio
@respx.mock
async def test_embed_batches_in_groups_of_batch_size() -> None:
    route = respx.post(_EMBEDDINGS_URL).mock(
        side_effect=lambda request: _fake_response(_inputs_from(request))
    )
    provider = OpenAIEmbeddingProvider(
        api_key="sk-test", model_name="text-embedding-3-small", batch_size=2
    )
    texts = [f"t{i}" for i in range(5)]
    vectors = await provider.embed(texts)

    assert len(vectors) == 5
    # 5 inputs at batch_size=2 → 3 POSTs of size [2, 2, 1].
    assert route.call_count == 3
    sizes = [len(_inputs_from(c.request)) for c in route.calls]
    assert sizes == [2, 2, 1]


def test_constructor_requires_api_key() -> None:
    with pytest.raises(ValueError, match="api_key is required"):
        OpenAIEmbeddingProvider(api_key="")


@pytest.mark.asyncio
@respx.mock
async def test_unknown_model_dimensions_populated_after_first_call() -> None:
    respx.post(_EMBEDDINGS_URL).mock(
        side_effect=lambda request: _fake_response(_inputs_from(request), dim=3)
    )
    provider = OpenAIEmbeddingProvider(api_key="sk-test", model_name="some-unknown-model")
    with pytest.raises(RuntimeError, match="dimensions unknown"):
        _ = provider.dimensions

    await provider.embed(["x"])
    assert provider.dimensions == 3

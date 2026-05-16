"""Embedding provider factory.

Resolves an :class:`EmbeddingProvider` from :class:`Settings`. All
provider-specific selection happens here; service code MUST NOT branch
on ``cfg.embedding_provider`` (constitution Principle V).
"""
from __future__ import annotations

from ..config import Settings, get_settings
from .base import EmbeddingProvider
from .local import LocalEmbeddingProvider
from .openai_client import OpenAIEmbeddingProvider

_DEFAULT_LOCAL_MODEL = "sentence-transformers/all-MiniLM-L6-v2"
_DEFAULT_OPENAI_MODEL = "text-embedding-3-small"


def make_embedding_provider(cfg: Settings | None = None) -> EmbeddingProvider:
    cfg = cfg or get_settings()
    name = cfg.embedding_provider.lower()
    model = cfg.embedding_model

    if name == "local":
        return LocalEmbeddingProvider(model_name=model or _DEFAULT_LOCAL_MODEL)
    if name == "openai":
        if not cfg.openai_api_key:
            raise ValueError("OPENAI_API_KEY must be set when EMBEDDING_PROVIDER=openai")
        return OpenAIEmbeddingProvider(
            api_key=cfg.openai_api_key,
            model_name=model or _DEFAULT_OPENAI_MODEL,
        )

    raise ValueError(f"unsupported embedding provider: {cfg.embedding_provider!r}")

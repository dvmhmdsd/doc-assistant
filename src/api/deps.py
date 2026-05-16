"""FastAPI dependencies + DI provider functions.

Provider functions are cached singletons (`lru_cache`) so every request
sees the same vector store, embedder, history store, etc. — required
for session isolation to actually work (a fresh `SessionService` per
request would lose every session handle).

All routes mount auth via ``Depends(require_bearer_token)``. Auth
failures raise typed :class:`UnauthorizedError` so the global
``app_exception_handler`` renders the OpenAPI ``Error`` schema instead
of FastAPI's default ``{"detail": ...}``.
"""
from __future__ import annotations

import secrets
from functools import lru_cache

from fastapi import Header

from ..chunker.chunker import Chunker
from ..config import Settings, get_settings
from ..embeddings.base import EmbeddingProvider
from ..embeddings.factory import make_embedding_provider
from ..history.base import ConversationStore
from ..history.memory import InMemoryConversationStore
from ..llm.base import LLMClient
from ..llm.factory import make_llm_client
from ..services.ingestion import IngestionService
from ..services.qa import QAService
from ..services.sessions import SessionService
from ..vector_store.base import VectorStore
from ..vector_store.chroma import ChromaVectorStore
from .errors import UnauthorizedError


# ---- auth -----------------------------------------------------------

def require_bearer_token(authorization: str | None = Header(None)) -> None:
    settings = get_settings()
    if not authorization or not authorization.lower().startswith("bearer "):
        raise UnauthorizedError("missing or malformed Authorization header")
    token = authorization.split(None, 1)[1]
    if not secrets.compare_digest(token, settings.app_shared_token):
        raise UnauthorizedError("invalid token")


# ---- singletons -----------------------------------------------------
#
# Each provider is an app-lifetime singleton. `lru_cache(maxsize=1)`
# makes FastAPI's `Depends(provider_fn)` resolve the same instance on
# every request without an explicit DI container.

@lru_cache(maxsize=1)
def _settings() -> Settings:
    return get_settings()


@lru_cache(maxsize=1)
def get_vector_store() -> VectorStore:
    return ChromaVectorStore(persist_directory=_settings().chroma_persist_dir)


@lru_cache(maxsize=1)
def get_history_store() -> ConversationStore:
    return InMemoryConversationStore()


@lru_cache(maxsize=1)
def get_embedder() -> EmbeddingProvider:
    return make_embedding_provider(_settings())


@lru_cache(maxsize=1)
def get_llm_client() -> LLMClient:
    return make_llm_client(_settings())


@lru_cache(maxsize=1)
def get_chunker() -> Chunker:
    cfg = _settings()
    return Chunker(size_tokens=cfg.chunk_size, overlap_tokens=cfg.chunk_overlap)


@lru_cache(maxsize=1)
def get_session_service() -> SessionService:
    return SessionService(get_vector_store(), get_history_store())


@lru_cache(maxsize=1)
def get_ingestion_service() -> IngestionService:
    return IngestionService(get_chunker(), get_embedder(), get_vector_store())


@lru_cache(maxsize=1)
def get_qa_service() -> QAService:
    return QAService(
        embedder=get_embedder(),
        vector_store=get_vector_store(),
        llm=get_llm_client(),
        history_store=get_history_store(),
    )

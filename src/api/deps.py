"""FastAPI dependencies + DI provider functions.

Provider functions are cached singletons (`lru_cache`) so every request
sees the same vector store, embedder, history store, etc. — required
for session isolation to actually work (a fresh `SessionService` per
request would lose every session handle).

Single-tenant demo: no global auth gate. Per-session isolation is
enforced via the opaque ``session_id`` returned by ``POST /upload``;
routes return 404 for unknown ids via ``SessionService.resolve``.
Production deploys MUST front the API with a reverse proxy / API
gateway that enforces authentication.
"""
from __future__ import annotations

from functools import lru_cache

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

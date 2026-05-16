"""Application settings (pydantic-settings).

All tunables MUST flow through this module — no ``os.environ`` reads
elsewhere (constitution Principle V). Adding a new env var requires
updating both this file AND ``.env.example``.
"""
from __future__ import annotations

from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    # --- auth ---
    app_shared_token: str

    # --- providers ---
    llm_provider: str = "anthropic"
    embedding_provider: str = "local"
    llm_model: str | None = None
    embedding_model: str | None = None
    anthropic_api_key: str | None = None
    openai_api_key: str | None = None

    # --- retrieval / chunking ---
    chunk_size: int = 500
    chunk_overlap: int = 50
    top_k_results: int = 5

    # --- uploads ---
    max_upload_bytes: int = 25 * 1024 * 1024

    # --- storage ---
    chroma_persist_dir: str = "./chroma_data"
    upload_tmp_dir: str = "./uploads_tmp"

    # --- retry policy (FR-021) ---
    retry_budget_seconds: float = 5.0
    retry_attempts: int = 3
    retry_max_wait: float = 2.0


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    s = Settings()  # type: ignore[call-arg]
    if not s.app_shared_token:
        raise ValueError("APP_SHARED_TOKEN must be set in environment (.env)")
    return s

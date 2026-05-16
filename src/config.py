"""Config placeholder matching ProviderConfiguration"""
from pydantic import BaseSettings


class Settings(BaseSettings):
    llm_provider: str = "anthropic"
    embedding_provider: str = "local"
    llm_model: str | None = None
    embedding_model: str | None = None
    chunk_size: int = 500
    chunk_overlap: int = 50
    top_k: int = 5
    max_upload_bytes: int = 25 * 1024 * 1024
    app_shared_token: str
    anthropic_api_key: str | None = None
    openai_api_key: str | None = None


def get_settings() -> Settings:
    return Settings()

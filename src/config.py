"""Application settings using pydantic-settings"""
from functools import lru_cache
from pydantic_settings import BaseSettings


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

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    s = Settings()
    if not s.app_shared_token:
        raise ValueError("APP_SHARED_TOKEN must be set in environment (.env)")
    return s

from __future__ import annotations

from ..config import Settings, get_settings
from .base import LLMClient


def make_llm_client(cfg: Settings | None = None) -> LLMClient:
    cfg = cfg or get_settings()
    name = cfg.llm_provider.lower()
    model = cfg.llm_model or ""

    if name == "openai":
        if not cfg.openai_api_key:
            raise ValueError("OPENAI_API_KEY must be set when LLM_PROVIDER=openai")
        from .openai_client import OpenAILLMClient

        return OpenAILLMClient(api_key=cfg.openai_api_key, model_name=model or "gpt-4o-mini")

    if name == "anthropic":
        if not cfg.anthropic_api_key:
            raise ValueError("ANTHROPIC_API_KEY must be set when LLM_PROVIDER=anthropic")
        from .anthropic_client import AnthropicLLMClient

        return AnthropicLLMClient(api_key=cfg.anthropic_api_key, model_name=model or "claude-2.1")

    raise ValueError(f"unsupported llm provider: {cfg.llm_provider!r}")

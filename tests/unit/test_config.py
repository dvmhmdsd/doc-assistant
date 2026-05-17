"""Unit tests for Settings + get_settings (T013).

``get_settings`` is ``@lru_cache``d. ``conftest.py`` auto-clears every
cached provider around each test so monkeypatched env changes are seen.
"""
from __future__ import annotations

import pytest

from src.config import Settings, get_settings


def test_default_provider_selection(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("LLM_PROVIDER", raising=False)
    monkeypatch.delenv("EMBEDDING_PROVIDER", raising=False)
    cfg = get_settings()
    assert isinstance(cfg, Settings)
    assert cfg.llm_provider == "anthropic"
    assert cfg.embedding_provider == "local"


def test_explicit_provider_overrides(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("LLM_PROVIDER", "openai")
    monkeypatch.setenv("EMBEDDING_PROVIDER", "openai")
    cfg = get_settings()
    assert cfg.llm_provider == "openai"
    assert cfg.embedding_provider == "openai"


def test_settings_returns_cached_instance() -> None:
    assert get_settings() is get_settings()

"""Unit tests for Settings + get_settings (T013).

``get_settings`` is ``@lru_cache``d. ``conftest.py`` auto-clears every
cached provider around each test so monkeypatched env changes are seen.
"""
from __future__ import annotations

import pytest

from src.config import Settings, get_settings


def test_get_settings_refuses_missing_shared_token(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("APP_SHARED_TOKEN", raising=False)
    with pytest.raises(ValueError, match="APP_SHARED_TOKEN"):
        get_settings()


def test_get_settings_reads_app_shared_token_from_env(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("APP_SHARED_TOKEN", "secret-token")
    cfg = get_settings()
    assert isinstance(cfg, Settings)
    assert cfg.app_shared_token == "secret-token"


def test_default_provider_selection(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("APP_SHARED_TOKEN", "x")
    monkeypatch.delenv("LLM_PROVIDER", raising=False)
    monkeypatch.delenv("EMBEDDING_PROVIDER", raising=False)
    cfg = get_settings()
    assert cfg.llm_provider == "anthropic"
    assert cfg.embedding_provider == "local"


def test_explicit_provider_overrides(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("APP_SHARED_TOKEN", "x")
    monkeypatch.setenv("LLM_PROVIDER", "openai")
    monkeypatch.setenv("EMBEDDING_PROVIDER", "openai")
    cfg = get_settings()
    assert cfg.llm_provider == "openai"
    assert cfg.embedding_provider == "openai"


def test_settings_returns_cached_instance(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("APP_SHARED_TOKEN", "x")
    assert get_settings() is get_settings()

"""Unit tests for the bearer-token auth dependency (T014)."""
from __future__ import annotations

import pytest

from src.api.deps import require_bearer_token
from src.api.errors import UnauthorizedError


def test_missing_header_raises(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("APP_SHARED_TOKEN", "secret")
    with pytest.raises(UnauthorizedError):
        require_bearer_token(None)


def test_malformed_header_raises(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("APP_SHARED_TOKEN", "secret")
    with pytest.raises(UnauthorizedError):
        require_bearer_token("secret")  # missing "Bearer " prefix


def test_wrong_token_raises(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("APP_SHARED_TOKEN", "secret")
    with pytest.raises(UnauthorizedError):
        require_bearer_token("Bearer wrong")


def test_correct_token_accepts(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("APP_SHARED_TOKEN", "secret")
    assert require_bearer_token("Bearer secret") is None


def test_lowercase_scheme_accepted(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("APP_SHARED_TOKEN", "secret")
    assert require_bearer_token("bearer secret") is None

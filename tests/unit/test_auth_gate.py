import pytest

from src.api.deps import require_bearer_token


def test_require_bearer_token_missing(monkeypatch):
    monkeypatch.setenv("APP_SHARED_TOKEN", "tok")
    with pytest.raises(Exception):
        require_bearer_token(None)


def test_require_bearer_token_invalid(monkeypatch):
    monkeypatch.setenv("APP_SHARED_TOKEN", "tok")
    with pytest.raises(Exception):
        require_bearer_token("Bearer wrong")

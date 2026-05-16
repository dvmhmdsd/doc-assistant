import os
import pytest

from src.config import get_settings, Settings


def test_get_settings_requires_token(monkeypatch):
    monkeypatch.delenv("APP_SHARED_TOKEN", raising=False)
    with pytest.raises(ValueError):
        get_settings()


def test_get_settings_reads_env(monkeypatch):
    monkeypatch.setenv("APP_SHARED_TOKEN", "s3cr3t")
    s = get_settings()
    assert isinstance(s, Settings)
    assert s.app_shared_token == "s3cr3t"

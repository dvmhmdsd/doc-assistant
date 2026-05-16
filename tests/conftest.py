"""Shared pytest fixtures.

Every `@lru_cache`d provider in ``src/api/deps`` and ``src/config`` holds
singletons across calls. Tests must run in isolation, so we clear those
caches automatically around each test. Without this:
- ``test_config`` sees stale Settings from a prior test's env.
- Integration tests share the same VectorStore / SessionService across
  cases → leaky session state.
"""
from __future__ import annotations

from collections.abc import Iterator

import pytest


@pytest.fixture(autouse=True)
def _clear_di_caches() -> Iterator[None]:
    from src import config
    from src.api import deps

    def _clear() -> None:
        for module in (config, deps):
            for name in dir(module):
                obj = getattr(module, name, None)
                if obj is not None and hasattr(obj, "cache_clear"):
                    try:
                        obj.cache_clear()
                    except Exception:  # noqa: BLE001 - best-effort cleanup
                        pass

    _clear()
    yield
    _clear()

"""Shared pytest fixtures.

Every ``@lru_cache``d provider in ``src/api/deps`` and ``src/config``
holds singletons across calls. Tests must run in isolation, so we clear
those caches automatically around each test. Without this:
- ``test_config`` sees stale Settings from a prior test's env.
- Integration tests share the same VectorStore / SessionService across
  cases → leaky session state.

Module import resolution: ``pyproject.toml`` sets
``[tool.pytest.ini_options] pythonpath = ["."]`` for new installs, but
older pytest binaries baked into the runtime image may not honor that.
The ``sys.path`` shim below is a belt-and-braces fallback that keeps
``from src import …`` working regardless of how pytest is invoked.
"""
from __future__ import annotations

import sys
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parent.parent
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

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

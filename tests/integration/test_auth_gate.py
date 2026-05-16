"""T022 integration test — deferred.

The auth-gate dependency itself is unit-tested in
``tests/unit/test_auth_gate.py``. End-to-end auth coverage across
all routes is planned but not part of the current commit window.
"""
import pytest

pytestmark = pytest.mark.skip(reason="T022 integration test deferred")


def test_auth_gate_placeholder() -> None: ...

"""SPA static mount + API routing precedence (T011)."""
from __future__ import annotations

from fastapi.testclient import TestClient

from src.api.app import create_app


def test_root_serves_spa_index() -> None:
    """`GET /` returns the SPA `index.html` (text/html)."""
    client = TestClient(create_app())

    resp = client.get("/")

    assert resp.status_code == 200
    assert "text/html" in resp.headers.get("content-type", "")


def test_api_route_takes_precedence_over_static_mount() -> None:
    """`/upload` must still resolve to the upload route, not the SPA index."""
    client = TestClient(create_app())

    resp = client.get("/upload")

    # GET is not allowed on the POST-only upload route — but crucially the
    # response must NOT be the SPA index (would indicate static mount
    # accidentally swallowed the API path).
    assert resp.status_code != 200 or "text/html" not in resp.headers.get(
        "content-type", ""
    )

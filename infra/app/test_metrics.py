"""Tests for the request metrics middleware, against a small stand-in app.

Run without touching the project environment:
  uv run --no-project --with fastapi --with httpx --with pytest \
    --with prometheus-client==0.22.1 pytest infra/app -q
"""

from __future__ import annotations

import pytest
from fastapi import FastAPI, HTTPException
from fastapi.testclient import TestClient
from prometheus_client import REGISTRY

from metrics import UNMATCHED, instrument


def _app() -> FastAPI:
    app = FastAPI()

    @app.get("/api/artist")
    def artist(name: str) -> dict[str, str]:
        if name == "missing":
            raise HTTPException(status_code=404, detail="nope")
        return {"name": name}

    @app.get("/api/song/{song_id}")
    def song(song_id: int) -> dict[str, int]:
        return {"id": song_id}

    @app.get("/api/boom")
    def boom() -> None:
        raise RuntimeError("database is down")

    return instrument(app)


def _count(route: str, status: str, method: str = "GET") -> float:
    value = REGISTRY.get_sample_value(
        "lyricstats_http_requests_total",
        {"method": method, "route": route, "status": status},
    )
    return value or 0.0


@pytest.fixture
def client() -> TestClient:
    return TestClient(_app(), raise_server_exceptions=False)


def test_counts_requests_by_route_template_and_status(client: TestClient) -> None:
    before_ok = _count("/api/artist", "200")
    before_404 = _count("/api/artist", "404")

    assert client.get("/api/artist", params={"name": "Taylor Swift"}).status_code == 200
    assert client.get("/api/artist", params={"name": "missing"}).status_code == 404

    assert _count("/api/artist", "200") == before_ok + 1
    assert _count("/api/artist", "404") == before_404 + 1


def test_path_parameters_do_not_create_new_series(client: TestClient) -> None:
    before = _count("/api/song/{song_id}", "200")

    for song_id in (1, 2, 3):
        client.get(f"/api/song/{song_id}")

    assert _count("/api/song/{song_id}", "200") == before + 3
    assert _count("/api/song/1", "200") == 0


def test_unhandled_exception_is_recorded_as_500(client: TestClient) -> None:
    before = _count("/api/boom", "500")

    assert client.get("/api/boom").status_code == 500

    assert _count("/api/boom", "500") == before + 1


def test_unknown_paths_share_one_label(client: TestClient) -> None:
    before = _count(UNMATCHED, "404")

    client.get("/does-not-exist")
    client.get("/also/not/here")

    assert _count(UNMATCHED, "404") == before + 2


def test_latency_is_observed_and_in_flight_returns_to_zero(client: TestClient) -> None:
    labels = {"method": "GET", "route": "/api/artist"}
    before = REGISTRY.get_sample_value("lyricstats_http_request_duration_seconds_count", labels) or 0

    client.get("/api/artist", params={"name": "x"})

    after = REGISTRY.get_sample_value("lyricstats_http_request_duration_seconds_count", labels)
    assert after == before + 1
    assert REGISTRY.get_sample_value("lyricstats_http_requests_in_flight") == 0


def test_metrics_endpoint_exposes_prometheus_text(client: TestClient) -> None:
    client.get("/api/artist", params={"name": "x"})

    response = client.get("/metrics")

    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/plain")
    assert "lyricstats_http_requests_total" in response.text

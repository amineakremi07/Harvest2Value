"""Error envelope (v2 only), v1 error formats unchanged, request id, CORS allow-list (R12), body limit."""

from __future__ import annotations

from collections.abc import Callable, Iterator

import pytest
from fastapi import Body
from fastapi.testclient import TestClient

from app.core.errors import ValidationFailed


@pytest.fixture
def client(make_client: Callable[..., TestClient]) -> TestClient:
    client = make_client(max_body_bytes=2048)
    app = client.app

    @app.get("/api/v2/_test/app-error")  # type: ignore[attr-defined]
    async def app_error() -> None:
        raise ValidationFailed("Harvest must be positive.", details={"field": "harvest_kg"})

    @app.get("/api/v2/_test/crash")  # type: ignore[attr-defined]
    async def crash() -> None:
        raise RuntimeError("secret internal detail")

    @app.post("/api/v2/_test/echo")  # type: ignore[attr-defined]
    async def echo(payload: dict = Body(...)) -> dict:
        return payload

    return client


def assert_envelope(response, status: int, code: str) -> dict:
    assert response.status_code == status
    error = response.json()["error"]
    assert error["code"] == code
    assert error["request_id"] and error["request_id"] == response.headers["x-request-id"]
    return error


# ---- v2 envelope ----

def test_app_error_envelope(client: TestClient) -> None:
    error = assert_envelope(client.get("/api/v2/_test/app-error"), 422, "VALIDATION_ERROR")
    assert error["message"] == "Harvest must be positive."
    assert error["details"] == {"field": "harvest_kg"}


def test_unknown_v2_route_is_enveloped_404(client: TestClient) -> None:
    assert_envelope(client.get("/api/v2/does-not-exist"), 404, "NOT_FOUND")


def test_request_validation_error_is_enveloped(client: TestClient) -> None:
    error = assert_envelope(client.post("/api/v2/_test/echo", content=b"[1,2]", headers={"content-type": "application/json"}), 422, "VALIDATION_ERROR")
    assert error["details"]["errors"][0]["loc"] == ["body"]


def test_unhandled_error_is_generic_500_without_internals(client: TestClient) -> None:
    response = client.get("/api/v2/_test/crash")
    error = assert_envelope(response, 500, "INTERNAL_ERROR")
    assert "secret internal detail" not in response.text
    assert "request id" in error["message"]


# ---- v1 formats unchanged ----

def test_v1_unknown_route_keeps_default_format(client: TestClient) -> None:
    response = client.get("/api/v1/does-not-exist")
    assert response.status_code == 404 and response.json() == {"detail": "Not Found"}


def test_v1_validation_keeps_default_format(client: TestClient) -> None:
    response = client.post("/api/v1/optimize", json={})
    assert response.status_code == 422
    assert isinstance(response.json()["detail"], list) and "error" not in response.json()


# ---- request id ----

def test_request_id_is_generated_and_echoed(client: TestClient) -> None:
    assert len(client.get("/api/v2/health").headers["x-request-id"]) == 36
    assert client.get("/health").headers["x-request-id"]


def test_safe_incoming_request_id_is_reused(client: TestClient) -> None:
    assert client.get("/api/v2/health", headers={"X-Request-ID": "trace-42"}).headers["x-request-id"] == "trace-42"


def test_unsafe_incoming_request_id_is_replaced(client: TestClient) -> None:
    rid = client.get("/api/v2/health", headers={"X-Request-ID": "bad id<script>"}).headers["x-request-id"]
    assert rid != "bad id<script>" and len(rid) == 36


# ---- CORS (R12) ----

def preflight(client: TestClient, origin: str):
    return client.options(
        "/api/v1/optimize",
        headers={"Origin": origin, "Access-Control-Request-Method": "POST", "Access-Control-Request-Headers": "content-type"},
    )


def test_cors_allows_configured_frontend_origin(client: TestClient) -> None:
    response = preflight(client, "http://localhost:5173")
    assert response.status_code == 200
    assert response.headers["access-control-allow-origin"] == "http://localhost:5173"
    assert "access-control-allow-credentials" not in response.headers


def test_cors_rejects_unknown_origin(client: TestClient) -> None:
    response = preflight(client, "https://evil.example")
    assert response.status_code == 400
    assert "access-control-allow-origin" not in response.headers
    simple = client.get("/api/v2/health", headers={"Origin": "https://evil.example"})
    assert "access-control-allow-origin" not in simple.headers


# ---- body size ----

def test_declared_oversized_body_is_413_before_reaching_the_app(client: TestClient) -> None:
    response = client.post("/api/v2/_test/echo", content=b"{" + b" " * 3000 + b"}", headers={"content-type": "application/json"})
    error = assert_envelope(response, 413, "PAYLOAD_TOO_LARGE")
    assert error["details"] == {"max_bytes": 2048}


def test_streamed_oversized_body_is_413(client: TestClient) -> None:
    def chunks() -> Iterator[bytes]:
        yield b'{"a": "'
        yield b"x" * 3000
        yield b'"}'

    response = client.post("/api/v2/_test/echo", content=chunks(), headers={"content-type": "application/json"})
    assert "content-length" not in response.request.headers
    assert_envelope(response, 413, "PAYLOAD_TOO_LARGE")


def test_small_body_passes(client: TestClient) -> None:
    assert client.post("/api/v2/_test/echo", json={"ok": True}).json() == {"ok": True}

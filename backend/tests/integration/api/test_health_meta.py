"""v2 health/readiness/meta. R11: readiness stays green without an LLM key."""

from collections.abc import Callable

from fastapi.testclient import TestClient


def test_health(make_client: Callable[..., TestClient]) -> None:
    r = make_client().get("/api/v2/health")
    assert r.status_code == 200 and r.json() == {"status": "ok"}


def test_ready_without_llm_key_is_still_ready(make_client: Callable[..., TestClient]) -> None:
    r = make_client().get("/api/v2/health/ready")
    assert r.status_code == 200
    body = r.json()
    assert body["status"] == "ready"
    assert body["checks"]["solver"]["status"] == "ok"
    assert body["checks"]["llm"] == {"provider": "groq", "model": "openai/gpt-oss-120b", "configured": False}


def test_ready_with_configured_provider(make_client: Callable[..., TestClient]) -> None:
    llm = make_client(llm_provider="nvidia_nim", llm_api_key="k").get("/api/v2/health/ready").json()["checks"]["llm"]
    assert llm == {"provider": "nvidia_nim", "model": "meta/llama-3.1-70b-instruct", "configured": True}


def test_ready_reports_unavailable_solver(make_client: Callable[..., TestClient], monkeypatch) -> None:
    from app.api.v2 import health

    monkeypatch.setattr(health, "_cbc_available", lambda: False)
    r = make_client().get("/api/v2/health/ready")
    assert r.status_code == 503 and r.json()["status"] == "not_ready"


def test_meta(make_client: Callable[..., TestClient]) -> None:
    body = make_client(llm_provider="mock", max_body_bytes=5000).get("/api/v2/meta").json()
    assert body["api_version"] == "v2"
    assert body["llm"]["configured"] is True
    assert body["limits"] == {"max_body_bytes": 5000, "solver_time_limit_s": 30}
    live = {"datasets", "runs", "scenarios", "explainability", "copilot", "reports"}
    assert {k for k, v in body["features"].items() if v} == live
    assert "weighted" in body["objectives"] and "interrupted" in body["run_statuses"]
    ops = {o["op"]: o for o in body["change_ops"]}
    assert len(ops) == 16 and ops["buyer_price"]["target"] == "one_or_all" and ops["add_buyer"]["target"] == "none"
    assert "mode" in ops["buyer_price"]["params_schema"]["properties"]


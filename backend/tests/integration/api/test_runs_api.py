"""Runs API: lifecycle, infeasible runs, cache, concurrency (R5), timeout, failures, startup recovery,
cancel, rerun, delete, queue limit."""

from __future__ import annotations

import time
from collections.abc import Callable
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.db.models import OptimizationRun
from app.db.session import unit_of_work
from tests.fixtures.api import (
    API,
    CrashingEngine,
    NotSolvedEngine,
    SlowEngine,
    create_dataset,
    error_code,
    start_run,
    wait_for,
    wait_until_status,
)
from tests.fixtures.builders import buyer, lot, payload_dict, vehicle


@pytest.fixture
def client(make_client: Callable[..., TestClient]) -> TestClient:
    return make_client()


def test_full_lifecycle_queued_to_succeeded(client: TestClient) -> None:
    dataset_id = create_dataset(client)
    client.app.state.optimization_engine = SlowEngine(0.5)
    r = client.post(f"{API}/runs", json={"dataset_id": dataset_id, "label": "baseline"})
    assert r.status_code == 202
    created = r.json()
    assert created["status"] in ("queued", "running") and created["label"] == "baseline" and created["cache_hit"] is False
    assert created["version_no"] == 1 and created["objective"] == "profit"
    assert len(created["effective_input_hash"]) == 64 and len(created["config_hash"]) == 64

    early = client.get(f"{API}/runs/{created['id']}/result")
    assert early.status_code == 409 and error_code(early) == "RUN_NOT_FINISHED"

    done = wait_for(client, created["id"])
    assert done["status"] == "succeeded" and done["solver_outcome"] == "optimal" and done["mip_gap"] == 0.01
    assert done["started_at"] and done["finished_at"] and done["solve_seconds"] is not None and done["error"] is None
    assert done["headline"]["realized_profit"] > 0

    result = client.get(f"{API}/runs/{created['id']}/result").json()
    assert result["kpis"]["realized_profit"] == done["headline"]["realized_profit"]
    assert result["kpis"]["harvest_kg"] == 12000 and result["buyers"] and result["allocations"]
    assert any(c["dual"] is not None for c in result["constraints"])

    listing = client.get(f"{API}/runs", params={"dataset_id": dataset_id, "status": "succeeded"}).json()
    assert listing["total"] == 1 and listing["items"][0]["id"] == created["id"]
    assert client.get(f"{API}/runs", params={"status": "failed"}).json()["total"] == 0


def test_wait_returns_the_finished_run(client: TestClient) -> None:
    r = client.post(f"{API}/runs?wait=15", json={"dataset_id": create_dataset(client)})
    assert r.status_code == 200 and r.json()["status"] == "succeeded"


def test_infeasible_is_not_an_http_error(client: TestClient) -> None:
    payload = payload_dict(lots=[lot("l1", 1000)], buyers=[buyer("b1", demand=3000, min_contract_kg=2000)])
    r = client.post(f"{API}/runs?wait=15", json={"dataset_id": create_dataset(client, payload=payload)})
    assert r.status_code == 200
    detail = r.json()
    assert detail["status"] == "infeasible" and detail["solver_outcome"] == "infeasible"
    assert detail["diagnostics"]["conflicts"] == [
        {"key": "demand_min|b1|", "family": "demand_min", "label": "Contracted minimum of B1", "relaxation_needed": 1000.0, "unit": "kg"}
    ]
    result = client.get(f"{API}/runs/{detail['id']}/result")
    assert result.status_code == 409 and error_code(result) == "RUN_INFEASIBLE"
    assert client.get(f"{API}/runs/{detail['id']}/diagnostics").json()["conflicts"][0]["relaxation_needed"] == 1000


def test_diagnostics_only_for_infeasible_runs(client: TestClient) -> None:
    run = start_run(client, create_dataset(client))
    r = client.get(f"{API}/runs/{run['id']}/diagnostics")
    assert r.status_code == 409 and error_code(r) == "RUN_NOT_INFEASIBLE"


def test_cache_reuses_an_identical_run(client: TestClient) -> None:
    dataset_id = create_dataset(client)
    first = start_run(client, dataset_id)
    r = client.post(f"{API}/runs", json={"dataset_id": dataset_id})
    assert r.status_code == 200 and r.json()["id"] == first["id"] and r.json()["cache_hit"] is True

    # same data through another dataset: same effective_input_hash -> same run
    twin = start_run(client, create_dataset(client))
    assert twin["id"] == first["id"] and twin["effective_input_hash"] == first["effective_input_hash"]

    other_config = start_run(client, dataset_id, config={"objective": "revenue"})
    assert other_config["id"] != first["id"] and other_config["config_hash"] != first["config_hash"]
    forced = start_run(client, dataset_id, use_cache=False)
    assert forced["id"] != first["id"] and forced["cache_hit"] is False
    assert client.get(f"{API}/runs").json()["total"] == 3


def test_r5_health_answers_during_a_long_run(client: TestClient) -> None:
    """R5 (audit): the solver used to block the event loop. A 2 s run must not delay /health."""
    dataset_id = create_dataset(client)
    client.app.state.optimization_engine = SlowEngine(2.0)
    run = start_run(client, dataset_id, wait=0, expect=202)
    wait_until_status(client, run["id"], "running")
    for path in ("/api/v2/health", "/health"):
        started = time.perf_counter()
        assert client.get(path).status_code == 200
        assert time.perf_counter() - started < 0.5
    assert client.get(f"{API}/runs/{run['id']}").json()["status"] == "running"
    assert wait_for(client, run["id"])["status"] == "succeeded"


def test_timeout_without_solution(client: TestClient) -> None:
    dataset_id = create_dataset(client)
    client.app.state.optimization_engine = NotSolvedEngine()
    detail = start_run(client, dataset_id, config={"time_limit_s": 1}, expect=200)
    assert detail["status"] == "timeout" and detail["solver_outcome"] == "not_solved"
    assert detail["error"]["code"] == "SOLVER_TIMEOUT" and "time limit" in detail["error"]["message"]
    r = client.get(f"{API}/runs/{detail['id']}/result")
    assert r.status_code == 409 and error_code(r) == "RUN_NO_RESULT"


def test_unexpected_failure_is_recorded_without_leaking_details(client: TestClient) -> None:
    dataset_id = create_dataset(client)
    client.app.state.optimization_engine = CrashingEngine()
    detail = start_run(client, dataset_id, expect=200)
    assert detail["status"] == "failed" and detail["error"]["code"] == "INTERNAL_ERROR"
    assert "secret" not in detail["error"]["message"]


def test_startup_marks_unfinished_runs_interrupted(make_client: Callable[..., TestClient], tmp_path: Path) -> None:
    url = f"sqlite:///{(tmp_path / 'recover.db').as_posix()}"
    first = make_client(database_url=url)
    run = start_run(first, create_dataset(first))
    with unit_of_work(first.app.state.session_factory) as session:
        stuck = session.get(OptimizationRun, run["id"])
        clones = []
        for status in ("queued", "running"):
            clone = OptimizationRun(**{c.name: getattr(stuck, c.name) for c in OptimizationRun.__table__.columns if c.name not in ("id", "created_at", "updated_at")})
            clone.status = status
            session.add(clone)
            clones.append(clone)
        session.flush()
        ids = [c.id for c in clones]
    first.__exit__(None, None, None)

    second = make_client(database_url=url)
    for run_id in ids:
        detail = second.get(f"{API}/runs/{run_id}").json()
        assert detail["status"] == "interrupted" and detail["error"]["code"] == "INTERRUPTED" and detail["finished_at"]
    assert second.get(f"{API}/runs/{run['id']}").json()["status"] == "succeeded"


def test_only_a_queued_run_can_be_cancelled(make_client: Callable[..., TestClient]) -> None:
    client = make_client(solver_max_concurrency=1)
    dataset_id = create_dataset(client)
    client.app.state.optimization_engine = SlowEngine(1.0)
    running = start_run(client, dataset_id, wait=0, expect=202)
    queued = start_run(client, dataset_id, wait=0, expect=202, config={"objective": "revenue"})
    wait_until_status(client, running["id"], "running")
    assert client.get(f"{API}/runs/{queued['id']}").json()["status"] == "queued"

    r = client.post(f"{API}/runs/{running['id']}/cancel")
    assert r.status_code == 409 and error_code(r) == "NOT_CANCELLABLE"
    r = client.post(f"{API}/runs/{queued['id']}/cancel")
    assert r.status_code == 200 and r.json()["status"] == "cancelled"

    assert wait_for(client, running["id"])["status"] == "succeeded"
    time.sleep(0.3)  # the cancelled job gets its slot and must skip
    assert client.get(f"{API}/runs/{queued['id']}").json()["status"] == "cancelled"


def test_rerun_with_overrides_keeps_the_frozen_input(client: TestClient) -> None:
    dataset_id = create_dataset(client)
    source = start_run(client, dataset_id)
    r = client.post(f"{API}/runs/{source['id']}/rerun?wait=15", json={"config_overrides": {"objective": "revenue"}, "label": "revenue"})
    assert r.status_code == 200
    rerun = r.json()
    assert rerun["id"] != source["id"] and rerun["config"]["objective"] == "revenue" and rerun["label"] == "revenue"
    assert rerun["effective_input_hash"] == source["effective_input_hash"]
    same = client.post(f"{API}/runs/{source['id']}/rerun", json={})
    assert same.json()["id"] == source["id"] and same.json()["cache_hit"] is True
    bad = client.post(f"{API}/runs/{source['id']}/rerun", json={"config_overrides": {"objective": "cost"}})
    assert bad.status_code == 422 and error_code(bad) == "CONFIG_INVALID"


def test_delete(client: TestClient) -> None:
    dataset_id = create_dataset(client)
    client.app.state.optimization_engine = SlowEngine(1.0)
    run = start_run(client, dataset_id, wait=0, expect=202)
    wait_until_status(client, run["id"], "running")
    r = client.delete(f"{API}/runs/{run['id']}")
    assert r.status_code == 409 and error_code(r) == "RUN_RUNNING"
    wait_for(client, run["id"])
    assert client.delete(f"{API}/runs/{run['id']}").status_code == 204
    assert client.get(f"{API}/runs/{run['id']}").status_code == 404


def test_request_errors(client: TestClient) -> None:
    dataset_id = create_dataset(client)
    assert error_code(client.post(f"{API}/runs", json={"dataset_id": "nope"})) == "NOT_FOUND"
    assert client.post(f"{API}/runs", json={"dataset_id": dataset_id, "version_no": 9}).status_code == 404
    r = client.post(f"{API}/runs", json={"dataset_id": dataset_id, "config": {"crop_id": "wheat"}})
    assert r.status_code == 422 and error_code(r) == "CONFIG_INVALID"
    r = client.post(f"{API}/runs", json={})
    assert r.status_code == 422 and error_code(r) == "VALIDATION_ERROR"
    assert client.post(f"{API}/runs?wait=20", json={"dataset_id": dataset_id}).status_code == 422

    blocked = payload_dict(lots=[lot("l1", 1000)], buyers=[buyer("b1")], vehicles=[vehicle(count=0)])
    r = client.post(f"{API}/runs", json={"dataset_id": create_dataset(client, payload=blocked)})
    assert r.status_code == 422 and error_code(r) == "DATASET_INVALID"
    assert client.get(f"{API}/runs/nope").status_code == 404


def test_full_queue_answers_503(client: TestClient) -> None:
    dataset_id = create_dataset(client)
    client.app.state.executor.max_pending = 0
    r = client.post(f"{API}/runs", json={"dataset_id": dataset_id})
    assert r.status_code == 503 and error_code(r) == "SOLVER_BUSY"
    assert client.get(f"{API}/runs").json()["total"] == 0  # nothing was queued

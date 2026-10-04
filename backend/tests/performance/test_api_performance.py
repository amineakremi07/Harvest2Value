"""Performance budgets of the API (phase 14). Solver times are covered in
tests/regression/test_audit_solver.py (every template < 5 s); here: read endpoints after a run,
report snapshots, and concurrent reads while the solver works.

Budgets are generous for CI machines; they catch regressions of an order of magnitude (an endpoint
that starts re-solving, an N+1 query), not micro-optimizations."""

from __future__ import annotations

import statistics
import time
from collections.abc import Callable
from concurrent.futures import ThreadPoolExecutor

import pytest
from fastapi.testclient import TestClient

from tests.fixtures.api import API, create_dataset, start_run

READ_BUDGET_S = 1.0  # p95 of a warm read
REPORT_BUDGET_S = 3.0


@pytest.fixture(scope="module")
def ready(tmp_path_factory: pytest.TempPathFactory) -> tuple[TestClient, str, str]:
    from app.core.config import Settings
    from app.main import create_app

    db = tmp_path_factory.mktemp("perf") / "perf.db"
    client = TestClient(create_app(Settings(_env_file=None, database_url=f"sqlite:///{db.as_posix()}", llm_provider="mock")))  # type: ignore[call-arg]
    client.__enter__()
    dataset_id = create_dataset(client, template="tunisia_olives")
    base = start_run(client, dataset_id)
    other = start_run(client, dataset_id, config={"objective": "revenue"}, use_cache=False)
    assert base["status"] == other["status"] == "succeeded"
    yield client, base["id"], other["id"]
    client.__exit__(None, None, None)


def p95(samples: list[float]) -> float:
    return statistics.quantiles(samples, n=20)[-1] if len(samples) >= 2 else samples[0]


def timed(call: Callable[[], object], repeat: int = 10) -> list[float]:
    call()  # warm-up (first explanation / analytics computation is cached afterwards)
    out = []
    for _ in range(repeat):
        started = time.perf_counter()
        call()
        out.append(time.perf_counter() - started)
    return out


@pytest.mark.parametrize(
    "path",
    [
        "/runs/{run}",
        "/runs/{run}/result",
        "/runs/{run}/explanation",
        "/runs/{run}/bottlenecks",
        "/runs/{run}/insights",
        "/runs/{run}/network",
        "/analytics/runs/{run}/financial",
        "/analytics/runs/{run}/operational",
        "/analytics/runs/{run}/buyers",
        "/analytics/runs/{run}/logistics",
        "/analytics/runs/{run}/crops",
        "/analytics/dashboard",
        "/runs",
        "/datasets",
    ],
)
def test_read_endpoints_are_fast(ready: tuple[TestClient, str, str], path: str) -> None:
    client, run_id, _ = ready
    url = API + path.format(run=run_id)

    def call() -> None:
        assert client.get(url).status_code == 200

    samples = timed(call)
    assert p95(samples) < READ_BUDGET_S, f"{path}: p95 {p95(samples):.3f}s"


def test_comparison_is_fast(ready: tuple[TestClient, str, str]) -> None:
    client, base, other = ready

    def call() -> None:
        assert client.post(f"{API}/comparisons", json={"baseline_run_id": base, "run_ids": [other]}).status_code == 200

    assert p95(timed(call)) < READ_BUDGET_S


def test_full_report_snapshot_is_fast(ready: tuple[TestClient, str, str]) -> None:
    client, base, other = ready
    spec = {
        "title": "Perf",
        "run_id": base,
        "compare_run_ids": [other],
        "sections": ["summary", "financial", "operational", "buyers", "logistics", "crops", "insights", "comparison"],
    }
    started = time.perf_counter()
    assert client.post(f"{API}/reports", json=spec).status_code == 201
    assert time.perf_counter() - started < REPORT_BUDGET_S


def test_concurrent_reads(ready: tuple[TestClient, str, str]) -> None:
    """40 reads from 8 threads: no error, and the whole batch stays within a few seconds."""
    client, run_id, _ = ready
    urls = [f"{API}/runs/{run_id}/result", f"{API}/analytics/runs/{run_id}/financial", f"{API}/runs/{run_id}/explanation", f"{API}/runs"] * 10
    started = time.perf_counter()
    with ThreadPoolExecutor(max_workers=8) as pool:
        statuses = list(pool.map(lambda u: client.get(u).status_code, urls))
    elapsed = time.perf_counter() - started
    assert statuses == [200] * len(urls)
    assert elapsed < 8.0, f"{elapsed:.2f}s"

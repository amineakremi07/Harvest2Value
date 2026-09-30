"""Helpers for v2 API tests: datasets, runs, and engines that are slow, time out or crash."""

from __future__ import annotations

import time
from typing import Any

from fastapi.testclient import TestClient

from app.domain.dataset import DatasetPayload
from app.domain.enums import SolverOutcome
from app.domain.run_config import RunConfig
from app.optimization.engine import EngineOutput, OptimizationEngine

API = "/api/v2"
TERMINAL = {"succeeded", "infeasible", "timeout", "failed", "cancelled", "interrupted"}


def error_code(r: Any) -> str:
    return r.json()["error"]["code"]


def create_dataset(client: TestClient, *, template: str = "tunisia_olives", payload: dict[str, Any] | None = None, name: str = "Test") -> str:
    body = {"name": name, "payload": payload} if payload is not None else {"template_key": template}
    r = client.post(f"{API}/datasets", json=body)
    assert r.status_code == 201, r.text
    return r.json()["dataset"]["id"]


def start_run(client: TestClient, dataset_id: str | None = None, *, wait: float = 15, expect: int | None = None, **body: Any) -> dict[str, Any]:
    if dataset_id is not None:
        body["dataset_id"] = dataset_id
    r = client.post(f"{API}/runs?wait={wait}", json=body)
    if expect is not None:
        assert r.status_code == expect, r.text
    return r.json()


def wait_for(client: TestClient, run_id: str, timeout: float = 20) -> dict[str, Any]:
    deadline = time.monotonic() + timeout
    while True:
        detail = client.get(f"{API}/runs/{run_id}").json()
        if detail["status"] in TERMINAL or time.monotonic() > deadline:
            return detail
        time.sleep(0.05)


def wait_until_status(client: TestClient, run_id: str, status: str, timeout: float = 10) -> None:
    deadline = time.monotonic() + timeout
    while client.get(f"{API}/runs/{run_id}").json()["status"] != status:
        assert time.monotonic() < deadline, f"run never reached {status}"
        time.sleep(0.02)


class SlowEngine(OptimizationEngine):
    """Blocks its worker thread before solving, like a long CBC run."""

    def __init__(self, delay: float) -> None:
        super().__init__()
        self.delay = delay

    def run(self, payload: DatasetPayload, config: RunConfig) -> EngineOutput:
        time.sleep(self.delay)
        return super().run(payload, config)


class NotSolvedEngine(OptimizationEngine):
    """CBC hit the time limit without any solution."""

    def run(self, payload: DatasetPayload, config: RunConfig) -> EngineOutput:
        return EngineOutput(SolverOutcome.NOT_SOLVED, None, [], float(config.time_limit_s or 1), 10)


class CrashingEngine(OptimizationEngine):
    def run(self, payload: DatasetPayload, config: RunConfig) -> EngineOutput:
        raise RuntimeError("secret internal detail")

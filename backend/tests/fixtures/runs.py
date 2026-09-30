"""Solve a payload and wrap the result in a RunContext (what explain, insights and analytics read)."""

from __future__ import annotations

from app.analytics.context import RunContext
from app.domain.dataset import DatasetPayload
from app.domain.results import SensitivityReport
from app.domain.run_config import RunConfig
from app.optimization.engine import OptimizationEngine
from app.services.optimization import _with_duals

ENGINE = OptimizationEngine()


def solve_context(
    payload: DatasetPayload,
    config: RunConfig | None = None,
    *,
    sensitivity: SensitivityReport | None = None,
    duals: bool = True,
    run_id: str = "run-1",
) -> RunContext:
    """Same pipeline as a succeeded run: solve, attach fixed-LP duals, build the context."""
    config = config or RunConfig()
    output = ENGINE.run(payload, config)
    assert output.result is not None, f"no solution: {output.outcome}"
    result = output.result
    report = sensitivity
    if duals:
        result, dual_report = _with_duals(ENGINE, payload, config, result)
        report = sensitivity or dual_report
    return RunContext.build(run_id, payload, config, result, report)

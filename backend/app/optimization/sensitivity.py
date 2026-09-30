"""Marginal values (plan §15).

Method 1, `fixed_lp_duals`: fix the integer decisions (trips `n`, served-buyer `y`) at the values
of the stored plan, solve the remaining LP with CBC and read `constraint.pi`. Verified in phase 4
on hand-computed cases (e.g. a saturated 600 kg store returns pi = 2.0 - 0.1 = 1.9 per kg).
A dual is flagged unreliable when
  - the run is not proven optimal (`feasible` at the time limit),
  - the constraint contains an integer variable (trips or served-buyer): its dual is conditional
    on that integer choice (e.g. `demand_max` of an unserved MOQ buyer reports the full price),
  - it is degenerate: binding with a zero dual (another binding constraint took the value),
  - the objective is `weighted` (normalized, unit-less scores).

Method 2, `probe`: apply a real scenario change (+1 vehicle, +10 % demand...) and re-optimize with
integers. Exact for that change; this is what recommendations use.
"""

from __future__ import annotations

import logging
from collections.abc import Sequence
from dataclasses import dataclass
from typing import Any

from pulp import LpContinuous, LpVariable

from ..core.errors import AppError
from ..domain.dataset import DatasetPayload
from ..domain.enums import ObjectiveKind, SolverOutcome
from ..domain.results import DualValue, OptimizationResultModel, ProbeResult
from ..domain.run_config import RunConfig
from .builder import BuiltModel
from .engine import OptimizationEngine
from .postprocess import BINDING_ABS_TOL, BINDING_REL_TOL, ZERO

logger = logging.getLogger(__name__)

MAX_PROBES = 8
# A tighter gap would shrink the noise band but costs up to 30 s per probe on the templates.
PROBE_TIME_LIMIT_S = 10
PROBE_KPIS = ("realized_profit", "realized_revenue", "sold_kg", "lost_kg", "transport_cost", "storage_cost", "trips")


@dataclass(frozen=True)
class DualsOutput:
    available: bool
    duals: list[DualValue]  # binding or non-zero constraints only
    by_key: dict[str, DualValue]


def _integer_variables(built: BuiltModel) -> set[str]:
    return {v.name for v in [*built.vars.n.values(), *built.vars.y.values()]}


def fix_integers(built: BuiltModel, result: OptimizationResultModel) -> None:
    """Pin trips and served-buyer binaries to the stored plan and relax them to continuous."""
    trips = {(t.buyer_id, t.vehicle_type_id, t.day): t.trips for t in result.trips}
    served = {b.buyer_id for b in result.buyers if b.sold_kg > 0}
    pinned: list[tuple[LpVariable, float]] = [(var, float(trips.get(key, 0))) for key, var in built.vars.n.items()]
    pinned += [(var, 1.0 if buyer_id in served else 0.0) for buyer_id, var in built.vars.y.items()]
    for var, value in pinned:
        var.cat = LpContinuous
        var.lowBound = value
        var.upBound = value


def fixed_lp_duals(
    engine: OptimizationEngine,
    payload: DatasetPayload,
    config: RunConfig,
    result: OptimizationResultModel,
    *,
    time_limit_s: int = 30,
) -> DualsOutput:
    built = engine.build_model(payload, config)
    if built is None:
        return DualsOutput(False, [], {})
    integer_names = _integer_variables(built)
    fix_integers(built, result)
    raw = engine.runner.solve_sync(built, time_limit_s=time_limit_s, gap=0.0)
    if raw.outcome != SolverOutcome.OPTIMAL:
        logger.warning("Fixed-integer LP not optimal", extra={"outcome": str(raw.outcome)})
        return DualsOutput(False, [], {})

    names = built.instance.name_of
    duals: list[DualValue] = []
    by_key: dict[str, DualValue] = {}
    for registered in built.registry:
        if not registered.key.reportable or registered.sense == "==":
            continue
        c = registered.constraint
        pi = c.pi
        value = 0.0 if pi is None or abs(pi) < ZERO else float(pi)
        rhs = -c.constant
        lhs = (c.value() or 0.0) - c.constant
        slack = rhs - lhs if registered.sense == "<=" else lhs - rhs
        binding = abs(slack) <= BINDING_ABS_TOL + BINDING_REL_TOL * abs(rhs)

        reason: str | None = None
        if result.outcome != SolverOutcome.OPTIMAL:
            reason = "the run is not proven optimal"
        elif config.objective == ObjectiveKind.WEIGHTED:
            reason = "weighted objective: values are normalized scores, not money"
        elif pi is None:
            reason = "the solver returned no dual value"
        elif any(var.name in integer_names for var in c.keys()):
            reason = "depends on trip or served-buyer decisions held fixed (conditional on integer choices)"
        elif binding and value == 0.0:
            reason = "degenerate: binding with a zero dual (another binding constraint carries the value)"

        dual = DualValue(
            key=str(registered.key),
            label=registered.key.label(names),
            family=registered.key.family,
            value=round(value, 6),
            reliable=reason is None,
            reason=reason,
        )
        by_key[dual.key] = dual
        if binding or value != 0.0:
            duals.append(dual)
    return DualsOutput(True, duals, by_key)


@dataclass(frozen=True)
class ProbeCandidate:
    label: str
    change: dict[str, Any]  # ScenarioChange shape, stored as-is in the report
    payload: DatasetPayload  # base payload with the change applied
    constraint_key: str | None = None


def probe_config(config: RunConfig) -> RunConfig:
    """Same gap as the run (so the stored plan is the reference), shorter time limit per probe."""
    return config.model_copy(update={"time_limit_s": min(config.time_limit_s or PROBE_TIME_LIMIT_S, PROBE_TIME_LIMIT_S)})


def probe(
    engine: OptimizationEngine,
    config: RunConfig,
    baseline: OptimizationResultModel,
    candidates: Sequence[ProbeCandidate],
) -> list[ProbeResult]:
    """Re-optimize each candidate (at most MAX_PROBES) with the run's gap and compare with the run.
    Both plans are only proven within that gap of their optimum, so a delta smaller than
    gap x |objective| is reported with `significant = False` rather than as a gain or loss."""
    tight = probe_config(config)
    gap = baseline.gap_requested
    ref = baseline.kpis
    results: list[ProbeResult] = []
    for candidate in candidates[:MAX_PROBES]:
        common = {"constraint_key": candidate.constraint_key, "label": candidate.label, "change": candidate.change}
        try:
            output = engine.run(candidate.payload, tight)
        except AppError as e:  # the change made the dataset or config unusable
            logger.info("Probe rejected", extra={"label": candidate.label, "code": e.code})
            results.append(ProbeResult(**common, outcome=SolverOutcome.ERROR, objective_value=None, delta_objective=None))
            continue
        if output.result is None:
            results.append(ProbeResult(**common, outcome=output.outcome, objective_value=None, delta_objective=None))
            continue
        new = output.result.kpis
        delta = round(new.objective_value - ref.objective_value, 4)
        noise = gap * max(abs(new.objective_value), abs(ref.objective_value))
        results.append(
            ProbeResult(
                **common,
                outcome=output.outcome,
                objective_value=new.objective_value,
                delta_objective=delta,
                significant=output.outcome == SolverOutcome.OPTIMAL and abs(delta) > noise,
                delta_kpis={k: round(float(getattr(new, k)) - float(getattr(ref, k)), 4) for k in PROBE_KPIS},
            )
        )
    return results

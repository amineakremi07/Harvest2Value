"""Infeasibility diagnostics by elastic relaxation (plan §15).

Physical constraints (lot split, stock balance, shelf life) are never relaxed. The requirement
constraints (contracted minimums, service level, profit floor) get an overflow variable >= 0 and
the solver minimizes their sum: the non-zero overflows are the conflicts, with the missing amount.
If relaxing requirements is not enough, capacities (storage, demand, fleet) are relaxed too.
Constraints that are impossible without any decision (e.g. a contracted minimum for a buyer that
no vehicle can reach) are reported directly.
"""

from __future__ import annotations

from pulp import LpMinimize, LpVariable, lpSum

from ..domain.dataset import DatasetPayload
from ..domain.enums import ObjectiveKind
from ..domain.results import ConflictInfo, Diagnostics
from ..domain.run_config import RunConfig
from .builder import BuiltModel, ModelBuilder
from .instance import build_instance
from .keys import ConstraintKey
from .runner import SolverRunner

REQUIREMENTS = ("demand_min", "service_level", "min_profit")
CAPACITIES = ("storage_capacity", "demand_max", "demand_day", "fleet_time", "fleet_trips", "trip_capacity")
# Reported as "limits reached" next to the conflicts (trip_capacity is a symptom, not a cause).
LIMITS = ("storage_capacity", "demand_max", "demand_day", "fleet_time", "fleet_trips")
STRUCTURAL = ("cold_chain_vehicle", "trip_duration")  # only when they concern a conflicting buyer
UNITS = {
    "demand_min": "kg",
    "service_level": "kg",
    "min_profit": "currency",
    "storage_capacity": "kg",
    "demand_max": "kg",
    "demand_day": "kg",
    "fleet_time": "h",
    "fleet_trips": "trips",
    "trip_capacity": "kg",
    "moq_min": "kg",
}
ZERO = 1e-6


def _build(payload: DatasetPayload, config: RunConfig) -> BuiltModel:
    # Mode constraints (service level, profit floor) exist only for their own objective; the
    # weighted mode has none, so any single objective will do (it is replaced below).
    kind = ObjectiveKind.PROFIT if config.objective == ObjectiveKind.WEIGHTED else config.objective
    return ModelBuilder().build(build_instance(payload, config), config, objective=kind)


def _suggestion(key: ConstraintKey, amount: float, name_of: dict[str, str]) -> str:
    entity = name_of.get(key.entity[0], key.entity[0]) if key.entity else ""
    day = f" on day {key.day}" if key.day is not None else ""
    return {
        "demand_min": f"Lower the contracted minimum of {entity} by {amount:,.0f} kg, or supply more.",
        "service_level": f"Lower service_level_min: {amount:,.0f} kg of the required share cannot be sold.",
        "min_profit": f"Lower min_profit by {amount:,.2f}: that profit is not reachable.",
        "storage_capacity": f"Add {amount:,.0f} kg of capacity to {entity}{day}.",
        "demand_max": f"{entity} would need {amount:,.0f} kg more demand.",
        "demand_day": f"{entity} would need to accept {amount:,.0f} kg more{day}.",
        "fleet_time": f"The {entity} fleet needs {amount:,.1f} more driving hours{day}.",
        "fleet_trips": f"The {entity} fleet needs {amount:,.0f} more trips{day}.",
        "trip_capacity": f"Deliveries to {entity}{day} need {amount:,.0f} kg more truck capacity.",
    }.get(key.family, f"Relax '{key}' by {amount:,.2f}.")


def _solve_elastic(built: BuiltModel, families: tuple[str, ...], runner: SolverRunner, time_limit_s: int) -> dict[str, float] | None:
    """Returns {constraint name: overflow} or None if even the relaxed model is infeasible."""
    overflow: dict[str, LpVariable] = {}
    for registered in built.registry:
        if registered.key.family not in families:
            continue
        s = LpVariable(f"elastic_{registered.name}", lowBound=0)
        # `lhs <= rhs` becomes `lhs - s <= rhs`; `lhs >= rhs` becomes `lhs + s >= rhs`.
        registered.constraint.addterm(s, -1 if registered.sense == "<=" else 1)
        overflow[registered.name] = s
    built.problem.sense = LpMinimize
    built.problem.setObjective(lpSum(overflow.values()))
    raw = runner.solve_sync(built, time_limit_s=time_limit_s, gap=0.0)
    if not raw.outcome.has_solution:
        return None
    return {name: float(var.varValue or 0.0) for name, var in overflow.items()}


def elastic_infeasibility(
    payload: DatasetPayload, config: RunConfig, *, runner: SolverRunner | None = None, time_limit_s: int = 30
) -> Diagnostics:
    runner = runner or SolverRunner()
    probe_model = _build(payload, config)
    inst = probe_model.instance
    names = {b.id: b.name for b in inst.buyers} | {f.id: f.name for f in inst.facilities} | {k.id: k.name for k in inst.vehicles}

    conflicts: list[ConflictInfo] = []
    suggestions: list[str] = []
    for key, amount in probe_model.registry.trivial_violations.items():
        conflicts.append(
            ConflictInfo(
                key=str(key), family=key.family, label=key.label(inst.name_of), relaxation_needed=round(amount, 4), unit=UNITS.get(key.family, "")
            )
        )
        suggestions.append(
            f"{key.label(inst.name_of)} can never be met ({amount:,.0f} {UNITS.get(key.family, '')} missing): "
            "no delivery is possible for it (cold chain, trip length or delivery window)."
        )

    for families in (REQUIREMENTS, REQUIREMENTS + CAPACITIES):
        built = _build(payload, config)
        built.registry.trivially_infeasible.clear()  # reported above; let the rest of the model solve
        solution = _solve_elastic(built, families, runner, time_limit_s)
        if solution is None:
            continue
        for name, amount in solution.items():
            if amount <= ZERO:
                continue
            key = built.registry.items[name].key
            conflicts.append(
                ConflictInfo(
                    key=str(key),
                    family=key.family,
                    label=key.label(inst.name_of),
                    relaxation_needed=round(amount, 4),
                    unit=UNITS.get(key.family, ""),
                )
            )
            suggestions.append(_suggestion(key, amount, names))
        if families == REQUIREMENTS:
            involved = {c.key.split("|")[1].split(",")[0] for c in conflicts}
            limits = [
                r.key.label(inst.name_of)
                for r in built.registry
                if r.sense != "=="
                and abs(r.constraint.slack or 0.0) <= 1e-6
                and (
                    r.key.family in LIMITS
                    or (r.key.family in STRUCTURAL and r.key.entity and r.key.entity[0] in involved)
                )
            ]
            if limits and conflicts:
                shown = ", ".join(limits[:5]) + (f" and {len(limits) - 5} more" if len(limits) > 5 else "")
                suggestions.append(f"Capacity limits reached in the closest feasible plan: {shown}.")
        return Diagnostics(conflicts=conflicts, suggestions=suggestions, method="elastic")

    if not suggestions:
        suggestions.append("No relaxation of requirements or capacities makes the model feasible; check the dataset.")
    return Diagnostics(conflicts=conflicts, suggestions=suggestions, method="elastic" if conflicts else "none")

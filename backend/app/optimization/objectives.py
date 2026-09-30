"""Objectives (plan §6.3): profit, revenue, waste, cost, weighted.

Single-criterion modes add a tiny tie-breaker (EPS) so equal-value plans are resolved
sensibly (e.g. revenue mode does not make useless trips). The weighted mode minimizes the
weighted sum of normalized deviations from each criterion's ideal value:
  deviation = (ideal - f) / (ideal - nadir) for a maximized criterion, and
              (f - ideal) / (nadir - ideal) for a minimized one,
where ideal/nadir come from a payoff table (one single-criterion solve per weighted criterion).
"""

from __future__ import annotations

from collections.abc import Callable, Mapping
from dataclasses import dataclass
from typing import TYPE_CHECKING, Literal

from pulp import LpAffineExpression, LpMaximize, LpMinimize, LpProblem, lpSum

from ..domain.enums import ObjectiveKind
from ..domain.run_config import RunConfig
from .keys import ConstraintKey, ConstraintRegistry

if TYPE_CHECKING:
    from .builder import Components
    from .instance import ProblemInstance

EPS = 1e-6

Criterion = Literal["profit", "waste", "cost"]


@dataclass(frozen=True)
class CriterionSpec:
    sense: Literal["max", "min"]
    expression: Callable[[Components], LpAffineExpression]
    single_objective: ObjectiveKind


CRITERIA: dict[Criterion, CriterionSpec] = {
    "profit": CriterionSpec("max", lambda c: c.profit + c.salvage, ObjectiveKind.PROFIT),
    "waste": CriterionSpec("min", lambda c: c.waste_kg, ObjectiveKind.WASTE),
    "cost": CriterionSpec("min", lambda c: c.cost, ObjectiveKind.COST),
}


@dataclass(frozen=True)
class CriterionBounds:
    ideal: float
    nadir: float


def weighted_criteria(config: RunConfig) -> dict[Criterion, float]:
    assert config.weights is not None
    weights = {"profit": config.weights.profit, "waste": config.weights.waste, "cost": config.weights.cost}
    return {c: w for c, w in weights.items() if w > 0}  # type: ignore[misc]


def ideal_points(payoff: Mapping[Criterion, Mapping[Criterion, float]]) -> dict[Criterion, CriterionBounds]:
    """payoff[solved_for][criterion] = value of `criterion` at the optimum of `solved_for`."""
    bounds: dict[Criterion, CriterionBounds] = {}
    for criterion in payoff:
        values = [row[criterion] for row in payoff.values()]
        if CRITERIA[criterion].sense == "max":
            bounds[criterion] = CriterionBounds(ideal=max(values), nadir=min(values))
        else:
            bounds[criterion] = CriterionBounds(ideal=min(values), nadir=max(values))
    return bounds


def _weighted_expression(
    components: Components, weights: Mapping[Criterion, float], bounds: Mapping[Criterion, CriterionBounds]
) -> LpAffineExpression:
    terms = []
    for criterion, weight in weights.items():
        b = bounds[criterion]
        spread = b.ideal - b.nadir
        if abs(spread) < 1e-9:
            continue  # every plan scores the same on this criterion
        f = CRITERIA[criterion].expression(components)
        deviation = (b.ideal - f) * (1.0 / spread) if CRITERIA[criterion].sense == "max" else (f - b.ideal) * (1.0 / -spread)
        terms.append(weight * deviation)
    return lpSum(terms)


class ObjectiveRegistry:
    """kind -> (sense, expression builder)."""

    _builders: dict[ObjectiveKind, tuple[int, Callable[[Components], LpAffineExpression]]] = {
        ObjectiveKind.PROFIT: (LpMaximize, lambda c: c.profit + c.salvage),
        ObjectiveKind.REVENUE: (LpMaximize, lambda c: c.revenue - EPS * c.cost),
        ObjectiveKind.WASTE: (LpMinimize, lambda c: c.waste_kg - EPS * c.profit),
        ObjectiveKind.COST: (LpMinimize, lambda c: c.cost - EPS * c.revenue),
    }

    @classmethod
    def build(
        cls,
        kind: ObjectiveKind,
        components: Components,
        config: RunConfig,
        bounds: Mapping[Criterion, CriterionBounds] | None = None,
    ) -> tuple[int, LpAffineExpression]:
        if kind == ObjectiveKind.WEIGHTED:
            if bounds is None:
                raise ValueError("weighted objective needs ideal/nadir bounds (see ideal_points)")
            # Tie-breaker towards profit so equally scored plans do not waste money.
            return LpMinimize, _weighted_expression(components, weighted_criteria(config), bounds) - EPS * components.profit
        return cls._builders[kind][0], cls._builders[kind][1](components)


def build_objective(
    kind: ObjectiveKind,
    components: Components,
    config: RunConfig,
    bounds: Mapping[Criterion, CriterionBounds] | None = None,
) -> tuple[int, LpAffineExpression]:
    return ObjectiveRegistry.build(kind, components, config, bounds)


def apply_objective(
    problem: LpProblem,
    kind: ObjectiveKind,
    components: Components,
    config: RunConfig,
    inst: ProblemInstance,
    registry: ConstraintRegistry,
    bounds: Mapping[Criterion, CriterionBounds] | None = None,
) -> None:
    sense, expression = build_objective(kind, components, config, bounds)
    problem.sense = sense
    problem.setObjective(expression)

    # Mode constraints only apply when that mode is the one being optimized.
    if kind == ObjectiveKind.COST and config.service_level_min is not None:
        registry.add(
            problem,
            ConstraintKey("service_level"),
            components.sold_kg >= config.service_level_min * inst.harvest_kg,
        )
    if kind == ObjectiveKind.WASTE and config.min_profit is not None:
        registry.add(problem, ConstraintKey("min_profit"), components.profit >= config.min_profit)

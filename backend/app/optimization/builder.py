"""ModelBuilder: variables + constraint modules + economic components + objective."""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass

from pulp import LpAffineExpression, LpMaximize, LpProblem, lpSum

from ..domain.enums import ObjectiveKind
from ..domain.run_config import RunConfig
from .constraints import ConstraintModule, balance, cold_chain, demand, shelf_life, storage, transport
from .instance import ProblemInstance
from .keys import ConstraintRegistry
from .objectives import Criterion, CriterionBounds, apply_objective
from .variables import VarSet, create_variables

DEFAULT_MODULES: tuple[ConstraintModule, ...] = (
    balance.add,
    shelf_life.add,
    storage.add,
    demand.add,
    transport.add,
    cold_chain.add,
)


@dataclass(frozen=True)
class Components:
    """Linear expressions of the economic quantities (plan §10), shared by objectives and KPIs."""

    revenue: LpAffineExpression
    transport: LpAffineExpression
    storage: LpAffineExpression
    disposal: LpAffineExpression
    waste_kg: LpAffineExpression
    ending_kg: LpAffineExpression
    salvage: LpAffineExpression
    sold_kg: LpAffineExpression

    @property
    def cost(self) -> LpAffineExpression:
        return self.transport + self.storage + self.disposal

    @property
    def profit(self) -> LpAffineExpression:
        """Realized profit: revenue - transport - storage - disposal (no inventory value)."""
        return self.revenue - self.cost


@dataclass
class BuiltModel:
    instance: ProblemInstance
    config: RunConfig
    objective: ObjectiveKind
    problem: LpProblem
    vars: VarSet
    registry: ConstraintRegistry
    components: Components


def build_components(inst: ProblemInstance, v: VarSet) -> Components:
    facilities = {f.id: f for f in inst.facilities}
    lots = {lot.id: lot for lot in inst.lots}
    legacy = {b.id: b.legacy_cost_per_kg for b in inst.buyers}

    revenue = lpSum(inst.price[(b, l, t)] * x for (b, l, _f, t), x in v.x.items())
    transport = lpSum(inst.trip_cost[(b, k)] * n for (b, k, _t), n in v.n.items()) + lpSum(
        legacy[b] * x for (b, _l, _f, _t), x in v.x.items() if legacy[b]
    )
    storage_cost = lpSum(facilities[f].cost_per_kg_day * stock for (_l, f, _t), stock in v.inv.items())
    daily_loss = lpSum(
        facilities[f].loss_rate * v.inv[(l, f, t - 1)]
        for (l, f, t) in v.inv
        if t > lots[l].day and facilities[f].loss_rate > 0
    )
    waste_kg = lpSum(v.unsold.values()) + daily_loss + lpSum(v.expired.values())
    ending_kg = lpSum(
        stock for (l, f, t), stock in v.inv.items() if not inst.expires[(l, f)] and t == inst.horizon - 1
    )
    return Components(
        revenue=revenue,
        transport=transport,
        storage=storage_cost,
        disposal=inst.disposal_cost_per_kg * waste_kg,
        waste_kg=waste_kg,
        ending_kg=ending_kg,
        salvage=inst.salvage_per_kg * ending_kg,
        sold_kg=lpSum(v.x.values()),
    )


class ModelBuilder:
    def __init__(self, modules: Sequence[ConstraintModule] = DEFAULT_MODULES) -> None:
        self.modules = tuple(modules)

    def build(
        self,
        inst: ProblemInstance,
        config: RunConfig,
        *,
        objective: ObjectiveKind | None = None,
        bounds: dict[Criterion, CriterionBounds] | None = None,
    ) -> BuiltModel:
        """`objective` overrides config.objective (used for the weighted mode's payoff table)."""
        kind = objective or config.objective
        problem = LpProblem("harvest2value", LpMaximize)
        v = create_variables(inst)
        registry = ConstraintRegistry()
        for add in self.modules:
            add(problem, inst, v, registry)
        components = build_components(inst, v)
        apply_objective(problem, kind, components, config, inst, registry, bounds)
        return BuiltModel(inst, config, kind, problem, v, registry, components)

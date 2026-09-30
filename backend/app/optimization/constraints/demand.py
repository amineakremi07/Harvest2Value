"""Buyer demand: horizon maximum, daily maximum, contracted minimum and minimum order.

With a minimum order (MOQ), a binary `y` says whether the buyer is served:
MOQ x y <= sold <= max_demand x y.
"""

from __future__ import annotations

from pulp import LpProblem, lpSum

from ..instance import ProblemInstance
from ..keys import ConstraintKey, ConstraintRegistry
from ..variables import VarSet


def add(problem: LpProblem, inst: ProblemInstance, v: VarSet, registry: ConstraintRegistry) -> None:
    for b in inst.buyers:
        sold = lpSum(v.sales_by_buyer.get(b.id, []))
        served = v.y.get(b.id)

        if served is not None:
            registry.add(problem, ConstraintKey("demand_max", (b.id,)), sold <= b.max_demand * served)
            registry.add(problem, ConstraintKey("moq_min", (b.id,)), sold >= b.min_order * served)
        else:
            registry.add(problem, ConstraintKey("demand_max", (b.id,)), sold <= b.max_demand)

        if b.max_per_day is not None:
            for t in v.buyer_days(b.id):
                registry.add(
                    problem,
                    ConstraintKey("demand_day", (b.id,), t),
                    lpSum(v.sales_by_buyer_day[(b.id, t)]) <= b.max_per_day,
                )

        if b.min_contract > 0:
            registry.add(problem, ConstraintKey("demand_min", (b.id,)), sold >= b.min_contract)

"""Storage capacity: end-of-day stock of all lots in a facility <= its capacity."""

from __future__ import annotations

from collections import defaultdict

from pulp import LpProblem, LpVariable, lpSum

from ..instance import ProblemInstance
from ..keys import ConstraintKey, ConstraintRegistry
from ..variables import VarSet


def add(problem: LpProblem, inst: ProblemInstance, v: VarSet, registry: ConstraintRegistry) -> None:
    stock: dict[tuple[str, int], list[LpVariable]] = defaultdict(list)
    for (_lot, facility_id, t), var in v.inv.items():
        stock[(facility_id, t)].append(var)
    capacity = {f.id: f.capacity for f in inst.facilities}
    for (facility_id, t), variables in sorted(stock.items()):
        registry.add(
            problem,
            ConstraintKey("storage_capacity", (facility_id,), t),
            lpSum(variables) <= capacity[facility_id],
        )

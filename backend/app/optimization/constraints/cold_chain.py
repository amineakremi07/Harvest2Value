"""Cold chain: a cold-chain crop or buyer only travels in refrigerated vehicles, and a
cold-chain crop cannot be placed in ambient storage. Written as explicit constraints
(rather than missing variables) so the explanation can say *why* a truck was not used."""

from __future__ import annotations

from collections import defaultdict

from pulp import LpProblem, LpVariable, lpSum

from ..instance import ProblemInstance
from ..keys import ConstraintKey, ConstraintRegistry
from ..variables import VarSet


def add(problem: LpProblem, inst: ProblemInstance, v: VarSet, registry: ConstraintRegistry) -> None:
    blocked: dict[tuple[str, str], list[LpVariable]] = defaultdict(list)
    for (buyer_id, vehicle_id, _t), n in v.n.items():
        if not inst.allow[(buyer_id, vehicle_id)]:
            blocked[(buyer_id, vehicle_id)].append(n)
    for (buyer_id, vehicle_id), trips in sorted(blocked.items()):
        registry.add(problem, ConstraintKey("cold_chain_vehicle", (buyer_id, vehicle_id)), lpSum(trips) <= 0)

    for f in inst.facilities:
        if not f.usable:
            placed = [v.z[(lot.id, f.id)] for lot in inst.lots]
            registry.add(problem, ConstraintKey("cold_chain_storage", (f.id,)), lpSum(placed) <= 0)

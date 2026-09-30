"""Decision variables (plan §10), created only where they make sense, with lookup indexes."""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass, field
from itertools import count

from pulp import LpBinary, LpContinuous, LpInteger, LpVariable

from .instance import DIRECT, ProblemInstance, trips_upper_bound


@dataclass
class VarSet:
    z: dict[tuple[str, str], LpVariable] = field(default_factory=dict)  # (lot, facility|DIRECT) placed kg
    x: dict[tuple[str, str, str, int], LpVariable] = field(default_factory=dict)  # (buyer, lot, facility|DIRECT, day) sold kg
    inv: dict[tuple[str, str, int], LpVariable] = field(default_factory=dict)  # (lot, facility, day) end-of-day stock
    expired: dict[tuple[str, str], LpVariable] = field(default_factory=dict)  # (lot, facility) kg expired
    unsold: dict[str, LpVariable] = field(default_factory=dict)  # lot -> kg not sold on the harvest day (direct)
    n: dict[tuple[str, str, int], LpVariable] = field(default_factory=dict)  # (buyer, vehicle, day) trips
    y: dict[str, LpVariable] = field(default_factory=dict)  # buyer served (only with a minimum order)

    # indexes
    sales_by_buyer: dict[str, list[LpVariable]] = field(default_factory=lambda: defaultdict(list))
    sales_by_buyer_day: dict[tuple[str, int], list[LpVariable]] = field(default_factory=lambda: defaultdict(list))
    sales_by_stock_day: dict[tuple[str, str, int], list[LpVariable]] = field(default_factory=lambda: defaultdict(list))
    trips_by_buyer_day: dict[tuple[str, int], list[tuple[str, LpVariable]]] = field(default_factory=lambda: defaultdict(list))

    def buyer_days(self, buyer_id: str) -> list[int]:
        return sorted({t for (b, t) in self.sales_by_buyer_day if b == buyer_id})


def create_variables(inst: ProblemInstance) -> VarSet:
    ids = count()

    def var(prefix: str, low: float = 0, up: float | None = None, cat: str = LpContinuous) -> LpVariable:
        return LpVariable(f"{prefix}{next(ids)}", lowBound=low, upBound=up, cat=cat)

    v = VarSet()
    for lot in inst.lots:
        v.z[(lot.id, DIRECT)] = var("z")
        v.unsold[lot.id] = var("u")
        for f in inst.facilities:
            v.z[(lot.id, f.id)] = var("z")
            for t in range(lot.day, inst.last_day[(lot.id, f.id)] + 1):
                v.inv[(lot.id, f.id, t)] = var("i")
            if inst.expires[(lot.id, f.id)]:
                v.expired[(lot.id, f.id)] = var("e")

        for b in inst.buyers:
            for facility_id in [DIRECT, *(f.id for f in inst.facilities)]:
                for t in inst.sale_days(b, lot, facility_id):
                    x = var("x")
                    v.x[(b.id, lot.id, facility_id, t)] = x
                    v.sales_by_buyer[b.id].append(x)
                    v.sales_by_buyer_day[(b.id, t)].append(x)
                    v.sales_by_stock_day[(lot.id, facility_id, t)].append(x)

    for b in inst.buyers:
        days = v.buyer_days(b.id)
        for vehicle in inst.vehicles:
            bound = trips_upper_bound(inst, b, vehicle)
            for t in days:
                n = var("n", up=bound, cat=LpInteger)
                v.n[(b.id, vehicle.id, t)] = n
                v.trips_by_buyer_day[(b.id, t)].append((vehicle.id, n))
        if b.min_order > 0 and days:
            v.y[b.id] = var("y", cat=LpBinary)
    return v

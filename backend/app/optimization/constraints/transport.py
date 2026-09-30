"""Transport: direct round trips producer -> buyer, one buyer per trip (no multi-stop routes).

- trip_capacity: kg delivered to a buyer on a day <= sum of capacities of the trips made;
- fleet_time:    round-trip hours of a vehicle type on a day <= count x hours per day;
- fleet_trips:   trips of a vehicle type on a day <= count x max trips per day;
- trip_duration: a round trip longer than a vehicle's working day is impossible.
"""

from __future__ import annotations

from collections import defaultdict

from pulp import LpAffineExpression, LpProblem, lpSum

from ..instance import ProblemInstance
from ..keys import ConstraintKey, ConstraintRegistry
from ..variables import VarSet


def add(problem: LpProblem, inst: ProblemInstance, v: VarSet, registry: ConstraintRegistry) -> None:
    capacity = {k.id: k.capacity for k in inst.vehicles}
    buyers = {b.id: b for b in inst.buyers}

    for (buyer_id, t), sales in sorted(v.sales_by_buyer_day.items()):
        trips = v.trips_by_buyer_day.get((buyer_id, t), [])
        # Useful capacity of one trip: never more than the buyer can take that day. Same integer
        # solutions, much tighter LP relaxation (the fixed trip cost is no longer diluted).
        b = buyers[buyer_id]
        daily_limit = min(b.max_per_day or b.max_demand, b.max_demand, inst.harvest_kg)
        registry.add(
            problem,
            ConstraintKey("trip_capacity", (buyer_id,), t),
            lpSum(sales) <= lpSum(min(capacity[k], daily_limit) * n for k, n in trips),
        )

    hours_used: dict[tuple[str, int], list[LpAffineExpression]] = defaultdict(list)
    trips_made: dict[tuple[str, int], list[LpAffineExpression]] = defaultdict(list)
    too_long: dict[tuple[str, str], list[LpAffineExpression]] = defaultdict(list)
    for (buyer_id, vehicle_id, t), n in v.n.items():
        vehicle = next(k for k in inst.vehicles if k.id == vehicle_id)
        hours = inst.trip_hours[(buyer_id, vehicle_id)]
        trips_made[(vehicle_id, t)].append(n)
        if vehicle.hours_per_day is None:
            continue
        if hours > vehicle.hours_per_day:
            too_long[(buyer_id, vehicle_id)].append(n)
        else:
            hours_used[(vehicle_id, t)].append(hours * n)

    for vehicle in inst.vehicles:
        for t in range(inst.horizon):
            if vehicle.hours_per_day is not None and hours_used.get((vehicle.id, t)):
                registry.add(
                    problem,
                    ConstraintKey("fleet_time", (vehicle.id,), t),
                    lpSum(hours_used[(vehicle.id, t)]) <= vehicle.count * vehicle.hours_per_day,
                )
            if vehicle.max_trips_per_day is not None and trips_made.get((vehicle.id, t)):
                registry.add(
                    problem,
                    ConstraintKey("fleet_trips", (vehicle.id,), t),
                    lpSum(trips_made[(vehicle.id, t)]) <= vehicle.count * vehicle.max_trips_per_day,
                )

    for (buyer_id, vehicle_id), trips in sorted(too_long.items()):
        registry.add(problem, ConstraintKey("trip_duration", (buyer_id, vehicle_id)), lpSum(trips) <= 0)

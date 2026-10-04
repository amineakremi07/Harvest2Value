"""Turn solver values into an OptimizationResultModel: tables, KPIs, constraint report.

Values below 1e-6 are treated as 0 and reported kg are rounded to 0.01 *after* extraction;
KPIs are computed from the raw values (by analytics.kpis). Invariants are checked on the raw
values and a violation is an engine bug, never a result shown to the user.
"""

from __future__ import annotations

from collections import defaultdict

from ..analytics.kpis import KpiInputs, compute_kpis
from ..core.errors import AppError
from ..domain.enums import SolverOutcome
from ..domain.results import (
    AllocationRow,
    BuyerSummary,
    ConstraintInfo,
    InventoryRow,
    OptimizationResultModel,
    TripRow,
    WasteRow,
)
from ..domain.run_config import DEFAULT_GAP
from .builder import BuiltModel
from .instance import DIRECT
from .runner import RawSolution

ZERO = 1e-6
BINDING_ABS_TOL = 1e-4
BINDING_REL_TOL = 1e-6


class EngineInvariantError(AppError):
    code = "ENGINE_INVARIANT"
    status = 500
    default_message = "The optimization result failed an internal consistency check."


def _val(var: object) -> float:
    raw = getattr(var, "varValue", None) or 0.0
    return 0.0 if abs(raw) < ZERO else float(raw)


def _kg(value: float) -> float:
    return round(value, 2) + 0.0


def outcome_label(outcome: SolverOutcome, gap: float) -> str:
    if outcome == SolverOutcome.OPTIMAL:
        return f"Optimal within {gap:.1%} of the best possible plan" if gap > 0 else "Optimal"
    if outcome == SolverOutcome.FEASIBLE:
        return "Best plan found within the time limit (not proven optimal)"
    return {
        SolverOutcome.INFEASIBLE: "No plan satisfies all constraints",
        SolverOutcome.UNBOUNDED: "The model is unbounded (data error)",
        SolverOutcome.NOT_SOLVED: "No plan found within the time limit",
    }.get(outcome, "The solver failed")


def extract(built: BuiltModel, raw: RawSolution) -> OptimizationResultModel:
    if not raw.outcome.has_solution:
        raise ValueError(f"No solution to extract (outcome {raw.outcome})")
    gap = DEFAULT_GAP if built.config.gap is None else built.config.gap
    inst, v = built.instance, built.vars
    facilities = {f.id: f for f in inst.facilities}
    vehicles = {k.id: k for k in inst.vehicles}
    lots = {lot.id: lot for lot in inst.lots}

    # ---- sales ----
    allocations: list[AllocationRow] = []
    revenue = 0.0
    sold_by_buyer: dict[str, float] = defaultdict(float)
    revenue_by_buyer: dict[str, float] = defaultdict(float)
    sold_by_lot: dict[str, float] = defaultdict(float)
    shipped: dict[tuple[str, int], float] = defaultdict(float)
    for (b, l, f, t), var in v.x.items():
        kg = _val(var)
        if kg <= 0:
            continue
        price = inst.price[(b, l, t)]
        revenue += price * kg
        sold_by_buyer[b] += kg
        revenue_by_buyer[b] += price * kg
        sold_by_lot[l] += kg
        shipped[(b, t)] += kg
        allocations.append(
            AllocationRow(
                buyer_id=b, lot_id=l, facility_id=None if f == DIRECT else f, day=t, kg=_kg(kg), unit_price=round(price, 4), revenue=round(price * kg, 2)
            )
        )

    # ---- trips ----
    trips: list[TripRow] = []
    transport_by_buyer: dict[str, float] = defaultdict(float)
    capacity_shipped: dict[tuple[str, int], float] = defaultdict(float)
    trip_count = 0
    trip_capacity = 0.0
    hours_used_limited = 0.0
    for (b, k, t), var in v.n.items():
        n = round(_val(var))
        if n <= 0:
            continue
        cost = inst.trip_cost[(b, k)] * n
        hours = inst.trip_hours[(b, k)] * n
        trip_count += n
        trip_capacity += vehicles[k].capacity * n
        capacity_shipped[(b, t)] += vehicles[k].capacity * n
        transport_by_buyer[b] += cost
        if vehicles[k].hours_per_day is not None:
            hours_used_limited += hours
        trips.append(
            TripRow(day=t, buyer_id=b, vehicle_type_id=k, trips=n, capacity_kg=vehicles[k].capacity * n, cost=round(cost, 2), hours=round(hours, 2))
        )
    for buyer in inst.buyers:
        transport_by_buyer[buyer.id] += buyer.legacy_cost_per_kg * sold_by_buyer.get(buyer.id, 0.0)
    transport = sum(transport_by_buyer.values())

    # ---- storage ----
    inventory: list[InventoryRow] = []
    storage_cost = 0.0
    stock_by_facility_day: dict[tuple[str, int], float] = defaultdict(float)
    inventory_kg_days = 0.0
    for (l, f, t), var in v.inv.items():
        kg = _val(var)
        stock_by_facility_day[(f, t)] += kg
        if kg <= 0:
            continue
        cost = facilities[f].cost_per_kg_day * kg
        storage_cost += cost
        inventory_kg_days += kg
        inventory.append(InventoryRow(day=t, facility_id=f, lot_id=l, kg_end=_kg(kg), cost=round(cost, 2)))
    stored_by_lot = {lot.id: sum(_val(v.z[(lot.id, f.id)]) for f in inst.facilities) for lot in inst.lots}

    # ---- waste and ending inventory ----
    waste: list[WasteRow] = []
    lost_by_lot: dict[str, float] = defaultdict(float)

    def lose(day: int, lot_id: str, facility_id: str | None, kind: str, kg: float) -> None:
        if kg <= ZERO:
            return
        lost_by_lot[lot_id] += kg
        waste.append(
            WasteRow(day=day, lot_id=lot_id, facility_id=facility_id, kind=kind, kg=_kg(kg), value_lost=round(kg * inst.reference_price, 2))
        )

    for lot in inst.lots:
        lose(lot.day, lot.id, None, "unsold_direct", _val(v.unsold[lot.id]))
    for l, f, t in v.inv:
        if t > lots[l].day and facilities[f].loss_rate > 0:
            lose(t, l, f, "daily_loss", facilities[f].loss_rate * _val(v.inv[(l, f, t - 1)]))
    for (l, f), var in v.expired.items():
        lose(inst.last_day[(l, f)], l, f, "expired", _val(var))

    ending_by_lot: dict[str, float] = defaultdict(float)
    for (l, f, t), var in v.inv.items():
        if not inst.expires[(l, f)] and t == inst.horizon - 1:
            ending_by_lot[l] += _val(var)

    lost_kg = sum(lost_by_lot.values())
    ending_kg = sum(ending_by_lot.values())
    sold_kg = sum(sold_by_buyer.values())
    disposal = inst.disposal_cost_per_kg * lost_kg

    _check_invariants(built, sold_by_lot, lost_by_lot, ending_by_lot, sold_by_buyer, stock_by_facility_day, shipped, capacity_shipped)

    kpis = compute_kpis(
        KpiInputs(
            harvest_kg=inst.harvest_kg,
            sold_kg=sold_kg,
            realized_revenue=revenue,
            transport_cost=transport,
            storage_cost=storage_cost,
            disposal_cost=disposal,
            ending_inventory_kg=ending_kg,
            salvage_value_per_kg=inst.salvage_per_kg,
            lost_kg=lost_kg,
            reference_price_per_kg=inst.reference_price,
            stored_kg=sum(stored_by_lot.values()),
            inventory_kg_days=inventory_kg_days,
            trips=trip_count,
            trip_capacity_kg=trip_capacity,
            fleet_hours_used=hours_used_limited,
            fleet_hours_available=_fleet_hours_available(built),
            storage_occupancy=[
                (stock_by_facility_day.get((f.id, t), 0.0), f.capacity)
                for f in inst.facilities
                if f.usable
                for t in range(inst.horizon)
            ],
            buyer_sold=dict(sold_by_buyer),
            buyer_net_revenue={b: revenue_by_buyer[b] - transport_by_buyer[b] for b in sold_by_buyer},
            buyer_max_demand={b.id: b.max_demand for b in inst.buyers},
            objective_value=raw.objective_value or 0.0,
        )
    )

    buyers = [
        BuyerSummary(
            buyer_id=b.id,
            buyer_name=b.name,
            sold_kg=_kg(sold_by_buyer.get(b.id, 0.0)),
            revenue=round(revenue_by_buyer.get(b.id, 0.0), 2),
            transport_cost=round(transport_by_buyer.get(b.id, 0.0), 2),
            net_revenue=round(revenue_by_buyer.get(b.id, 0.0) - transport_by_buyer.get(b.id, 0.0), 2),
            net_price_per_kg=round((revenue_by_buyer[b.id] - transport_by_buyer[b.id]) / sold_by_buyer[b.id], 4)
            if sold_by_buyer.get(b.id, 0.0) > 0
            else None,
            max_demand_kg=b.max_demand,
            fulfillment_pct=round(100.0 * sold_by_buyer.get(b.id, 0.0) / b.max_demand, 2),
        )
        for b in inst.buyers
    ]

    return OptimizationResultModel(
        outcome=raw.outcome,
        outcome_label=outcome_label(raw.outcome, gap),
        gap_requested=gap,
        objective=built.objective,
        crop_id=inst.crop_id,
        horizon_days=inst.horizon,
        kpis=kpis,
        buyers=buyers,
        allocations=sorted(allocations, key=lambda a: (a.day, a.buyer_id, a.lot_id)),
        inventory=sorted(inventory, key=lambda r: (r.day, r.facility_id, r.lot_id)),
        trips=sorted(trips, key=lambda r: (r.day, r.buyer_id, r.vehicle_type_id)),
        waste=sorted(waste, key=lambda r: (r.day, r.lot_id)),
        constraints=constraint_report(built),
        warnings=list(inst.warnings),
        solve_seconds=round(raw.solve_seconds, 3),
    )


def _fleet_hours_available(built: BuiltModel) -> float | None:
    limited = [k for k in built.instance.vehicles if k.hours_per_day is not None]
    if not limited:
        return None
    return sum(k.count * (k.hours_per_day or 0.0) for k in limited) * built.instance.horizon


def constraint_report(built: BuiltModel) -> list[ConstraintInfo]:
    """Inequalities only (equalities are always tight and say nothing). lhs/rhs recomputed from
    PuLP's `lhs - rhs (sense) 0` form: rhs = -constant, lhs = value - constant."""
    names = built.instance.name_of
    report: list[ConstraintInfo] = []
    for registered in built.registry:
        if not registered.key.reportable or registered.sense == "==":
            continue
        c = registered.constraint
        rhs = -c.constant
        lhs = (c.value() or 0.0) - c.constant
        slack = rhs - lhs if registered.sense == "<=" else lhs - rhs
        slack = 0.0 if abs(slack) < ZERO else slack
        report.append(
            ConstraintInfo(
                key=str(registered.key),
                family=registered.key.family,
                entity=list(registered.key.entity),
                day=registered.key.day,
                label=registered.key.label(names),
                sense=registered.sense,
                lhs=round(lhs, 4),
                rhs=round(rhs, 4),
                slack=round(slack, 4),
                binding=slack <= BINDING_ABS_TOL + BINDING_REL_TOL * abs(rhs),
            )
        )
    return report


def _check_invariants(
    built: BuiltModel,
    sold_by_lot: dict[str, float],
    lost_by_lot: dict[str, float],
    ending_by_lot: dict[str, float],
    sold_by_buyer: dict[str, float],
    stock_by_facility_day: dict[tuple[str, int], float],
    shipped: dict[tuple[str, int], float],
    capacity_shipped: dict[tuple[str, int], float],
) -> None:
    inst = built.instance
    problems: list[str] = []
    for lot in inst.lots:
        tol = 1e-4 * max(1.0, lot.quantity)
        accounted = sold_by_lot.get(lot.id, 0.0) + lost_by_lot.get(lot.id, 0.0) + ending_by_lot.get(lot.id, 0.0)
        if abs(accounted - lot.quantity) > tol:
            problems.append(f"mass balance of lot {lot.id}: {accounted:.4f} != {lot.quantity}")
    for b in inst.buyers:
        if sold_by_buyer.get(b.id, 0.0) > b.max_demand * (1 + 1e-6) + 1e-4:
            problems.append(f"demand of {b.id} exceeded")
    capacity = {f.id: f.capacity for f in inst.facilities}
    for (f, t), stock in stock_by_facility_day.items():
        if stock > capacity[f] * (1 + 1e-6) + 1e-4:
            problems.append(f"capacity of {f} exceeded on day {t}")
    for key, kg in shipped.items():
        if kg > capacity_shipped.get(key, 0.0) * (1 + 1e-6) + 1e-4:
            problems.append(f"trips to {key[0]} on day {key[1]} carry less than delivered")
    if problems:
        raise EngineInvariantError(details={"violations": problems[:20]})

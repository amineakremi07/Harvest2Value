"""KPI formulas (plan §11) — the only place they are defined.

Inputs are plain numbers aggregated from solver values (no PuLP here), so the formulas are
testable in isolation and reusable for comparisons. There is no `net_profit`:
  realized_profit = realized_revenue - total_cost        (money actually earned)
  economic_value  = realized_profit + ending_inventory_value   ("valeur économique", not a profit)
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field

from ..domain.results import Kpis


@dataclass(frozen=True)
class KpiInputs:
    harvest_kg: float
    sold_kg: float
    realized_revenue: float
    transport_cost: float
    storage_cost: float
    disposal_cost: float
    ending_inventory_kg: float
    salvage_value_per_kg: float
    lost_kg: float
    reference_price_per_kg: float
    stored_kg: float  # kg placed in a storage facility
    inventory_kg_days: float  # sum of end-of-day stock over facilities and days
    trips: int
    trip_capacity_kg: float  # capacity of the trips made
    fleet_hours_used: float  # on vehicle types with a daily hour limit
    fleet_hours_available: float | None  # None: no vehicle type has an hour limit
    storage_occupancy: Sequence[tuple[float, float]] = ()  # (stock kg, capacity kg) per facility-day
    buyer_sold: Mapping[str, float] = field(default_factory=dict)
    buyer_net_revenue: Mapping[str, float] = field(default_factory=dict)  # revenue - transport
    buyer_max_demand: Mapping[str, float] = field(default_factory=dict)  # buyers eligible for the crop
    objective_value: float = 0.0


def _pct(part: float, whole: float) -> float | None:
    return 100.0 * part / whole if whole > 0 else None


def _r(value: float, digits: int = 2) -> float:
    return round(value, digits) + 0.0  # + 0.0 turns -0.0 into 0.0


def _opt(value: float | None, digits: int = 2) -> float | None:
    return None if value is None else _r(value, digits)


def compute_kpis(i: KpiInputs) -> Kpis:
    total_cost = i.transport_cost + i.storage_cost + i.disposal_cost
    realized_profit = i.realized_revenue - total_cost
    ending_value = i.ending_inventory_kg * i.salvage_value_per_kg
    occupancy = [stock / cap for stock, cap in i.storage_occupancy if cap > 0]
    sold_by_active = [i.buyer_sold.get(b, 0.0) for b in i.buyer_max_demand]
    active_buyers = {b: v for b, v in i.buyer_net_revenue.items() if i.buyer_sold.get(b, 0.0) > 1e-9}

    return Kpis(
        harvest_kg=_r(i.harvest_kg),
        sold_kg=_r(i.sold_kg),
        realized_revenue=_r(i.realized_revenue),
        transport_cost=_r(i.transport_cost),
        storage_cost=_r(i.storage_cost),
        disposal_cost=_r(i.disposal_cost),
        total_cost=_r(total_cost),
        realized_profit=_r(realized_profit),
        margin_pct=_opt(_pct(realized_profit, i.realized_revenue)),
        ending_inventory_kg=_r(i.ending_inventory_kg),
        ending_inventory_value=_r(ending_value),
        economic_value=_r(realized_profit + ending_value),
        lost_kg=_r(i.lost_kg),
        lost_value=_r(i.lost_kg * i.reference_price_per_kg),
        waste_rate_pct=_r(_pct(i.lost_kg, i.harvest_kg) or 0.0),
        sold_rate_pct=_r(_pct(i.sold_kg, i.harvest_kg) or 0.0),
        storage_rate_pct=_r(_pct(i.stored_kg, i.harvest_kg) or 0.0),
        fulfillment_rate_pct=_opt(_pct(sum(sold_by_active), sum(i.buyer_max_demand.values()))),
        vehicle_utilization_pct=_opt(_pct(i.fleet_hours_used, i.fleet_hours_available or 0.0)),
        load_factor_pct=_opt(_pct(i.sold_kg, i.trip_capacity_kg)),
        storage_utilization_peak_pct=_r(100.0 * max(occupancy)) if occupancy else None,
        storage_utilization_avg_pct=_r(100.0 * sum(occupancy) / len(occupancy)) if occupancy else None,
        trips=i.trips,
        avg_transport_cost_per_kg=_r(i.transport_cost / i.sold_kg, 4) if i.sold_kg > 0 else None,
        avg_storage_days=_r(i.inventory_kg_days / i.stored_kg) if i.stored_kg > 0 else None,
        objective_value=_r(i.objective_value, 4),
        best_buyer_id=max(active_buyers, key=lambda b: active_buyers[b]) if active_buyers else None,
    )

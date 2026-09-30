"""Hand-computed micro-problems. Each docstring shows the arithmetic the expected values come from.

Builder defaults (tests/fixtures/builders.py): price 1, demand 1e6, one truck of 1e6 kg with no
time limit and zero cost, distance 0, ambient shelf life 1 day, no storage, no decay, no loss.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from app.domain.dataset import DatasetPayload
from app.domain.enums import ObjectiveKind, SolverOutcome
from app.domain.run_config import ObjectiveWeights, RunConfig
from tests.fixtures.builders import buyer, crop, lot, make_payload, route, storage, vehicle


@dataclass(frozen=True)
class Case:
    name: str
    payload: DatasetPayload
    config: RunConfig
    outcome: SolverOutcome = SolverOutcome.OPTIMAL
    kpis: dict[str, Any] = field(default_factory=dict)  # expected Kpis fields (approx)
    sold_by_buyer: dict[str, float] = field(default_factory=dict)
    binding: set[str] = field(default_factory=set)  # constraint families expected binding


def direct_sale() -> Case:
    """1 000 kg, one buyer at 2.0 taking at most 800 kg, 50 per trip (1 000 kg truck).
    Sell 800 (1 trip): revenue 1 600, transport 50, profit 1 550; 200 kg lost on day 0."""
    return Case(
        "direct_sale",
        make_payload(
            lots=[lot("l1", 1000)],
            buyers=[buyer("b1", price=2.0, demand=800)],
            vehicles=[vehicle(capacity=1000, fixed_cost_per_trip=50)],
        ),
        RunConfig(),
        kpis=dict(sold_kg=800, lost_kg=200, realized_revenue=1600, transport_cost=50, realized_profit=1550, trips=1, storage_rate_pct=0),
        sold_by_buyer={"b1": 800},
        binding={"demand_max"},
    )


def storage_profitable() -> Case:
    """Price 1.0 today, 2.0 from day 2; storage 0.1/kg/day; 10 per trip; horizon 3 days.
    Sell today: 1 000 - 10 = 990.  Store 2 nights (end of day 0 and day 1): 1 000 x 0.1 x 2 = 200,
    sell on day 2: 2 000 - 200 - 10 = 1 790  ->  store."""
    return Case(
        "storage_profitable",
        make_payload(
            lots=[lot("l1", 1000)],
            buyers=[buyer("b1", price=1.0, price_schedule=[{"day": 2, "price": 2.0}])],
            crops=[crop(shelf_life_ambient_days=5)],
            storage_facilities=[storage(capacity=1000, cost=0.1)],
            vehicles=[vehicle(capacity=1000, fixed_cost_per_trip=10)],
        ),
        RunConfig(horizon_days=3),
        kpis=dict(sold_kg=1000, realized_revenue=2000, storage_cost=200, transport_cost=10, realized_profit=1790, storage_rate_pct=100, lost_kg=0),
    )


def storage_not_profitable() -> Case:
    """Same as storage_profitable with storage at 0.6/kg/day: storing costs 1 200, profit 790 < 990 -> sell today."""
    base = storage_profitable()
    payload = base.payload.model_copy(deep=True)
    payload.storage_facilities[0].cost_per_kg_per_day = 0.6
    return Case(
        "storage_not_profitable",
        payload,
        base.config,
        kpis=dict(sold_kg=1000, realized_revenue=1000, storage_cost=0, realized_profit=990, storage_rate_pct=0),
    )


def forced_expiry() -> Case:
    """Shelf life 2 days (held until end of day 1), buyer only receives from day 3: nothing can be sold.
    All 1 000 kg are lost, profit 0."""
    return Case(
        "forced_expiry",
        make_payload(
            lots=[lot("l1", 1000)],
            buyers=[buyer("b1", price=2.0, window_start_day=3)],
            crops=[crop(shelf_life_ambient_days=2)],
            storage_facilities=[storage(capacity=1000, cost=0.0)],
        ),
        RunConfig(horizon_days=6),
        kpis=dict(sold_kg=0, lost_kg=1000, realized_profit=0, waste_rate_pct=100, ending_inventory_kg=0),
    )


def storage_saturated() -> Case:
    """Buyer (2.0) only from day 1; storage 600 kg at 0.1/kg/day; 10 per trip; horizon 2 days.
    Store 600 one night (60), sell 600 on day 1: 1 200 - 60 - 10 = 1 130; 400 kg lost on day 0."""
    return Case(
        "storage_saturated",
        make_payload(
            lots=[lot("l1", 1000)],
            buyers=[buyer("b1", price=2.0, window_start_day=1)],
            crops=[crop(shelf_life_ambient_days=5)],
            storage_facilities=[storage(capacity=600, cost=0.1)],
            vehicles=[vehicle(capacity=1000, fixed_cost_per_trip=10)],
        ),
        RunConfig(horizon_days=2),
        kpis=dict(sold_kg=600, lost_kg=400, storage_cost=60, realized_profit=1130, storage_utilization_peak_pct=100),
        binding={"storage_capacity"},
    )


def fleet_limiting() -> Case:
    """5 000 kg, 2 trucks of 1 000 kg, 10 h/day, 100 km at 50 km/h + 1 h loading = 5 h per round trip.
    20 h available -> 4 trips -> 4 000 kg sold, 1 000 kg lost."""
    return Case(
        "fleet_limiting",
        make_payload(
            lots=[lot("l1", 5000)],
            buyers=[buyer("b1", price=1.0, demand=10000)],
            vehicles=[vehicle(capacity=1000, count=2, hours_per_day=10, avg_speed_kmh=50, loading_hours_per_trip=1)],
            routes=[route("b1", distance=100)],
        ),
        RunConfig(),
        kpis=dict(sold_kg=4000, lost_kg=1000, trips=4, vehicle_utilization_pct=100, load_factor_pct=100),
        binding={"fleet_time"},
    )


def cold_chain() -> Case:
    """Cold-chain crop: 5 free ambient trucks are unusable; 1 reefer (500 kg, 1 trip/day, 20 per trip).
    Sell 500 at 2.0: 1 000 - 20 = 980; 500 kg lost."""
    return Case(
        "cold_chain",
        make_payload(
            lots=[lot("l1", 1000)],
            buyers=[buyer("b1", price=2.0)],
            crops=[crop(requires_cold_chain=True)],
            vehicles=[
                vehicle("truck", capacity=1e6, count=5),
                vehicle("reefer", capacity=500, count=1, refrigerated=True, max_trips_per_day=1, fixed_cost_per_trip=20),
            ],
        ),
        RunConfig(),
        kpis=dict(sold_kg=500, lost_kg=500, realized_profit=980, trips=1),
        binding={"fleet_trips"},
    )


def minimum_order() -> Case:
    """500 kg; buyer A pays 3.0 but orders at least 800 kg, buyer B pays 1.0.
    A's minimum cannot be met -> everything to B: profit 500."""
    return Case(
        "minimum_order",
        make_payload(
            lots=[lot("l1", 500)],
            buyers=[buyer("a", price=3.0, demand=1000, min_order_kg=800), buyer("b", price=1.0, demand=1000)],
        ),
        RunConfig(),
        kpis=dict(sold_kg=500, realized_profit=500, lost_kg=0),
        sold_by_buyer={"a": 0, "b": 500},
    )


def min_contract_infeasible() -> Case:
    """A 2 000 kg contract minimum with only 1 000 kg harvested: infeasible."""
    return Case(
        "min_contract_infeasible",
        make_payload(lots=[lot("l1", 1000)], buyers=[buyer("b1", demand=3000, min_contract_kg=2000)]),
        RunConfig(),
        outcome=SolverOutcome.INFEASIBLE,
    )


def _costly_trip_payload() -> DatasetPayload:
    return make_payload(
        lots=[lot("l1", 1000)],
        buyers=[buyer("x", price=1.0, demand=1000)],
        vehicles=[vehicle(capacity=1000, fixed_cost_per_trip=1100)],
    )


def profit_refuses_costly_trip() -> Case:
    """Selling 1 000 kg at 1.0 needs a 1 100 trip: profit -100 < 0 -> profit mode sells nothing."""
    return Case(
        "profit_refuses_costly_trip",
        _costly_trip_payload(),
        RunConfig(objective=ObjectiveKind.PROFIT),
        kpis=dict(sold_kg=0, lost_kg=1000, realized_profit=0),
    )


def weighted_accepts_costly_trip() -> Case:
    """Weights profit 1, waste 2. Payoff table: profit-optimum (profit 0, waste 1 000), waste-optimum
    (profit -100, waste 0). Normalized: sell all -> 1 x 1 + 2 x 0 = 1 ; sell nothing -> 0 + 2 x 1 = 2 -> sell."""
    return Case(
        "weighted_accepts_costly_trip",
        _costly_trip_payload(),
        RunConfig(objective=ObjectiveKind.WEIGHTED, weights=ObjectiveWeights(profit=1, waste=2)),
        kpis=dict(sold_kg=1000, lost_kg=0, realized_profit=-100),
    )


def revenue_mode_sells_everything() -> Case:
    return Case(
        "revenue_mode_sells_everything",
        _costly_trip_payload(),
        RunConfig(objective=ObjectiveKind.REVENUE),
        kpis=dict(sold_kg=1000, realized_revenue=1000),
    )


def waste_mode_sells_everything() -> Case:
    return Case(
        "waste_mode_sells_everything",
        _costly_trip_payload(),
        RunConfig(objective=ObjectiveKind.WASTE),
        kpis=dict(sold_kg=1000, lost_kg=0),
    )


def cost_mode_meets_service_level() -> Case:
    """At least 50 % must be sold: one trip (1 100) is unavoidable and carries up to 1 000 kg."""
    return Case(
        "cost_mode_meets_service_level",
        _costly_trip_payload(),
        RunConfig(objective=ObjectiveKind.COST, service_level_min=0.5),
        kpis=dict(total_cost=1100, trips=1),
    )


ALL_CASES = [
    direct_sale,
    storage_profitable,
    storage_not_profitable,
    forced_expiry,
    storage_saturated,
    fleet_limiting,
    cold_chain,
    minimum_order,
    min_contract_infeasible,
    profit_refuses_costly_trip,
    weighted_accepts_costly_trip,
    revenue_mode_sells_everything,
    waste_mode_sells_everything,
    cost_mode_meets_service_level,
]

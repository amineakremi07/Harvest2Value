"""Properties that must hold for any small random instance (hypothesis)."""

from __future__ import annotations

from hypothesis import HealthCheck, given, settings
from hypothesis import strategies as st

from app.domain.enums import SolverOutcome
from app.domain.run_config import RunConfig
from app.optimization.engine import OptimizationEngine
from tests.fixtures.builders import buyer, crop, lot, make_payload, route, storage, vehicle

ENGINE = OptimizationEngine()


@st.composite
def instances(draw):
    lots = [
        lot(f"l{i}", draw(st.integers(100, 2000)), day=draw(st.integers(0, 3)))
        for i in range(draw(st.integers(1, 2)))
    ]
    buyers, routes = [], []
    for i in range(draw(st.integers(1, 3))):
        kw = {}
        if draw(st.booleans()):
            kw["max_per_day_kg"] = draw(st.integers(100, 1500))
        if draw(st.booleans()):
            kw["price_schedule"] = [{"day": draw(st.integers(1, 4)), "price": draw(st.floats(0, 6))}]
        if draw(st.integers(0, 4)) == 0:
            kw["min_order_kg"] = draw(st.integers(50, 500))
        demand = draw(st.integers(600, 3000))
        buyers.append(buyer(f"b{i}", price=draw(st.floats(0, 5)), demand=demand, **kw))
        routes.append(route(f"b{i}", distance=draw(st.integers(0, 200))))
    facilities = []
    if draw(st.booleans()):
        facilities.append(storage(capacity=draw(st.integers(0, 2000)), cost=draw(st.floats(0, 0.5))))
    hours = draw(st.one_of(st.none(), st.floats(6, 12)))
    return make_payload(
        lots=lots,
        buyers=buyers,
        routes=routes,
        crops=[
            crop(
                shelf_life_ambient_days=draw(st.integers(1, 5)),
                loss_rate_pct_per_day_ambient=draw(st.floats(0, 20)),
                quality_decay_pct_per_day=draw(st.floats(0, 10)),
            )
        ],
        storage_facilities=facilities,
        vehicles=[
            vehicle(
                capacity=draw(st.integers(200, 2000)),
                count=draw(st.integers(1, 3)),
                fixed_cost_per_trip=draw(st.floats(0, 200)),
                cost_per_km=draw(st.floats(0, 2)),
                hours_per_day=hours,
                avg_speed_kmh=60,
                loading_hours_per_trip=0.5,
            )
        ],
    )


@settings(max_examples=40, deadline=None, suppress_health_check=[HealthCheck.too_slow])
@given(instances())
def test_plan_invariants(payload) -> None:
    out = ENGINE.run(payload, RunConfig(horizon_days=6))
    assert out.outcome == SolverOutcome.OPTIMAL
    result = out.result
    assert result is not None
    k = result.kpis

    # mass balance: every harvested kg is sold, lost or still in stock
    assert abs(k.harvest_kg - (k.sold_kg + k.lost_kg + k.ending_inventory_kg)) <= 0.05
    # never above a buyer's demand
    demand = {b.id: b.max_demand_kg for b in payload.buyers}
    for b in result.buyers:
        assert b.sold_kg <= demand[b.buyer_id] + 0.01
    # profit never exceeds revenue, and is exactly revenue - costs
    assert k.realized_profit <= k.realized_revenue + 0.01
    assert abs(k.realized_profit - (k.realized_revenue - k.total_cost)) <= 0.02
    # a profit-maximizing plan never loses money: selling nothing is always possible
    assert k.realized_profit >= -0.01
    if k.storage_utilization_peak_pct is not None:
        assert k.storage_utilization_peak_pct <= 100.01
    # allocations add up to the KPIs
    assert abs(sum(a.kg for a in result.allocations) - k.sold_kg) <= 0.05 * max(1, len(result.allocations))

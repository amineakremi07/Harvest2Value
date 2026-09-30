"""Analytics sections, market ranking, network and comparison: consistency with the solver result."""

from __future__ import annotations

import pytest

from app.analytics.buyers import buyers
from app.analytics.comparison import ComparedRun, compare
from app.analytics.crops import crops
from app.analytics.financial import financial
from app.analytics.logistics import logistics
from app.analytics.market import analyze_market
from app.analytics.network import network
from app.analytics.operational import operational
from app.core.errors import ValidationFailed
from app.domain.dataset import DatasetPayload
from app.domain.run_config import RunConfig
from app.domain.scenario import parse_change
from app.optimization.engine import OptimizationEngine
from app.scenarios.apply import apply_changes
from tests.fixtures.builders import TEMPLATES, buyer, crop, lot, make_payload, route, vehicle
from tests.fixtures.runs import solve_context

ENGINE = OptimizationEngine()


@pytest.fixture(scope="module")
def dates():
    payload = DatasetPayload.model_validate_json(next(p for p in TEMPLATES if p.stem == "tunisia_dates").read_text(encoding="utf-8"))
    return solve_context(payload, duals=False)


def test_financial_waterfall_adds_up(dates) -> None:
    section = financial(dates)
    k = dates.result.kpis
    assert sum(step.value for step in section.waterfall[:-1]) == pytest.approx(k.realized_profit, abs=0.02)
    assert section.waterfall[-1].value == k.realized_profit
    assert sum(d.revenue for d in section.daily) == pytest.approx(k.realized_revenue, abs=0.05)
    assert sum(d.transport_cost for d in section.daily) == pytest.approx(k.transport_cost, abs=0.05)
    assert sum(d.storage_cost for d in section.daily) == pytest.approx(k.storage_cost, abs=0.05)
    assert sum(b.share_of_revenue_pct or 0 for b in section.by_buyer) == pytest.approx(100, abs=0.05)


def test_operational_flows_add_up(dates) -> None:
    section = operational(dates)
    k = dates.result.kpis
    assert sum(d.sold_kg for d in section.daily) == pytest.approx(k.sold_kg, abs=0.1)
    assert sum(d.lost_kg for d in section.daily) == pytest.approx(k.lost_kg, abs=0.1)
    assert sum(section.waste_by_kind.values()) == pytest.approx(k.lost_kg, abs=0.1)
    assert len(section.daily) == dates.result.horizon_days
    assert max(s.peak_pct or 0 for s in section.storage) == pytest.approx(k.storage_utilization_peak_pct, abs=0.01)


def test_buyers_section(dates) -> None:
    section = buyers(dates)
    assert sum(b.sold_kg for b in section.buyers) == pytest.approx(dates.result.kpis.sold_kg, abs=0.1)
    assert section.best_buyer_id == dates.result.kpis.best_buyer_id
    assert [b.sold_kg for b in section.buyers] == sorted((b.sold_kg for b in section.buyers), reverse=True)


def test_logistics_section_on_a_fleet_limited_case() -> None:
    """2 trucks x 10 h, 5 h per trip: 4 trips, 20 h used out of 20 h, fleet binds on day 0."""
    payload = make_payload(
        lots=[lot("l1", 5000)],
        buyers=[buyer("b1", demand=10000)],
        vehicles=[vehicle(capacity=1000, count=2, hours_per_day=10, avg_speed_kmh=50, loading_hours_per_trip=1, fixed_cost_per_trip=10)],
        routes=[route("b1", distance=100)],
    )
    section = logistics(solve_context(payload))
    (truck,) = section.vehicles
    assert (truck.trips, truck.hours, truck.hours_available, truck.utilization_pct, truck.binding_days) == (4, 20, 20, 100, [0])
    assert section.cost_per_trip == 10 and section.routes[0].cost_per_kg == pytest.approx(0.01)


def test_crops_section(dates) -> None:
    section = crops(dates)
    assert section.value_curve[0].price_multiplier == 1
    assert sum(l.quantity_kg for l in section.lots) == pytest.approx(dates.result.kpis.harvest_kg)
    assert sum(l.sold_kg + l.lost_kg + l.ending_kg for l in section.lots) == pytest.approx(dates.result.kpis.harvest_kg, abs=0.1)
    assert section.risk_level in ("high", "medium", "low")


def test_network_flows_match_the_plan(dates) -> None:
    graph = network(dates)
    sales = [e for e in graph.edges if e.kind == "sale"]
    assert sum(e.kg for e in sales) == pytest.approx(dates.result.kpis.sold_kg, abs=0.1)
    ids = {n.id for n in graph.nodes}
    assert all(e.source in ids and e.target in ids for e in graph.edges)
    day0 = network(dates, day=0)
    assert all(e.kind != "sale" or e.kg <= dates.sold_by_day.get(0, 0) + 0.01 for e in day0.edges)


def test_market_ranks_by_estimated_net_price() -> None:
    """a: 2.0 - 100/1000 = 1.9 ; b: 2.2 - 500/1000 = 1.7 ; c: cold chain, no reefer -> unreachable."""
    payload = make_payload(
        lots=[lot("l1", 1000)],
        buyers=[buyer("a", price=2.0, demand=5000), buyer("b", price=2.2, demand=5000), buyer("c", requires_cold_chain=True)],
        vehicles=[vehicle(capacity=1000, cost_per_km=1.0)],
        routes=[route("a", distance=50), route("b", distance=250), route("c", distance=10)],
    )
    rows = {r.buyer_id: r for r in analyze_market(payload).rows}
    assert rows["a"].net_price_per_kg == pytest.approx(1.9) and rows["a"].rank == 1
    assert rows["b"].net_price_per_kg == pytest.approx(1.7) and rows["b"].rank == 2
    assert not rows["c"].reachable and rows["c"].rank is None and rows["c"].unreachable_reason == "needs a refrigerated vehicle"


def test_market_needs_a_crop_when_several_are_harvested() -> None:
    payload = make_payload(
        lots=[lot("l1", 1000), lot("l2", 500, crop_id="d")],
        buyers=[buyer("a", crop_ids=["c", "d"])],
        crops=[crop(), crop(id="d", name="Other")],
    )
    with pytest.raises(ValidationFailed):
        analyze_market(payload)
    assert analyze_market(payload, "d").crop_id == "d"


# ---- comparison ----

def _compared(run_id: str, payload: DatasetPayload) -> ComparedRun:
    result = ENGINE.run(payload, RunConfig()).result
    return ComparedRun(run_id=run_id, label=run_id, scenario_id=None, result=result, payload=payload)


def test_comparison_with_added_and_removed_buyers() -> None:
    base = make_payload(lots=[lot("l1", 1000)], buyers=[buyer("a", price=2.0, demand=600), buyer("b", price=1.0)])
    removed = apply_changes(base, [parse_change({"op": "remove_buyer", "target": "b"})]).effective
    added = apply_changes(
        base,
        [parse_change({"op": "add_buyer", "params": {"buyer": {"id": "n", "name": "New", "location": "Sousse", "crop_ids": ["c"], "price_per_kg": 1.5, "max_demand_kg": 5000}, "route": {"buyer_id": "n", "distance_km": 0}}})],
    ).effective
    result = compare(_compared("base", base), [_compared("minus_b", removed), _compared("plus_n", added)])

    matrix = {row.buyer_id: row.cells for row in result.buyer_matrix}
    assert matrix["b"]["minus_b"].status == "removed" and matrix["b"]["minus_b"].sold_kg is None
    assert matrix["b"]["minus_b"].delta_kg == -400
    assert matrix["n"]["plus_n"].status == "added" and matrix["n"]["plus_n"].sold_kg == 400
    assert matrix["n"]["base"].status == "absent"
    assert matrix["a"]["plus_n"].status == "common" and matrix["a"]["plus_n"].delta_kg == 0

    profit = next(r for r in result.kpi_table if r.kpi == "realized_profit")
    assert profit.values == {"base": 1600, "minus_b": 1200, "plus_n": 1800}
    assert profit.deltas["minus_b"].abs == -400 and profit.deltas["minus_b"].pct == -25
    assert profit.best_run_id == "plus_n"
    lost = next(r for r in result.kpi_table if r.kpi == "lost_kg")
    assert lost.better == "lower" and lost.best_run_id is None  # base and plus_n tie at 0 kg lost

    codes = {(c.code, c.run_id) for c in result.notable_changes}
    assert {("BUYER_REMOVED", "minus_b"), ("BUYER_ADDED", "plus_n"), ("PROFIT_CHANGE", "minus_b"), ("PROFIT_CHANGE", "plus_n")} <= codes
    removed_msg = next(c.message for c in result.notable_changes if c.code == "BUYER_REMOVED")
    assert removed_msg == "Buyer B is removed (it received 400 kg)."
    assert len(result.series["sold_kg_by_day"]) == 1 and result.series["sold_kg_by_day"][0].values["plus_n"] == 1000


def test_comparison_volume_change_uses_was() -> None:
    base = make_payload(lots=[lot("l1", 5000)], buyers=[buyer("a", price=2.0, demand=1000), buyer("b", price=1.0)])
    more = apply_changes(base, [parse_change({"op": "buyer_demand", "target": "a", "params": {"field": "max_demand_kg", "mode": "absolute", "value": 3000}})]).effective
    result = compare(_compared("base", base), [_compared("more", more)])
    change = next(c for c in result.notable_changes if c.code == "BUYER_VOLUME_CHANGE" and c.params["buyer_id"] == "a")
    assert change.message == "A gets 2,000 kg: 3,000 kg (was 1,000 kg)."

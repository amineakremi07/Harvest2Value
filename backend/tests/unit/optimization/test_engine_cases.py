"""End to end on the hand-computed micro-problems (tests/fixtures/solver/cases.py)."""

from __future__ import annotations

import asyncio

import pytest

from app.core.errors import ValidationFailed
from app.domain.enums import SolverOutcome
from app.domain.run_config import RunConfig
from app.optimization.engine import OptimizationEngine
from tests.fixtures.builders import buyer, lot, make_payload, vehicle
from tests.fixtures.solver.cases import ALL_CASES, Case

ENGINE = OptimizationEngine()


@pytest.mark.parametrize("make_case", ALL_CASES, ids=lambda f: f.__name__)
def test_case(make_case) -> None:
    case: Case = make_case()
    out = ENGINE.run(case.payload, case.config)

    assert out.outcome == case.outcome
    if case.outcome != SolverOutcome.OPTIMAL:
        assert out.result is None
        return
    result = out.result
    assert result is not None
    for name, expected in case.kpis.items():
        assert getattr(result.kpis, name) == pytest.approx(expected, abs=0.01), name
    sold = {b.buyer_id: b.sold_kg for b in result.buyers}
    for buyer_id, expected in case.sold_by_buyer.items():
        assert sold[buyer_id] == pytest.approx(expected, abs=0.01), buyer_id
    binding = {c.family for c in result.constraints if c.binding}
    assert case.binding <= binding, binding


def test_storage_profitable_sells_everything_on_day_2() -> None:
    from tests.fixtures.solver.cases import storage_profitable

    case = storage_profitable()
    result = ENGINE.run(case.payload, case.config).result
    assert result is not None
    assert [(a.day, a.facility_id, a.kg) for a in result.allocations] == [(2, "store", 1000)]
    assert [(r.day, r.kg_end) for r in result.inventory] == [(0, 1000), (1, 1000)]
    assert result.kpis.avg_storage_days == 2


def test_cold_chain_uses_only_the_reefer() -> None:
    from tests.fixtures.solver.cases import cold_chain

    result = ENGINE.run(cold_chain().payload, cold_chain().config).result
    assert result is not None
    assert {t.vehicle_type_id for t in result.trips} == {"reefer"}
    assert any(c.family == "cold_chain_vehicle" and c.entity == ["b1", "truck"] for c in result.constraints)


def test_daily_loss_is_reported_as_waste() -> None:
    """Sell 500 kg on day 2 (price 5) with 10 %/day storage loss: 617.28 kg must be stored on day 0."""
    p = make_payload(
        lots=[lot("l1", 1000)],
        buyers=[buyer("b1", price=1.0, price_schedule=[{"day": 2, "price": 5.0}], window_start_day=2, max_per_day_kg=500)],
        crops=[{"id": "c", "name": "Crop", "type": "perishable", "reference_price_per_kg": 2.0, "shelf_life_ambient_days": 3, "loss_rate_pct_per_day_ambient": 10}],
        storage_facilities=[{"id": "s", "name": "S", "capacity_kg": 1000, "cost_per_kg_per_day": 0.01}],
    )
    result = ENGINE.run(p, RunConfig()).result
    assert result is not None
    k = result.kpis
    assert k.sold_kg == pytest.approx(500, abs=0.01)
    loss = sum(w.kg for w in result.waste if w.kind == "daily_loss")
    assert loss == pytest.approx(500 / 0.81 - 500, abs=0.05)  # 61.73 + 55.56
    assert k.harvest_kg == pytest.approx(k.sold_kg + k.lost_kg + k.ending_inventory_kg, abs=0.05)
    assert k.lost_value == pytest.approx(k.lost_kg * 2.0, abs=0.05)


def test_expired_stock_is_reported_as_waste() -> None:
    """Expiry and harvest-day loss cost the same, so the solver may pick either: check the
    reporting on a hand-set solution (1 000 kg stored two days, then expired)."""
    from app.domain.enums import ObjectiveKind
    from app.optimization.builder import ModelBuilder
    from app.optimization.instance import DIRECT, build_instance
    from app.optimization.postprocess import extract
    from app.optimization.runner import RawSolution
    from tests.fixtures.solver.cases import forced_expiry

    case = forced_expiry()
    built = ModelBuilder().build(build_instance(case.payload, case.config), case.config)
    v = built.vars
    for var in [*v.z.values(), *v.unsold.values(), *v.inv.values(), *v.expired.values(), *v.x.values(), *v.n.values()]:
        var.varValue = 0.0
    v.z[("l1", "store")].varValue = 1000
    v.inv[("l1", "store", 0)].varValue = 1000
    v.inv[("l1", "store", 1)].varValue = 1000
    v.expired[("l1", "store")].varValue = 1000
    assert v.z[("l1", DIRECT)].varValue == 0 and built.objective == ObjectiveKind.PROFIT

    result = extract(built, RawSolution(SolverOutcome.OPTIMAL, "Optimal", 1, 0.0, 0.0))
    assert [(w.kind, w.day, w.facility_id, w.kg) for w in result.waste] == [("expired", 1, "store", 1000)]
    assert result.kpis.lost_kg == 1000 and result.kpis.storage_rate_pct == 100


def test_salvage_value_is_economic_value_not_profit() -> None:
    p = make_payload(
        lots=[lot("l1", 1000)],
        buyers=[buyer("b1", price=1.0, demand=400)],
        crops=[{"id": "c", "name": "Crop", "type": "durable", "reference_price_per_kg": 1.0, "shelf_life_ambient_days": 30}],
        storage_facilities=[{"id": "s", "name": "S", "capacity_kg": 1000, "cost_per_kg_per_day": 0.0}],
    )
    result = ENGINE.run(p, RunConfig(horizon_days=5, salvage_value_pct=50)).result
    assert result is not None
    k = result.kpis
    assert (k.sold_kg, k.ending_inventory_kg) == (400, 600)
    assert k.realized_profit == 400 and k.ending_inventory_value == 300 and k.economic_value == 700
    assert k.realized_revenue == 400  # the stock is never counted as revenue


def test_blocking_dataset_errors_stop_the_run() -> None:
    p = make_payload(lots=[lot("l1", 10)], buyers=[buyer("b1")], vehicles=[vehicle(count=0)])
    with pytest.raises(ValidationFailed) as exc:
        ENGINE.run(p, RunConfig())
    assert exc.value.code == "DATASET_INVALID"


def test_run_async() -> None:
    from tests.fixtures.solver.cases import direct_sale

    out = asyncio.run(ENGINE.run_async(direct_sale().payload, direct_sale().config))
    assert out.outcome == SolverOutcome.OPTIMAL and out.result is not None and out.result.kpis.realized_profit == 1550


def test_gap_is_configurable_and_reported() -> None:
    from tests.fixtures.solver.cases import direct_sale

    case = direct_sale()
    default = ENGINE.run(case.payload, case.config).result
    strict = ENGINE.run(case.payload, RunConfig(gap=0.001)).result
    assert default is not None and strict is not None
    assert (default.gap_requested, strict.gap_requested) == (0.01, 0.001)
    assert strict.outcome_label == "Optimal within 0.1% of the best possible plan"

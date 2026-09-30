"""Regressions R1-R4 from the V1 audit, plus template-level checks and performance.

R1  inventory was valued as if already sold          -> revenue only counts real sales
R2  `net_profit` mixed profit and inventory value    -> realized_profit / economic_value
R3  shelf life was read but never constrained        -> no sale after a lot's shelf life
R4  solver status was never checked                  -> no KPIs without a solution
"""

from __future__ import annotations

import time

import pytest

from app.domain.dataset import DatasetPayload
from app.domain.enums import SolverOutcome
from app.domain.migrations_v1 import migrate_v1_to_v2
from app.domain.run_config import RunConfig
from app.optimization.engine import OptimizationEngine
from tests.fixtures.builders import TEMPLATES, V1_FIXTURES, buyer, crop, load_json, lot, make_payload, storage, vehicle
from tests.fixtures.solver.cases import min_contract_infeasible

ENGINE = OptimizationEngine()


def template(path) -> DatasetPayload:
    return DatasetPayload.model_validate_json(path.read_text(encoding="utf-8"))


@pytest.fixture(scope="module")
def template_results():
    return {p.stem: ENGINE.run(template(p), RunConfig()) for p in TEMPLATES}


# ---- R1 ----

@pytest.mark.parametrize("path", V1_FIXTURES, ids=lambda p: p.stem)
def test_r1_v1_compatibility_never_stores_without_a_later_sale(path) -> None:
    """V1 stored 4 000 kg of olives because storage was valued at the average price.
    In compatibility mode (1 day) nothing can be sold later, so nothing is stored."""
    payload, _ = migrate_v1_to_v2(load_json(path))
    result = ENGINE.run(payload, RunConfig()).result
    assert result is not None
    assert result.kpis.storage_rate_pct == 0 and result.kpis.storage_cost == 0
    assert result.kpis.ending_inventory_kg == 0


def test_r1_v1_olives_bias_is_gone() -> None:
    payload, _ = migrate_v1_to_v2(load_json(next(p for p in V1_FIXTURES if p.stem == "tunisia_olives")))
    k = ENGINE.run(payload, RunConfig()).result.kpis  # type: ignore[union-attr]
    assert k.realized_profit <= k.realized_revenue
    assert k.realized_profit < 26444.0  # v1 `net_profit`, inflated by 4 000 kg of fictitious storage value


def test_r1_revenue_is_only_sales(template_results) -> None:
    for name, out in template_results.items():
        r = out.result
        assert r is not None, name
        assert r.kpis.realized_revenue == pytest.approx(sum(a.revenue for a in r.allocations), abs=0.05 * len(r.allocations) + 0.01)
        assert r.kpis.ending_inventory_value == 0  # default salvage value is 0


# ---- R2 ----

def test_r2_profit_is_revenue_minus_costs(template_results) -> None:
    for out in template_results.values():
        k = out.result.kpis  # type: ignore[union-attr]
        assert k.realized_profit == pytest.approx(k.realized_revenue - k.total_cost, abs=0.02)
        assert k.realized_profit <= k.realized_revenue
        assert k.economic_value == pytest.approx(k.realized_profit + k.ending_inventory_value, abs=0.02)
        assert not hasattr(k, "net_profit")


# ---- R3 ----

def test_r3_no_sale_after_shelf_life(template_results) -> None:
    for name, out in template_results.items():
        payload = template(next(p for p in TEMPLATES if p.stem == name))
        crop_ = payload.crops[0]
        lot_day = {lot_.id: lot_.available_day for lot_ in payload.harvest_lots}
        cold = {f.id: f.refrigerated for f in payload.storage_facilities}
        for a in out.result.allocations:  # type: ignore[union-attr]
            if a.facility_id is None:
                assert a.day == lot_day[a.lot_id], name
            else:
                shelf = (crop_.shelf_life_cold_days or crop_.shelf_life_ambient_days) if cold[a.facility_id] else crop_.shelf_life_ambient_days
                assert lot_day[a.lot_id] < a.day <= lot_day[a.lot_id] + shelf - 1, name


def test_r3_perishable_stock_is_lost_after_shelf_life() -> None:
    """Shelf life 2 days: the buyer only opens on day 4, nothing can reach it."""
    p = make_payload(
        lots=[lot("l1", 1000)],
        buyers=[buyer("b1", price=3.0, window_start_day=4)],
        crops=[crop(shelf_life_ambient_days=2)],
        storage_facilities=[storage(capacity=1000)],
    )
    k = ENGINE.run(p, RunConfig(horizon_days=6)).result.kpis  # type: ignore[union-attr]
    assert k.sold_kg == 0 and k.lost_kg == 1000


# ---- R4 ----

def test_r4_infeasible_run_has_no_kpis() -> None:
    case = min_contract_infeasible()
    out = ENGINE.run(case.payload, case.config)
    assert out.outcome == SolverOutcome.INFEASIBLE and out.result is None


def test_r4_time_limit_without_solution_is_not_a_result(monkeypatch) -> None:
    from app.optimization import runner as runner_module

    monkeypatch.setattr(runner_module, "map_status", lambda status, sol_status: SolverOutcome.NOT_SOLVED)
    case = min_contract_infeasible()
    payload = case.payload.model_copy(deep=True)
    payload.buyers[0].min_contract_kg = None
    out = ENGINE.run(payload, RunConfig())
    assert out.outcome == SolverOutcome.NOT_SOLVED and out.result is None


# ---- templates ----

def test_all_templates_are_optimal_and_coherent(template_results) -> None:
    assert len(template_results) == 5
    for name, out in template_results.items():
        assert out.outcome == SolverOutcome.OPTIMAL, name
        k = out.result.kpis  # type: ignore[union-attr]
        assert k.harvest_kg == pytest.approx(k.sold_kg + k.lost_kg + k.ending_inventory_kg, abs=0.05), name
        assert 0 <= k.waste_rate_pct <= 100 and k.sold_kg > 0 and k.realized_profit > 0, name
        assert not [c for c in out.result.constraints if c.slack < -1e-3], name  # type: ignore[union-attr]


def test_storage_is_only_chosen_when_it_pays() -> None:
    """Remove every storage facility and re-solve: if the plan stored anything, it must have
    earned strictly more with storage; if storage brings nothing, nothing is stored.
    Solved exactly (gap 0): two plans that are each "within 1 %" cannot be compared."""
    exact = RunConfig(gap=0.0)
    for path in TEMPLATES:
        with_storage = ENGINE.run(template(path), exact).result
        assert with_storage is not None
        payload = template(path).model_copy(deep=True)
        payload.storage_facilities = []
        without = ENGINE.run(payload, exact.model_copy(update={"horizon_days": with_storage.horizon_days})).result
        assert without is not None
        stored = with_storage.kpis.storage_rate_pct
        gain = with_storage.kpis.realized_profit - without.kpis.realized_profit
        assert gain >= -0.05, path.stem
        if stored > 0.01:
            assert gain > 0.05, (path.stem, stored, gain)


# ---- performance ----

@pytest.mark.parametrize("path", TEMPLATES, ids=lambda p: p.stem)
def test_template_solves_under_5_seconds(path) -> None:
    started = time.perf_counter()
    ENGINE.run(template(path), RunConfig())
    assert time.perf_counter() - started < 5.0


def test_30_day_case_solves_under_5_seconds() -> None:
    """6 lots over 30 days, 8 buyers with daily limits and price schedules, 2 facilities, 2 vehicle types."""
    buyers = [
        buyer(
            f"b{i}",
            price=1.0 + 0.15 * i,
            demand=4000 + 500 * i,
            max_per_day_kg=600,
            price_schedule=[{"day": 10 + 2 * i, "price": 1.3 + 0.15 * i}],
        )
        for i in range(8)
    ]
    from tests.fixtures.builders import route

    p = make_payload(
        lots=[lot(f"l{i}", 5000, day=5 * i) for i in range(6)],
        buyers=buyers,
        routes=[route(f"b{i}", distance=20 + 30 * i, road_factor_override=None, road_condition="fair") for i in range(8)],
        crops=[crop(shelf_life_ambient_days=10, shelf_life_cold_days=20, quality_decay_pct_per_day=0.5, loss_rate_pct_per_day_ambient=0.5, loss_rate_pct_per_day_cold=0.1)],
        storage_facilities=[storage("amb", capacity=8000, cost=0.02), storage("cold", capacity=4000, cost=0.05, refrigerated=True)],
        vehicles=[
            vehicle("truck", capacity=3000, count=3, fixed_cost_per_trip=40, cost_per_km=1.1, hours_per_day=12, avg_speed_kmh=60, loading_hours_per_trip=1),
            vehicle("reefer", capacity=2000, count=1, refrigerated=True, fixed_cost_per_trip=60, cost_per_km=1.4, hours_per_day=12, avg_speed_kmh=60, loading_hours_per_trip=1),
        ],
    )
    started = time.perf_counter()
    out = ENGINE.run(p, RunConfig(horizon_days=30))
    elapsed = time.perf_counter() - started
    assert out.outcome == SolverOutcome.OPTIMAL and out.horizon_days == 30
    assert out.result is not None and out.result.gap_requested == 0.01
    assert out.result.outcome_label == "Optimal within 1.0% of the best possible plan"
    assert elapsed < 5.0, f"{elapsed:.2f}s"

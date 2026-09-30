"""Marginal values: CBC duals on known LPs (phase 4 check), reliability flags, perturbation probes."""

from __future__ import annotations

import pytest
from pulp import PULP_CBC_CMD, LpMaximize, LpProblem, LpVariable

from app.analytics.context import RunContext
from app.domain.enums import SolverOutcome
from app.domain.results import WasteRow
from app.domain.run_config import RunConfig
from app.domain.scenario import parse_change
from app.optimization.engine import OptimizationEngine
from app.optimization.sensitivity import MAX_PROBES, ProbeCandidate, fixed_lp_duals, probe
from app.scenarios.apply import apply_changes
from app.services.optimization import probe_candidates
from tests.fixtures.builders import buyer, lot, make_payload, route
from tests.fixtures.runs import solve_context
from tests.fixtures.solver import cases

ENGINE = OptimizationEngine()


def _duals(case):
    c = case()
    out = ENGINE.run(c.payload, c.config)
    return fixed_lp_duals(ENGINE, c.payload, c.config, out.result)


def test_cbc_duals_on_a_known_continuous_lp() -> None:
    """max 3a + 2b  s.t.  a + b <= 4 (c1), a + 3b <= 6 (c2), a <= 3 (c3)  ->  a = 3, b = 1.
    All three constraints bind at this vertex (degenerate in 2D): the duals are not unique, but any
    valid dual vector is >= 0 and satisfies strong duality 4 y1 + 6 y2 + 3 y3 = 11."""
    p = LpProblem("known", LpMaximize)
    a, b = LpVariable("a", 0), LpVariable("b", 0)
    p += 3 * a + 2 * b
    p += (a + b <= 4, "c1")
    p += (a + 3 * b <= 6, "c2")
    p += (a <= 3, "c3")
    p.solve(PULP_CBC_CMD(msg=False))
    y = {n: c.pi for n, c in p.constraints.items()}
    assert (a.varValue, b.varValue) == (3, 1)
    assert 4 * y["c1"] + 6 * y["c2"] + 3 * y["c3"] == pytest.approx(11)
    assert all(v >= -1e-9 for v in y.values())


def test_cbc_duals_on_a_non_degenerate_lp() -> None:
    """max 3a + b  s.t.  a + b <= 4 (c1), a <= 6 (c2): a = 4, b = 0. pi(c1) = 3, pi(c2) = 0, dj(b) = -2."""
    p = LpProblem("nondegenerate", LpMaximize)
    a, b = LpVariable("a", 0), LpVariable("b", 0)
    p += 3 * a + b
    p += (a + b <= 4, "c1")
    p += (a <= 6, "c2")
    p.solve(PULP_CBC_CMD(msg=False))
    assert p.constraints["c1"].pi == pytest.approx(3)
    assert p.constraints["c2"].pi == pytest.approx(0)
    assert b.dj == pytest.approx(-2)


def test_storage_dual_is_price_minus_storage_cost() -> None:
    """storage_saturated: one more kg of capacity on day 0 sells at 2.0 on day 1 after 0.1 of storage."""
    report = _duals(cases.storage_saturated)
    assert report.available
    dual = report.by_key["storage_capacity|store|0"]
    assert dual.value == pytest.approx(1.9) and dual.reliable and dual.reason is None


def test_degenerate_binding_constraint_is_unreliable() -> None:
    """direct_sale: demand (800) and the 800 kg useful truck load bind together; CBC gives the whole
    value to the truck constraint, so the demand dual is 0 while binding -> degenerate."""
    report = _duals(cases.direct_sale)
    demand = report.by_key["demand_max|b1|"]
    assert demand.value == 0 and not demand.reliable and "degenerate" in (demand.reason or "")
    truck = report.by_key["trip_capacity|b1|0"]
    assert truck.value == pytest.approx(2.0) and not truck.reliable and "integer" in (truck.reason or "")


def test_dual_conditional_on_integer_choice_is_unreliable() -> None:
    """minimum_order: buyer A is not served (y = 0), so `sold <= 1000 y` reports the full price 3.0
    per kg although A can only be served with 800 kg: flagged unreliable."""
    report = _duals(cases.minimum_order)
    dual = report.by_key["demand_max|a|"]
    assert dual.value == pytest.approx(3.0) and not dual.reliable


def test_duals_are_attached_to_the_constraint_report() -> None:
    ctx = solve_context(cases.storage_saturated().payload, cases.storage_saturated().config)
    info = next(c for c in ctx.result.constraints if c.key == "storage_capacity|store|0")
    assert info.dual == pytest.approx(1.9) and info.dual_reliable is True
    assert ctx.sensitivity is not None and ctx.sensitivity.duals_available


def test_probe_one_more_truck_gives_the_expected_delta() -> None:
    """fleet_limiting: 2 trucks x 10 h, 5 h per trip -> 4 trips -> 4 000 kg sold at 1.0.
    A third truck allows 6 trips; only 1 000 kg remain -> +1 000 of profit, +1 trip, -1 000 kg lost."""
    c = cases.fleet_limiting()
    base = ENGINE.run(c.payload, c.config).result
    change = {"op": "vehicle_count", "target": "truck", "params": {"mode": "delta", "value": 1}}
    candidate = ProbeCandidate("+1 truck", change, apply_changes(c.payload, [parse_change(change)]).effective, "fleet_time|truck|")
    (result,) = probe(ENGINE, c.config, base, [candidate])
    assert result.outcome == SolverOutcome.OPTIMAL and result.significant
    assert result.delta_objective == pytest.approx(1000)
    assert result.delta_kpis["sold_kg"] == pytest.approx(1000)
    assert result.delta_kpis["lost_kg"] == pytest.approx(-1000)
    assert result.delta_kpis["trips"] == 1


def test_probe_within_gap_noise_is_not_significant() -> None:
    """Delta smaller than gap x |objective| (both plans only proven within the gap) is flagged."""
    payload = make_payload(lots=[lot("l1", 100_000)], buyers=[buyer("b1", price=1.0, demand=100_000)])
    config = RunConfig(gap=0.01)
    base = ENGINE.run(payload, config).result
    change = {"op": "buyer_price", "target": "b1", "params": {"mode": "delta", "value": 0.001}}
    candidate = ProbeCandidate("+0.001", change, apply_changes(payload, [parse_change(change)]).effective)
    (result,) = probe(ENGINE, config, base, [candidate])
    assert result.delta_objective == pytest.approx(100) and not result.significant  # 100 < 1 % x 100 000


def test_probe_candidates_follow_bottlenecks_and_are_deduplicated() -> None:
    """fleet_limiting: fleet_time binds -> one '+1 vehicle' probe (fleet_trips would map to the same change)."""
    ctx = solve_context(cases.fleet_limiting().payload)
    candidates = probe_candidates(ctx)
    assert [c.change for c in candidates] == [{"op": "vehicle_count", "target": "truck", "params": {"mode": "delta", "value": 1}}]
    assert candidates[0].constraint_key == "fleet_time|truck|"
    assert candidates[0].payload.vehicle_types[0].count == 3


def test_probe_candidates_include_shelf_life_when_stock_expired() -> None:
    """Expiry and harvest-day loss cost the same, so the waste kind is set by hand (as in the engine tests)."""
    c = cases.forced_expiry()
    result = ENGINE.run(c.payload, c.config).result
    expired = WasteRow(day=1, lot_id="l1", facility_id="store", kind="expired", kg=1000, value_lost=1000)
    ctx = RunContext.build("r", c.payload, c.config, result.model_copy(update={"waste": [expired]}))
    (candidate,) = [p for p in probe_candidates(ctx) if p.change["op"] == "shelf_life"]
    assert candidate.change["params"] == {"field": "ambient", "mode": "delta", "value": 1}
    assert candidate.payload.crops[0].shelf_life_ambient_days == 3


def test_probe_count_is_capped() -> None:
    buyers = [buyer(f"b{i}", price=1.0 + i / 10, demand=100) for i in range(12)]
    payload = make_payload(lots=[lot("l1", 5000)], buyers=buyers, routes=[route(b["id"]) for b in buyers])
    ctx = solve_context(payload)
    assert len(probe_candidates(ctx)) == MAX_PROBES


def test_weighted_runs_skip_duals() -> None:
    c = cases.weighted_accepts_costly_trip()
    ctx = solve_context(c.payload, c.config)
    assert ctx.sensitivity is not None and not ctx.sensitivity.duals_available
    assert all(info.dual is None for info in ctx.result.constraints)


def test_storage_probe_on_a_saturated_store() -> None:
    """storage_saturated + 1 000 kg of capacity: the 400 kg lost on day 0 can now be stored one night
    (0.1/kg) and sold at 2.0 on day 1 -> +760 (same single trip)."""
    c = cases.storage_saturated()
    base = ENGINE.run(c.payload, c.config).result
    change = {"op": "storage_capacity", "target": "store", "params": {"mode": "delta", "value": 1000}}
    candidate = ProbeCandidate("+1000 kg", change, apply_changes(c.payload, [parse_change(change)]).effective)
    (result,) = probe(ENGINE, c.config, base, [candidate])
    assert result.delta_objective == pytest.approx(400 * (2.0 - 0.1))


def test_unusable_probe_is_reported_not_raised() -> None:
    c = cases.direct_sale()
    base = ENGINE.run(c.payload, c.config).result
    bad = c.payload.model_copy(deep=True)
    bad.vehicle_types[0].count = 0  # NO_VEHICLE: blocking dataset error
    (result,) = probe(ENGINE, c.config, base, [ProbeCandidate("no truck", {"op": "vehicle_count"}, bad)])
    assert result.outcome == SolverOutcome.ERROR and result.delta_objective is None


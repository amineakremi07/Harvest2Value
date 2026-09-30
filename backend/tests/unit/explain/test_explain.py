"""Explainability: limiting factor per case (plan §15 order), bottlenecks, alternatives, trade-offs, builder."""

from __future__ import annotations

import pytest

from app.domain.explanation import LIMITING_ORDER
from app.domain.enums import SolverOutcome
from app.domain.results import ProbeResult, SensitivityReport
from app.explain.alternatives import best_alternative, tradeoffs
from app.explain.binding import bottlenecks, really_binding
from app.explain.builder import ExplanationBuilder
from app.explain.limiting import limiting_factor
from tests.fixtures.builders import buyer, lot, make_payload, route, vehicle
from tests.fixtures.runs import solve_context
from tests.fixtures.solver import cases


def code(ctx, buyer_id: str) -> str:
    return limiting_factor(ctx, buyer_id).code


def test_order_is_the_documented_one() -> None:
    assert LIMITING_ORDER == (
        "UNPROFITABLE", "DEMAND_CAP", "DAILY_DEMAND_CAP", "FLEET_TIME", "COLD_CHAIN", "SHELF_LIFE_WINDOW", "MOQ", "OPPORTUNITY",
    )


def test_unprofitable() -> None:
    """Price 1.0 x 1 000 kg against a 1 100 trip: net price -0.1/kg, the buyer is not served."""
    c = cases.profit_refuses_costly_trip()
    factor = limiting_factor(solve_context(c.payload, c.config), "x")
    assert factor.code == "UNPROFITABLE" and factor.evidence["net_price_per_kg"] == pytest.approx(-0.1)


def test_demand_cap() -> None:
    factor = limiting_factor(solve_context(cases.direct_sale().payload), "b1")
    assert factor.code == "DEMAND_CAP" and factor.evidence == {"sold_kg": 800, "max_demand_kg": 800}
    assert factor.constraint_keys == ["demand_max|b1|"]


def test_daily_demand_cap() -> None:
    """300 kg per day at most, shelf life 1 day, no storage: 300 sold on day 0, 700 lost."""
    payload = make_payload(lots=[lot("l1", 1000)], buyers=[buyer("b1", max_per_day_kg=300)])
    factor = limiting_factor(solve_context(payload), "b1")
    assert factor.code == "DAILY_DEMAND_CAP" and factor.evidence["days"] == [0]


def test_fleet_time() -> None:
    factor = limiting_factor(solve_context(cases.fleet_limiting().payload), "b1")
    assert factor.code == "FLEET_TIME" and factor.evidence["remaining_demand_kg"] == 6000
    assert all(k.startswith("fleet_time|truck|") for k in factor.constraint_keys)


def test_cold_chain() -> None:
    payload = make_payload(lots=[lot("l1", 1000)], buyers=[buyer("cold", requires_cold_chain=True), buyer("b2", demand=500)])
    factor = limiting_factor(solve_context(payload), "cold")
    assert factor.code == "COLD_CHAIN" and factor.evidence["requires_cold_chain"] is True


def test_trip_too_long_is_reported_as_no_compatible_vehicle() -> None:
    payload = make_payload(
        lots=[lot("l1", 1000)],
        buyers=[buyer("far"), buyer("near", demand=500)],
        vehicles=[vehicle(hours_per_day=10, avg_speed_kmh=50)],
        routes=[route("far", distance=400), route("near", distance=10)],
    )
    factor = limiting_factor(solve_context(payload), "far")
    assert factor.code == "COLD_CHAIN" and "longer than a working day" in factor.message


def test_shelf_life_window() -> None:
    c = cases.forced_expiry()
    factor = limiting_factor(solve_context(c.payload, c.config), "b1")
    assert factor.code == "SHELF_LIFE_WINDOW" and factor.evidence["delivery_window"] == [3, 5]


def test_moq_and_not_a_fake_demand_cap() -> None:
    """Buyer A (MOQ 800) is not served: `sold <= 1000 y` reads 0 = 0 (tight on paper) but is not a cap."""
    ctx = solve_context(cases.minimum_order().payload)
    assert code(ctx, "a") == "MOQ"
    fake = next(c for c in ctx.result.constraints if c.key == "demand_max|a|")
    assert fake.binding and not really_binding(fake, ctx)


def test_opportunity_when_the_harvest_is_exhausted() -> None:
    payload = make_payload(lots=[lot("l1", 1000)], buyers=[buyer("a", price=2.0, demand=600), buyer("b", price=1.0)])
    factor = limiting_factor(solve_context(payload), "b")
    assert factor.code == "OPPORTUNITY" and factor.evidence["harvest_exhausted"] is True


def test_first_matching_factor_wins() -> None:
    """Unprofitable buyer that also has an MOQ: UNPROFITABLE comes first."""
    payload = make_payload(
        lots=[lot("l1", 1000)],
        buyers=[buyer("x", price=1.0, demand=1000, min_order_kg=500), buyer("y", price=0.5, demand=1000)],
        vehicles=[vehicle(capacity=1000, fixed_cost_per_trip=1100)],
    )
    assert code(solve_context(payload), "x") == "UNPROFITABLE"


def test_bottlenecks_are_grouped_by_entity_and_ranked_by_probe_gain() -> None:
    """Two buyers each limited by their maximum demand; the probe with the larger gain ranks first."""
    payload = make_payload(lots=[lot("l1", 5000)], buyers=[buyer("a", price=2.0, demand=1000), buyer("b", price=3.0, demand=1000)])
    probes = [
        ProbeResult(constraint_key="demand_max|a|", label="a", change={}, outcome=SolverOutcome.OPTIMAL, objective_value=1, delta_objective=200, significant=True),
        ProbeResult(constraint_key="demand_max|b|", label="b", change={}, outcome=SolverOutcome.OPTIMAL, objective_value=1, delta_objective=300, significant=True),
    ]
    ctx = solve_context(payload, sensitivity=SensitivityReport(probes=probes, probes_computed=True))
    ranked = bottlenecks(ctx)
    assert [(b.key, b.rank, b.probe_gain) for b in ranked] == [("demand_max|b|", 1, 300), ("demand_max|a|", 2, 200)]
    assert ranked[0].suggested_change == {
        "op": "buyer_demand", "target": "b", "params": {"field": "max_demand_kg", "mode": "relative_pct", "value": 10},
    }


def test_insignificant_probe_does_not_rank() -> None:
    payload = make_payload(lots=[lot("l1", 5000)], buyers=[buyer("a", price=2.0, demand=1000)])
    probe = ProbeResult(constraint_key="demand_max|a|", label="a", change={}, outcome=SolverOutcome.OPTIMAL, objective_value=1, delta_objective=5, significant=False)
    ctx = solve_context(payload, sensitivity=SensitivityReport(probes=[probe], probes_computed=True))
    assert bottlenecks(ctx)[0].probe_gain is None


def test_fleet_bottleneck_groups_days() -> None:
    ranked = bottlenecks(solve_context(cases.fleet_limiting().payload))
    assert ranked[0].key == "fleet_time|truck|" and ranked[0].binding_days == [0]
    assert ranked[0].suggested_label == "+1 vehicle of type Truck"


def test_alternative_compares_net_prices() -> None:
    """A (2.0, 600 kg) is full; B (1.0) has demand left: sending A's kg to B loses 1.0 per kg."""
    payload = make_payload(lots=[lot("l1", 1000)], buyers=[buyer("a", price=2.0, demand=600), buyer("b", price=1.0, demand=5000)])
    ctx = solve_context(payload)
    alt = best_alternative(ctx, "a")
    assert alt is not None and alt.buyer_id == "b" and alt.difference_per_kg == pytest.approx(-1.0)


def test_tradeoffs_between_buyers_sharing_a_binding_fleet() -> None:
    """One truck-day (10 h) = 5 round trips of 2 h. A takes 2 trips (its 2 000 kg), B the other 3:
    both are served on day 0 and the fleet binds."""
    payload = make_payload(
        lots=[lot("l1", 10000)],
        buyers=[buyer("a", price=2.0, demand=2000), buyer("b", price=1.9, demand=5000)],
        vehicles=[vehicle(capacity=1000, count=1, hours_per_day=10, avg_speed_kmh=50, loading_hours_per_trip=0)],
        routes=[route("a", distance=50), route("b", distance=50)],
    )
    ctx = solve_context(payload)
    found = tradeoffs(ctx)
    assert found and found[0].buyer_ids == ["a", "b"] and found[0].constraint_key == "fleet_time|truck|"


def test_builder_produces_cards_for_buyers_storage_and_losses() -> None:
    c = cases.storage_saturated()
    explanation = ExplanationBuilder().build(solve_context(c.payload, c.config))
    kinds = [(d.kind, d.entity_id) for d in explanation.decisions]
    assert kinds == [("buyer", "b1"), ("storage", "store"), ("waste", "waste")]
    storage_card = explanation.decisions[1]
    assert storage_card.limiting_factor is not None and storage_card.limiting_factor.code == "STORAGE_CAP"
    assert [(m.kind, m.delta_objective) for m in storage_card.marginal_values] == [("dual", pytest.approx(1.9))]
    assert explanation.decisions[2].metrics["lost_kg"] == 400
    assert not explanation.sensitivity_computed
    assert all(b.binding for b in explanation.binding)


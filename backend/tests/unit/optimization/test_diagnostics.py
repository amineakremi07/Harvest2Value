"""Infeasibility diagnostics: the elastic relaxation names the right conflict and the missing amount."""

from __future__ import annotations

import pytest

from app.domain.enums import ObjectiveKind, SolverOutcome
from app.domain.run_config import RunConfig
from app.optimization.diagnostics import elastic_infeasibility
from app.optimization.engine import OptimizationEngine
from tests.fixtures.builders import buyer, crop, lot, make_payload, route, vehicle
from tests.fixtures.solver.cases import min_contract_infeasible

ENGINE = OptimizationEngine()


def conflicts(payload, config=None) -> dict[str, float]:
    config = config or RunConfig()
    assert ENGINE.run(payload, config).outcome == SolverOutcome.INFEASIBLE
    return {c.key: c.relaxation_needed for c in elastic_infeasibility(payload, config).conflicts}


def test_contract_above_harvest() -> None:
    """2 000 kg contracted, 1 000 kg harvested: the contract is 1 000 kg short."""
    case = min_contract_infeasible()
    diagnostics = elastic_infeasibility(case.payload, case.config)
    assert [(c.key, c.relaxation_needed, c.unit) for c in diagnostics.conflicts] == [("demand_min|b1|", 1000.0, "kg")]
    assert diagnostics.method == "elastic"
    assert diagnostics.suggestions[0].startswith("Lower the contracted minimum of B1 by 1,000 kg")


def test_contract_above_fleet_capacity_names_the_fleet_limit() -> None:
    """Fleet: 2 trucks x 10 h, 5 h per trip -> 4 000 kg deliverable; contract 4 500 -> 500 kg short,
    and the driving-hours limit is reported as the capacity reached."""
    payload = make_payload(
        lots=[lot("l1", 5000)],
        buyers=[buyer("b1", demand=10000, min_contract_kg=4500)],
        vehicles=[vehicle(capacity=1000, count=2, hours_per_day=10, avg_speed_kmh=50, loading_hours_per_trip=1)],
        routes=[route("b1", distance=100)],
    )
    config = RunConfig()
    assert conflicts(payload, config) == {"demand_min|b1|": 500.0}
    suggestions = elastic_infeasibility(payload, config).suggestions
    assert any("Driving hours of the Truck fleet" in s for s in suggestions)


def test_contract_with_an_unreachable_buyer_points_at_the_cold_chain() -> None:
    payload = make_payload(
        lots=[lot("l1", 1000)],
        buyers=[buyer("b1", min_contract_kg=100, requires_cold_chain=True), buyer("b2")],
    )
    assert conflicts(payload) == {"demand_min|b1|": 100.0}
    assert any("Cold chain: Truck cannot deliver to B1" in s for s in elastic_infeasibility(payload, RunConfig()).suggestions)


def test_constraint_without_any_decision_is_reported_directly() -> None:
    """Lot sellable on day 0 only (shelf life 1, no storage), buyer receives from day 2: its contract
    minimum has no sale variable at all (trivially infeasible, never sent to CBC)."""
    payload = make_payload(
        lots=[lot("l1", 1000)],
        buyers=[buyer("b1", min_contract_kg=100, window_start_day=2), buyer("b2")],
    )
    config = RunConfig(horizon_days=5)
    diagnostics = elastic_infeasibility(payload, config)
    assert [(c.key, c.relaxation_needed) for c in diagnostics.conflicts] == [("demand_min|b1|", 100.0)]
    assert "can never be met" in diagnostics.suggestions[0]


def test_service_level_in_cost_mode() -> None:
    """Cost mode must sell 90 % of 1 000 kg but the only buyer takes 600 kg: 300 kg short."""
    payload = make_payload(lots=[lot("l1", 1000)], buyers=[buyer("b1", demand=600)])
    config = RunConfig(objective=ObjectiveKind.COST, service_level_min=0.9)
    assert conflicts(payload, config) == {"service_level||": pytest.approx(300.0)}


def test_profit_floor_in_waste_mode() -> None:
    """Waste mode with a profit floor of 5 000 when at most 1 000 x 2.0 = 2 000 can be earned."""
    payload = make_payload(lots=[lot("l1", 1000)], buyers=[buyer("b1", price=2.0)], crops=[crop()])
    config = RunConfig(objective=ObjectiveKind.WASTE, min_profit=5000)
    assert conflicts(payload, config) == {"min_profit||": pytest.approx(3000.0)}

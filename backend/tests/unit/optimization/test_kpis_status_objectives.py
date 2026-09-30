"""KPI formulas (§11), solver status mapping, objective helpers."""

import pytest

from app.analytics.kpis import KpiInputs, compute_kpis
from app.domain.enums import SolverOutcome
from app.domain.results import Kpis
from app.optimization.objectives import CriterionBounds, ideal_points
from app.optimization.runner import map_status


def inputs(**kw) -> KpiInputs:
    base = dict(
        harvest_kg=1000,
        sold_kg=700,
        realized_revenue=1400,
        transport_cost=100,
        storage_cost=50,
        disposal_cost=10,
        ending_inventory_kg=200,
        salvage_value_per_kg=0.5,
        lost_kg=100,
        reference_price_per_kg=2.0,
        stored_kg=400,
        inventory_kg_days=1200,
        trips=2,
        trip_capacity_kg=1000,
        fleet_hours_used=6,
        fleet_hours_available=24,
        storage_occupancy=[(400, 500), (100, 500)],
        buyer_sold={"a": 500, "b": 200},
        buyer_net_revenue={"a": 900, "b": 400},
        buyer_max_demand={"a": 500, "b": 500, "c": 400},
        objective_value=1340.0,
    )
    base.update(kw)
    return KpiInputs(**base)


def test_kpi_formulas() -> None:
    k = compute_kpis(inputs())
    assert k.total_cost == 160
    assert k.realized_profit == 1240  # 1 400 - 160
    assert k.margin_pct == pytest.approx(88.57)
    assert k.ending_inventory_value == 100  # 200 x 0.5
    assert k.economic_value == 1340  # profit + inventory value
    assert k.lost_value == 200 and k.waste_rate_pct == 10 and k.sold_rate_pct == 70 and k.storage_rate_pct == 40
    assert k.fulfillment_rate_pct == pytest.approx(700 / 1400 * 100)
    assert k.vehicle_utilization_pct == 25 and k.load_factor_pct == 70
    assert (k.storage_utilization_peak_pct, k.storage_utilization_avg_pct) == (80, 50)
    assert k.avg_transport_cost_per_kg == pytest.approx(0.1429, abs=1e-4)
    assert k.avg_storage_days == 3  # 1 200 kg-days / 400 kg
    assert k.best_buyer_id == "a"


def test_undefined_ratios_are_none() -> None:
    k = compute_kpis(inputs(sold_kg=0, realized_revenue=0, stored_kg=0, trip_capacity_kg=0, fleet_hours_available=None, storage_occupancy=[], buyer_sold={}, buyer_net_revenue={}))
    assert k.margin_pct is None and k.avg_transport_cost_per_kg is None and k.avg_storage_days is None
    assert k.load_factor_pct is None and k.vehicle_utilization_pct is None and k.storage_utilization_peak_pct is None
    assert k.best_buyer_id is None


def test_r2_there_is_no_net_profit() -> None:
    assert "net_profit" not in Kpis.model_fields
    assert "valeur économique" in (Kpis.model_fields["economic_value"].description or "").lower()


@pytest.mark.parametrize(
    ("status", "sol_status", "outcome"),
    [
        (1, 1, SolverOutcome.OPTIMAL),
        (1, 2, SolverOutcome.FEASIBLE),  # time limit reached with a solution
        (0, 0, SolverOutcome.NOT_SOLVED),  # time limit reached without a solution
        (-1, -1, SolverOutcome.INFEASIBLE),
        (-2, -2, SolverOutcome.UNBOUNDED),
        (-3, -3, SolverOutcome.ERROR),
    ],
)
def test_status_mapping(status: int, sol_status: int, outcome: SolverOutcome) -> None:
    assert map_status(status, sol_status) == outcome
    assert outcome.has_solution == (outcome in (SolverOutcome.OPTIMAL, SolverOutcome.FEASIBLE))


def test_ideal_points_from_payoff_table() -> None:
    payoff = {"profit": {"profit": 0.0, "waste": 1000.0}, "waste": {"profit": -100.0, "waste": 0.0}}
    assert ideal_points(payoff) == {
        "profit": CriterionBounds(ideal=0.0, nadir=-100.0),
        "waste": CriterionBounds(ideal=0.0, nadir=1000.0),
    }

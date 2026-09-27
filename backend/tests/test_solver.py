import pytest

from app.engines.solver import solve_optimization
from app.models.schemas import OptimizeRequest, OptimizeResponse


def _optimize_request(
    harvest_kg: float,
    storage_capacity_kg: float,
    buyer_demand_kg: float,
    vehicle_capacity_kg: float,
) -> OptimizeRequest:
    return OptimizeRequest(
        producer={
            "id": "farm-1",
            "name": "Test Farm",
            "region": "Central",
            "country": "Tunisia",
            "harvest_kg": harvest_kg,
            "storage_capacity_kg": storage_capacity_kg,
            "storage_cost_per_kg_per_day": 0.05,
            "shelf_life_days": 5,
        },
        buyers=[
            {
                "id": "buyer-1",
                "name": "Local Market",
                "location": "Tunis",
                "max_demand_kg": buyer_demand_kg,
                "price_per_kg": 10.0,
                "distance_km": 2.0,
                "transport_cost_per_kg_per_km": 0.1,
            }
        ],
        crop={"name": "Olives", "type": "durable", "unit": "kg"},
        logistics={
            "available_vehicles": 1,
            "vehicle_capacity_kg": vehicle_capacity_kg,
        },
    )


def test_solve_harvest_success() -> None:
    request = _optimize_request(
        harvest_kg=100,
        storage_capacity_kg=20,
        buyer_demand_kg=100,
        vehicle_capacity_kg=100,
    )

    result = solve_optimization(request.model_dump())
    response = OptimizeResponse.model_validate(result)

    assert response.status == "Optimal"
    assert response.allocated_kg == sum(
        allocation.allocated_kg for allocation in response.allocation.values()
    )
    assert 0 < response.allocation["buyer-1"].allocated_kg <= 100
    assert (
        response.allocated_kg + response.stored_kg + response.wasted_kg
        == response.total_harvest_kg
    )
    assert response.net_profit > 0
    expected_profit = (
        response.allocation["buyer-1"].allocated_kg * (10.0 - 2.0 * 0.1)
        + response.stored_kg * (10.0 - 0.05)
        - response.wasted_kg * 5.0
    )
    assert response.net_profit == pytest.approx(expected_profit, abs=0.01)


def test_solve_harvest_storage_saturated() -> None:
    request = _optimize_request(
        harvest_kg=100,
        storage_capacity_kg=10,
        buyer_demand_kg=1,
        vehicle_capacity_kg=1,
    )

    response = OptimizeResponse.model_validate(
        solve_optimization(request.model_dump())
    )

    assert response.status == "Optimal"
    assert response.stored_kg == 10
    assert response.stored_kg <= request.producer.storage_capacity_kg
    assert response.allocated_kg <= request.logistics.vehicle_capacity_kg
    assert (
        response.allocated_kg + response.stored_kg + response.wasted_kg
        == response.total_harvest_kg
    )

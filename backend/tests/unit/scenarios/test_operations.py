"""Scenario operations (plan §12): every op in absolute / relative_pct / delta mode, bounds and errors;
order and conflicts; lineage."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import pytest
from pydantic import ValidationError

from app.core.errors import ScenarioApplyError, ValidationFailed
from app.domain.dataset import DatasetPayload
from app.domain.scenario import CHANGE_TYPES, parse_change
from app.scenarios.apply import ChangeRef, apply_changes
from app.scenarios.lineage import resolve_chain
from app.scenarios.operations import OPERATIONS, compute
from tests.fixtures.builders import buyer, crop, lot, make_payload, storage, vehicle


def base() -> DatasetPayload:
    return make_payload(
        lots=[lot("l1", 1000), lot("l2", 500, day=2)],
        buyers=[
            buyer("b1", price=1.2, demand=800, max_per_day_kg=400, min_contract_kg=100, price_schedule=[{"day": 3, "price": 1.5}]),
            buyer("b2", price=2.0, demand=600),
        ],
        crops=[crop(shelf_life_ambient_days=5, shelf_life_cold_days=10)],
        storage_facilities=[storage("s1", capacity=2000, cost=0.1), storage("s2", capacity=500, cost=0.2, refrigerated=True)],
        vehicles=[vehicle("t1", capacity=1000, count=2, cost_per_km=0.5, fixed_cost_per_trip=20)],
    )


def apply(*changes: dict[str, Any], payload: DatasetPayload | None = None) -> DatasetPayload:
    return apply_changes(payload or base(), [parse_change(c) for c in changes]).effective


def fails(*changes: dict[str, Any]) -> dict[str, Any]:
    with pytest.raises(ScenarioApplyError) as info:
        apply(*changes)
    assert info.value.status == 422 and info.value.code == "SCENARIO_APPLY_ERROR"
    return info.value.details


def num(mode: str, value: float, **extra: Any) -> dict[str, Any]:
    return {"mode": mode, "value": value, **extra}


def test_registry_covers_every_change_type() -> None:
    assert set(OPERATIONS) == set(CHANGE_TYPES) and len(OPERATIONS) == 16


@pytest.mark.parametrize(
    ("old", "mode", "value", "expected"),
    [(100, "absolute", 80, 80), (100, "relative_pct", -10, 90), (100, "delta", -25, 75), (1.2, "relative_pct", -10, 1.08)],
)
def test_compute(old: float, mode: str, value: float, expected: float) -> None:
    assert compute(old, mode, value, field="f") == expected


# ---- buyer_price ----

def test_buyer_price_r7_minus_ten_percent_is_computed_by_the_backend() -> None:
    """R7: '-10 %' is sent as relative_pct -10; the backend computes 1.2 -> 1.08 (and the schedule)."""
    p = apply({"op": "buyer_price", "target": "b1", "params": num("relative_pct", -10)})
    assert p.buyers[0].price_per_kg == 1.08 and p.buyers[0].price_schedule[0].price == 1.35
    assert p.buyers[1].price_per_kg == 2.0


def test_buyer_price_all_buyers_absolute_and_delta() -> None:
    p = apply({"op": "buyer_price", "target": "*", "params": num("absolute", 3)})
    assert [b.price_per_kg for b in p.buyers] == [3, 3] and p.buyers[0].price_schedule[0].price == 3
    p = apply({"op": "buyer_price", "target": "b2", "params": num("delta", -0.5)})
    assert p.buyers[1].price_per_kg == 1.5


def test_buyer_price_cannot_become_negative() -> None:
    details = fails({"op": "buyer_price", "target": "b1", "params": num("delta", -2)})
    assert details["change_index"] == 0 and "must be >= 0" in details["reason"]


# ---- buyer_demand ----

def test_buyer_demand_fields() -> None:
    p = apply({"op": "buyer_demand", "target": "*", "params": num("relative_pct", 20, field="max_demand_kg")})
    assert [b.max_demand_kg for b in p.buyers] == [960, 720]
    p = apply({"op": "buyer_demand", "target": "b1", "params": num("delta", 100, field="max_per_day_kg")})
    assert p.buyers[0].max_per_day_kg == 500
    p = apply({"op": "buyer_demand", "target": "b2", "params": num("absolute", 50, field="min_contract_kg")})
    assert p.buyers[1].min_contract_kg == 50


def test_buyer_demand_bounds() -> None:
    assert "must be > 0" in fails({"op": "buyer_demand", "target": "b1", "params": num("absolute", 0, field="max_demand_kg")})["reason"]
    assert "above max_demand_kg" in fails({"op": "buyer_demand", "target": "b1", "params": num("absolute", 900, field="min_contract_kg")})["reason"]
    assert "below the buyer's minimum" in fails({"op": "buyer_demand", "target": "b1", "params": num("absolute", 50, field="max_demand_kg")})["reason"]
    assert "use mode 'absolute'" in fails({"op": "buyer_demand", "target": "b2", "params": num("relative_pct", 10, field="max_per_day_kg")})["reason"]


# ---- harvest ----

def test_harvest_quantity() -> None:
    p = apply({"op": "harvest_quantity", "target": "*", "params": num("relative_pct", 20)})
    assert [h.quantity_kg for h in p.harvest_lots] == [1200, 600]
    assert "must be > 0" in fails({"op": "harvest_quantity", "target": "l2", "params": num("delta", -500)})["reason"]


def test_harvest_timing() -> None:
    p = apply({"op": "harvest_timing", "target": "l2", "params": {"shift_days": 3}})
    assert p.harvest_lots[1].available_day == 5
    assert "must be >= 0" in fails({"op": "harvest_timing", "target": "l1", "params": {"shift_days": -1}})["reason"]


# ---- storage ----

def test_storage_capacity_and_cost() -> None:
    p = apply(
        {"op": "storage_capacity", "target": "s1", "params": num("delta", -1000)},
        {"op": "storage_cost", "target": "*", "params": num("relative_pct", 50)},
    )
    assert p.storage_facilities[0].capacity_kg == 1000
    assert [s.cost_per_kg_per_day for s in p.storage_facilities] == [0.15, 0.3]
    assert "must be >= 0" in fails({"op": "storage_capacity", "target": "s2", "params": num("delta", -501)})["reason"]


def test_add_and_remove_storage() -> None:
    facility = {"id": "s3", "name": "New cold room", "capacity_kg": 2000, "refrigerated": True, "cost_per_kg_per_day": 0.3}
    p = apply({"op": "add_storage", "params": {"facility": facility}}, {"op": "remove_storage", "target": "s1"})
    assert [s.id for s in p.storage_facilities] == ["s2", "s3"]
    assert "already exists" in fails({"op": "add_storage", "params": {"facility": {**facility, "id": "s1"}}})["reason"]


# ---- vehicles ----

def test_transport_cost_is_the_fuel_proxy() -> None:
    p = apply({"op": "transport_cost", "target": "*", "params": num("relative_pct", 15, field="cost_per_km")})
    assert p.vehicle_types[0].cost_per_km == 0.575 and p.vehicle_types[0].fixed_cost_per_trip == 20
    p = apply({"op": "transport_cost", "target": "t1", "params": num("absolute", 0, field="fixed_cost_per_trip")})
    assert p.vehicle_types[0].fixed_cost_per_trip == 0


def test_vehicle_count_and_capacity() -> None:
    p = apply({"op": "vehicle_count", "target": "t1", "params": {"mode": "delta", "value": -1}})
    assert p.vehicle_types[0].count == 1
    assert "must be >= 0" in fails({"op": "vehicle_count", "target": "t1", "params": {"mode": "delta", "value": -3}})["reason"]
    p = apply({"op": "vehicle_capacity", "target": "t1", "params": num("relative_pct", 50)})
    assert p.vehicle_types[0].capacity_kg == 1500
    assert "must be > 0" in fails({"op": "vehicle_capacity", "target": "t1", "params": num("absolute", 0)})["reason"]


def test_vehicle_count_rejects_percentages() -> None:
    with pytest.raises(ValidationError):
        parse_change({"op": "vehicle_count", "target": "t1", "params": {"mode": "relative_pct", "value": 10}})


# ---- shelf life ----

def test_shelf_life() -> None:
    p = apply({"op": "shelf_life", "target": "c", "params": num("delta", -2, field="ambient")})
    assert p.crops[0].shelf_life_ambient_days == 3
    p = apply({"op": "shelf_life", "target": "c", "params": num("relative_pct", 15, field="cold")})
    assert p.crops[0].shelf_life_cold_days == 12  # 11.5 rounded to whole days
    assert "shorter than ambient" in fails({"op": "shelf_life", "target": "c", "params": num("absolute", 11, field="ambient")})["reason"]
    assert "must be >= 1" in fails({"op": "shelf_life", "target": "c", "params": num("absolute", 0, field="ambient")})["reason"]


# ---- buyers ----

NEW_BUYER = {"id": "b3", "name": "Sousse", "location": "Sousse", "crop_ids": ["c"], "price_per_kg": 1.8, "max_demand_kg": 300}
NEW_ROUTE = {"buyer_id": "b3", "distance_km": 140, "road_condition": "good"}


def test_add_buyer_with_route() -> None:
    p = apply({"op": "add_buyer", "params": {"buyer": NEW_BUYER, "route": NEW_ROUTE}})
    assert p.buyers[-1].id == "b3" and p.route_for("b3").distance_km == 140


def test_add_buyer_errors() -> None:
    assert "already exists" in fails({"op": "add_buyer", "params": {"buyer": {**NEW_BUYER, "id": "b1"}, "route": {**NEW_ROUTE, "buyer_id": "b1"}}})["reason"]
    assert "unknown crop" in fails({"op": "add_buyer", "params": {"buyer": {**NEW_BUYER, "crop_ids": ["dates"]}, "route": NEW_ROUTE}})["reason"]
    with pytest.raises(ValidationError):
        parse_change({"op": "add_buyer", "params": {"buyer": NEW_BUYER, "route": {**NEW_ROUTE, "buyer_id": "x"}}})


def test_remove_buyer_removes_its_route() -> None:
    p = apply({"op": "remove_buyer", "target": "b2"})
    assert [b.id for b in p.buyers] == ["b1"] and [r.buyer_id for r in p.routes] == ["b1"]


def test_removing_the_last_buyer_is_rejected() -> None:
    details = fails({"op": "remove_buyer", "target": "b2"}, {"op": "remove_buyer", "target": "b1"})
    assert details["change_index"] == 1 and details["reason"] == "at least one buyer must remain"


# ---- route / cold chain ----

def test_route_fields() -> None:
    p = apply(
        {"op": "route", "target": "b1", "params": {"field": "road_condition", "value": "poor"}},
        {"op": "route", "target": "b1", "params": {"field": "distance_km", "mode": "relative_pct", "value": 50}},
        {"op": "route", "target": "b2", "params": {"field": "toll_per_trip", "mode": "delta", "value": 12}},
    )
    route_b1 = p.route_for("b1")
    assert route_b1.road_condition == "poor" and route_b1.distance_km == 0 and p.route_for("b2").toll_per_trip == 12
    with pytest.raises(ValidationError):
        parse_change({"op": "route", "target": "b1", "params": {"field": "distance_km", "value": "poor"}})


def test_cold_chain_for_a_buyer_or_a_crop() -> None:
    p = apply({"op": "cold_chain", "target": "b1", "params": {"required": True}})
    assert p.buyers[0].requires_cold_chain is True
    p = apply({"op": "cold_chain", "target": "c", "params": {"required": True, "entity": "crop"}})
    assert p.crops[0].requires_cold_chain is True


# ---- targets, order, conflicts ----

def test_target_shapes() -> None:
    with pytest.raises(ValidationError):
        parse_change({"op": "remove_buyer", "target": "*"})
    with pytest.raises(ValidationError):
        parse_change({"op": "buyer_price", "params": num("delta", 1)})
    assert "does not exist" in fails({"op": "buyer_price", "target": "nobody", "params": num("delta", 1)})["reason"]


def test_changes_apply_in_order() -> None:
    """+10 % then +1 differs from +1 then +10 %."""
    a = apply({"op": "buyer_price", "target": "b2", "params": num("relative_pct", 10)}, {"op": "buyer_price", "target": "b2", "params": num("delta", 1)})
    b = apply({"op": "buyer_price", "target": "b2", "params": num("delta", 1)}, {"op": "buyer_price", "target": "b2", "params": num("relative_pct", 10)})
    assert (a.buyers[1].price_per_kg, b.buyers[1].price_per_kg) == (3.2, 3.3)


def test_change_on_an_entity_removed_earlier_is_a_conflict() -> None:
    details = fails({"op": "remove_buyer", "target": "b2"}, {"op": "buyer_price", "target": "b2", "params": num("delta", 1)})
    assert details["change_index"] == 1 and "removed by an earlier change" in details["reason"]


def test_disabled_changes_are_skipped_and_applied_changes_are_reported() -> None:
    changes = [
        parse_change({"op": "buyer_price", "target": "b1", "params": num("delta", 1), "enabled": False}),
        parse_change({"op": "vehicle_count", "target": "t1", "params": {"mode": "delta", "value": 1}}),
    ]
    result = apply_changes(base(), changes)
    assert result.effective.buyers[0].price_per_kg == 1.2
    assert [(a.index, a.op, a.summary) for a in result.applied] == [(1, "vehicle_count", "count t1: 2 -> 3")]
    assert [d.path for d in result.diff] == ["vehicle_types[t1].count"]


def test_errors_name_the_scenario_and_change() -> None:
    ref = ChangeRef(parse_change({"op": "remove_storage", "target": "zz"}), scenario_id="s-1", change_id="c-9")
    with pytest.raises(ScenarioApplyError) as info:
        apply_changes(base(), [ref])
    assert info.value.details["scenario_id"] == "s-1" and info.value.details["change_id"] == "c-9"


def test_base_payload_is_never_mutated() -> None:
    payload = base()
    before = payload.model_dump()
    apply({"op": "remove_buyer", "target": "b2"}, payload=payload)
    assert payload.model_dump() == before


# ---- lineage ----

@dataclass
class Node:
    id: str
    parent_id: str | None


def test_lineage_is_root_first() -> None:
    nodes = {"a": Node("a", None), "b": Node("b", "a"), "c": Node("c", "b")}
    assert [n.id for n in resolve_chain(nodes["c"], nodes.get)] == ["a", "b", "c"]


def test_lineage_rejects_cycles() -> None:
    nodes = {"a": Node("a", "b"), "b": Node("b", "a")}
    with pytest.raises(ValidationFailed):
        resolve_chain(nodes["a"], nodes.get)

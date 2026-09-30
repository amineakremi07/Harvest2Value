"""Structural rules of the v2 dataset schema."""

import json
import re

import pytest
from pydantic import ValidationError

from app.domain.dataset import DatasetPayload, trip_cost, trip_hours
from tests.fixtures.builders import buyer, crop, lot, make_payload, payload_dict, route, storage, vehicle


def base(**kw):
    return payload_dict(lots=[lot("l1", 1000)], buyers=[buyer("b1")], **kw)


def test_minimal_payload_is_valid() -> None:
    p = DatasetPayload.model_validate(base())
    assert p.schema_version == "2.0" and p.route_for("b1").distance_km == 0


def test_json_round_trip_is_lossless() -> None:
    p = make_payload(
        lots=[lot("l1", 1000, day=2)],
        buyers=[buyer("b1", price_schedule=[{"day": 3, "price": 2.5}], window_start_day=1)],
        storage_facilities=[storage(refrigerated=True, cost=0.02)],
        crops=[crop(shelf_life_cold_days=5, loss_rate_pct_per_day_cold=0.5)],
    )
    again = DatasetPayload.model_validate_json(p.model_dump_json())
    assert again == p
    assert json.loads(again.model_dump_json()) == json.loads(p.model_dump_json())


@pytest.mark.parametrize(
    ("mutate", "message"),
    [
        (lambda d: d["buyers"].append(buyer("b1")), "buyers: duplicate id(s) ['b1']"),
        (lambda d: d["harvest_lots"].append(lot("l1", 5)), "harvest_lots: duplicate id(s) ['l1']"),
        (lambda d: d["harvest_lots"].append(lot("l2", 5, crop_id="ghost")), "unknown crop_id 'ghost'"),
        (lambda d: d["buyers"][0].update(crop_ids=["ghost"]), "unknown crop_ids ['ghost']"),
        (lambda d: d["routes"].append(route("nobody")), "unknown buyer_id(s) ['nobody']"),
        (lambda d: d["routes"].append(route("b1")), "more than one route for buyer(s) ['b1']"),
        (lambda d: d["routes"].clear() or d["routes"].append(route("b1")) or d["buyers"].append(buyer("b2")), "missing route for buyer(s) ['b2']"),
    ],
)
def test_cross_reference_errors(mutate, message: str) -> None:
    data = base()
    mutate(data)
    with pytest.raises(ValidationError, match=re.escape(message)):
        DatasetPayload.model_validate(data)


@pytest.mark.parametrize(
    ("section", "index", "field", "value"),
    [
        ("harvest_lots", 0, "quantity_kg", -5),
        ("harvest_lots", 0, "quantity_kg", 0),
        ("buyers", 0, "price_per_kg", -1),
        ("buyers", 0, "max_demand_kg", 0),
        ("crops", 0, "shelf_life_ambient_days", 0),
        ("crops", 0, "quality_decay_pct_per_day", 120),
        ("vehicle_types", 0, "capacity_kg", 0),
        ("vehicle_types", 0, "count", -1),
        ("routes", 0, "distance_km", -3),
        ("buyers", 0, "price_per_kg", float("nan")),
        ("buyers", 0, "id", "bad id!"),
    ],
)
def test_invalid_values(section: str, index: int, field: str, value) -> None:
    data = base()
    data[section][index][field] = value
    with pytest.raises(ValidationError):
        DatasetPayload.model_validate(data)


def test_unknown_fields_are_rejected() -> None:
    data = base()
    data["buyers"][0]["discount"] = 3
    with pytest.raises(ValidationError, match="Extra inputs are not permitted"):
        DatasetPayload.model_validate(data)


@pytest.mark.parametrize(
    "buyer_kw",
    [
        {"min_contract_kg": 5000, "demand": 1000},
        {"min_order_kg": 5000, "demand": 1000},
        {"window_start_day": 5, "window_end_day": 2},
        {"price_schedule": [{"day": 3, "price": 1}, {"day": 1, "price": 2}]},
        {"price_schedule": [{"day": 1, "price": 1}, {"day": 1, "price": 2}]},
    ],
)
def test_buyer_consistency(buyer_kw) -> None:
    with pytest.raises(ValidationError):
        make_payload(lots=[lot("l1", 10)], buyers=[buyer("b1", **buyer_kw)])


def test_cold_shelf_life_cannot_be_shorter() -> None:
    with pytest.raises(ValidationError, match="shelf_life_cold_days"):
        make_payload(lots=[lot("l1", 10)], buyers=[buyer("b1")], crops=[crop(shelf_life_ambient_days=5, shelf_life_cold_days=3)])


def test_price_schedule_step_function() -> None:
    b = make_payload(
        lots=[lot("l1", 10)], buyers=[buyer("b1", price=1.0, price_schedule=[{"day": 2, "price": 2.0}, {"day": 5, "price": 3.0}])]
    ).buyers[0]
    assert [b.price_on(d) for d in range(7)] == [1.0, 1.0, 2.0, 2.0, 2.0, 3.0, 3.0]


def test_trip_hours_and_cost_use_road_factor() -> None:
    p = make_payload(
        lots=[lot("l1", 10)],
        buyers=[buyer("b1")],
        routes=[{"buyer_id": "b1", "distance_km": 100, "road_condition": "poor", "toll_per_trip": 5}],
        vehicles=[vehicle(avg_speed_kmh=54, loading_hours_per_trip=1, fixed_cost_per_trip=20, cost_per_km=0.5)],
    )
    r, v = p.routes[0], p.vehicle_types[0]
    assert r.road_factor == 1.35
    assert trip_hours(r, v) == pytest.approx(2 * 100 * 1.35 / 54 + 1)  # 6 h
    assert trip_cost(r, v) == pytest.approx(20 + 2 * 100 * 1.35 * 0.5 + 5)  # 160

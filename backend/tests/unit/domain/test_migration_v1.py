"""v1 -> v2 migration of the five Tunisian fixtures, in compatibility mode."""

import copy

import pytest

from app.domain.migrations_v1 import V1FormatError, detect_format, migrate_v1_to_v2
from app.domain.validation import validate_business
from tests.fixtures.builders import V1_FIXTURES, load_json


def test_all_five_fixtures_are_present() -> None:
    assert len(V1_FIXTURES) == 5


@pytest.mark.parametrize("path", V1_FIXTURES, ids=lambda p: p.stem)
def test_fixture_migrates_in_compatibility_mode(path) -> None:
    v1 = load_json(path)
    assert detect_format(v1) == "v1"

    payload, assumptions = migrate_v1_to_v2(v1)

    lot = payload.harvest_lots[0]
    assert len(payload.harvest_lots) == 1 and lot.available_day == 0
    assert lot.quantity_kg == v1["producer"]["harvest_kg"]
    crop = payload.crops[0]
    assert crop.shelf_life_ambient_days == 1 and crop.type == v1["crop"]["type"]
    assert crop.requires_cold_chain == v1["logistics"]["refrigerated_required"]

    vehicle = payload.vehicle_types[0]
    assert vehicle.count == v1["logistics"]["available_vehicles"]
    assert vehicle.capacity_kg == v1["logistics"]["vehicle_capacity_kg"]
    assert (vehicle.hours_per_day, vehicle.max_trips_per_day, vehicle.fixed_cost_per_trip, vehicle.cost_per_km) == (None, 1, 0, 0)

    assert [b.id for b in payload.buyers] == [b["id"] for b in v1["buyers"]]
    for b in v1["buyers"]:
        r = payload.route_for(b["id"])
        assert r.legacy_cost_per_kg_per_km == b["transport_cost_per_kg_per_km"]
        assert r.distance_km == b["distance_km"] and r.road_factor == 1.0
        assert next(x for x in payload.buyers if x.id == b["id"]).price_per_kg == b["price_per_kg"]

    facility = payload.storage_facilities[0]
    assert facility.capacity_kg == v1["producer"]["storage_capacity_kg"]
    assert facility.cost_per_kg_per_day == v1["producer"]["storage_cost_per_kg_per_day"]

    codes = {a.code for a in assumptions}
    assert {"V1_COMPATIBILITY_MODE", "V1_SHELF_LIFE_REPLACED", "V1_FLEET"} <= codes
    assert validate_business(payload).is_valid


def test_missing_optional_v1_fields_become_assumptions() -> None:
    v1 = copy.deepcopy(load_json(V1_FIXTURES[0]))
    del v1["producer"]["storage_cost_per_kg_per_day"]
    del v1["buyers"][0]["distance_km"]
    payload, assumptions = migrate_v1_to_v2(v1)
    codes = {a.code for a in assumptions}
    assert {"V1_STORAGE_COST_DEFAULT", "V1_DISTANCE_DEFAULT"} <= codes
    assert payload.storage_facilities[0].cost_per_kg_per_day == 0.05


def test_invalid_v1_document_is_rejected_with_paths() -> None:
    v1 = copy.deepcopy(load_json(V1_FIXTURES[0]))
    del v1["producer"]["harvest_kg"]
    v1["buyers"][0]["price_per_kg"] = -1
    with pytest.raises(V1FormatError) as exc:
        migrate_v1_to_v2(v1)
    assert "producer.harvest_kg" in str(exc.value) and "buyers.0.price_per_kg" in str(exc.value)


def test_detect_format() -> None:
    assert detect_format({"schema_version": "2.0"}) == "v2"
    assert detect_format({"hello": 1}) == "unknown"
    assert detect_format([1, 2]) == "unknown"

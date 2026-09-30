from pydantic import ValidationError

from app.domain.dataset import DatasetPayload
from app.domain.diff import payload_diff
from app.domain.validation import report_from_validation_error, validate_business
from tests.fixtures.builders import buyer, crop, lot, make_payload, payload_dict, route, storage, vehicle


def codes(report, level: str) -> set[str]:
    return {i.code for i in getattr(report, level)}


def test_clean_payload_has_no_errors() -> None:
    report = validate_business(make_payload(lots=[lot("l1", 100)], buyers=[buyer("b1")]))
    assert report.is_valid and not report.warnings


def test_no_vehicle_and_no_buyer_for_crop() -> None:
    p = make_payload(
        lots=[lot("l1", 100), lot("l2", 50, crop_id="other")],
        buyers=[buyer("b1")],
        crops=[crop(), crop(id="other", name="Other")],
        vehicles=[vehicle(count=0)],
    )
    assert {"NO_VEHICLE", "NO_BUYER_FOR_CROP"} <= codes(validate_business(p), "errors")


def test_cold_chain_without_reefer_is_an_error() -> None:
    p = make_payload(
        lots=[lot("l1", 100)],
        buyers=[buyer("b1")],
        crops=[crop(requires_cold_chain=True)],
        storage_facilities=[storage()],
    )
    report = validate_business(p)
    assert "COLD_CHAIN_NO_VEHICLE" in codes(report, "errors")
    assert {"AMBIENT_STORAGE_UNUSABLE", "BUYER_UNREACHABLE_COLD_CHAIN"} <= codes(report, "warnings")


def test_warnings_for_demand_contracts_and_long_trips() -> None:
    p = make_payload(
        lots=[lot("l1", 1000)],
        buyers=[buyer("b1", demand=300, min_contract_kg=200), buyer("b2", demand=500, min_contract_kg=400)],
        vehicles=[vehicle(hours_per_day=4, avg_speed_kmh=50)],
        routes=[route("b1", distance=200)],
    )
    warnings = codes(validate_business(p), "warnings")
    assert {"DEMAND_BELOW_HARVEST", "TRIP_TOO_LONG"} <= warnings


def test_contracts_exceeding_harvest() -> None:
    p = make_payload(lots=[lot("l1", 100)], buyers=[buyer("b1", demand=500, min_contract_kg=400)])
    assert "CONTRACTS_EXCEED_HARVEST" in codes(validate_business(p), "warnings")


def test_assumptions_are_listed() -> None:
    data = payload_dict(lots=[lot("l1", 100)], buyers=[buyer("b1")], vehicles=[vehicle()])
    data["currency"] = None
    data["routes"] = [{"buyer_id": "b1", "distance_km": 10}]
    assert {"ROAD_FACTOR_DEFAULT", "UNLIMITED_DRIVING_HOURS", "CURRENCY_DEFAULT"} <= codes(
        validate_business(DatasetPayload.model_validate(data)), "assumptions"
    )


def test_structural_errors_as_report() -> None:
    data = payload_dict(lots=[lot("l1", -1)], buyers=[buyer("b1")])
    try:
        DatasetPayload.model_validate(data)
    except ValidationError as e:
        report = report_from_validation_error(e)
    assert not report.is_valid and report.errors[0].path == "harvest_lots.0.quantity_kg"


def test_diff_matches_by_id_and_reports_paths() -> None:
    a = payload_dict(lots=[lot("l1", 100)], buyers=[buyer("b1", price=1.0), buyer("b2")])
    b = payload_dict(lots=[lot("l1", 100)], buyers=[buyer("b2"), buyer("b1", price=1.5), buyer("b3")])
    del b["routes"][2]  # keep routes identical apart from b3
    b["routes"].append(route("b3"))

    diffs = {(d.path, d.kind) for d in payload_diff(a, b)}
    assert ("buyers[b1].price_per_kg", "changed") in diffs
    assert ("buyers[b3]", "added") in diffs
    assert ("routes[b3]", "added") in diffs
    assert all(not p.startswith("buyers[b2]") for p, _ in diffs)  # reordering is not a change


def test_diff_of_identical_documents_is_empty() -> None:
    a = payload_dict(lots=[lot("l1", 100)], buyers=[buyer("b1")])
    assert payload_diff(a, a) == []

"""ProblemInstance coefficients (no solver involved)."""

import pytest

from app.core.errors import ValidationFailed
from app.domain.run_config import RunConfig
from app.optimization.instance import DIRECT, build_instance, trips_upper_bound
from tests.fixtures.builders import buyer, crop, lot, make_payload, route, storage, vehicle


def test_auto_horizon_is_last_lot_plus_longest_usable_shelf_life() -> None:
    p = make_payload(
        lots=[lot("l1", 100, day=0), lot("l2", 100, day=4)],
        buyers=[buyer("b1")],
        crops=[crop(shelf_life_ambient_days=3, shelf_life_cold_days=6)],
        storage_facilities=[storage("amb"), storage("cold", refrigerated=True)],
    )
    inst = build_instance(p, RunConfig())
    assert inst.horizon == 4 + 6
    assert inst.last_day[("l2", "cold")] == 9 and inst.expires[("l2", "cold")]
    assert inst.last_day[("l1", "amb")] == 2 and inst.last_day[("l1", DIRECT)] == 0


def test_no_storage_means_one_day_per_lot() -> None:
    inst = build_instance(make_payload(lots=[lot("l1", 100, day=2)], buyers=[buyer("b1")]), RunConfig())
    assert inst.horizon == 3


def test_horizon_is_capped_at_60_days() -> None:
    p = make_payload(lots=[lot("l1", 10)], buyers=[buyer("b1")], crops=[crop(shelf_life_ambient_days=300)], storage_facilities=[storage()])
    assert build_instance(p, RunConfig()).horizon == 60


def test_shelf_life_beyond_horizon_is_ending_inventory_not_expiry() -> None:
    p = make_payload(lots=[lot("l1", 10)], buyers=[buyer("b1")], crops=[crop(shelf_life_ambient_days=10)], storage_facilities=[storage()])
    inst = build_instance(p, RunConfig(horizon_days=4))
    assert inst.last_day[("l1", "store")] == 3 and not inst.expires[("l1", "store")]


def test_price_decays_with_age_and_follows_schedule() -> None:
    p = make_payload(
        lots=[lot("l1", 10, day=1)],
        buyers=[buyer("b1", price=2.0, price_schedule=[{"day": 3, "price": 4.0}])],
        crops=[crop(shelf_life_ambient_days=5, quality_decay_pct_per_day=10)],
        storage_facilities=[storage()],
    )
    inst = build_instance(p, RunConfig())
    assert inst.price[("b1", "l1", 1)] == pytest.approx(2.0)  # age 0
    assert inst.price[("b1", "l1", 2)] == pytest.approx(2.0 * 0.9)  # age 1
    assert inst.price[("b1", "l1", 3)] == pytest.approx(4.0 * 0.8)  # new price, age 2
    assert ("b1", "l1", 0) not in inst.price  # not harvested yet


def test_cold_chain_compatibility_and_facility_usability() -> None:
    p = make_payload(
        lots=[lot("l1", 10)],
        buyers=[buyer("b1")],
        crops=[crop(requires_cold_chain=True, shelf_life_ambient_days=2, shelf_life_cold_days=4, loss_rate_pct_per_day_ambient=2, loss_rate_pct_per_day_cold=0.5)],
        storage_facilities=[storage("amb"), storage("cold", refrigerated=True)],
        vehicles=[vehicle("truck"), vehicle("reefer", refrigerated=True)],
    )
    inst = build_instance(p, RunConfig())
    amb, cold = inst.facilities
    assert not amb.usable and cold.usable
    assert (cold.shelf_life, cold.loss_rate, amb.loss_rate) == (4, 0.005, 0.02)
    assert inst.allow[("b1", "truck")] is False and inst.allow[("b1", "reefer")] is True
    assert any("not refrigerated" in w for w in inst.warnings)


def test_trip_cost_hours_and_legacy_cost() -> None:
    p = make_payload(
        lots=[lot("l1", 10)],
        buyers=[buyer("b1")],
        routes=[route("b1", distance=100, road_factor_override=None, road_condition="fair", legacy_cost_per_kg_per_km=0.004)],
        vehicles=[vehicle(avg_speed_kmh=46, loading_hours_per_trip=1, fixed_cost_per_trip=40, cost_per_km=1.0, hours_per_day=12)],
    )
    inst = build_instance(p, RunConfig())
    assert inst.trip_hours[("b1", "truck")] == pytest.approx(2 * 100 * 1.15 / 46 + 1)  # 6 h
    assert inst.trip_cost[("b1", "truck")] == pytest.approx(40 + 230)
    assert inst.buyers[0].legacy_cost_per_kg == pytest.approx(0.4)  # 0.004 x 100 km, no road factor


def test_too_long_trip_makes_buyer_unreachable() -> None:
    p = make_payload(
        lots=[lot("l1", 10)],
        buyers=[buyer("b1")],
        routes=[route("b1", distance=500)],
        vehicles=[vehicle(hours_per_day=8, avg_speed_kmh=50)],
    )
    inst = build_instance(p, RunConfig())
    assert not inst.trip_possible("b1", inst.vehicles[0])
    assert any("cannot be reached" in w for w in inst.warnings)


def test_trips_upper_bound() -> None:
    p = make_payload(
        lots=[lot("l1", 5000)],
        buyers=[buyer("b1", demand=10000)],
        routes=[route("b1", distance=100)],
        vehicles=[vehicle(capacity=1000, count=2, hours_per_day=10, avg_speed_kmh=50, loading_hours_per_trip=1)],
    )
    inst = build_instance(p, RunConfig())
    assert trips_upper_bound(inst, inst.buyers[0], inst.vehicles[0]) == 4  # min(ceil(5000/1000)=5, floor(20/5)=4)


def test_lots_after_horizon_are_dropped_with_a_warning() -> None:
    p = make_payload(lots=[lot("l1", 10, day=0), lot("l2", 10, day=5)], buyers=[buyer("b1")])
    inst = build_instance(p, RunConfig(horizon_days=3))
    assert [l.id for l in inst.lots] == ["l1"] and any("l2" in w for w in inst.warnings)


def test_buyer_window_clipped_or_excluded() -> None:
    p = make_payload(lots=[lot("l1", 10)], buyers=[buyer("b1", window_start_day=1, window_end_day=30), buyer("b2", window_start_day=9)])
    inst = build_instance(p, RunConfig(horizon_days=5))
    assert [b.id for b in inst.buyers] == ["b1"] and inst.buyers[0].window == (1, 4)


@pytest.mark.parametrize(
    ("kw", "config", "message"),
    [
        ({}, RunConfig(crop_id="ghost"), "Unknown crop_id"),
        ({"crops": [crop(), crop(id="d", name="D")]}, RunConfig(crop_id="d"), "has no harvest lot"),
        ({"crops": [crop(), crop(id="d", name="D")], "extra_lot": True}, RunConfig(), "several harvested crops"),
        ({}, RunConfig(horizon_days=1, crop_id=None), None),
    ],
)
def test_crop_selection(kw, config, message) -> None:
    lots = [lot("l1", 10)] + ([lot("l2", 10, crop_id="d")] if kw.pop("extra_lot", False) else [])
    buyers = [buyer("b1", crop_ids=[c["id"] for c in kw.get("crops", [crop()])])]
    p = make_payload(lots=lots, buyers=buyers, **kw)
    if message is None:
        assert build_instance(p, config).crop_id == "c"
    else:
        with pytest.raises(ValidationFailed, match=message):
            build_instance(p, config)

"""Constraint modules, one at a time: which constraints exist and with which coefficients.
(Solutions are checked end to end in test_engine_cases.py.)"""

from __future__ import annotations

import pytest
from pulp import LpMaximize, LpProblem

from app.domain.run_config import RunConfig
from app.optimization.constraints import balance, cold_chain, demand, shelf_life, storage, transport
from app.optimization.instance import DIRECT, build_instance
from app.optimization.keys import ConstraintKey, ConstraintRegistry
from app.optimization.variables import create_variables
from tests.fixtures.builders import buyer, crop, lot, make_payload, route, vehicle
from tests.fixtures.builders import storage as storage_facility


def build(payload, config=None, modules=()):
    inst = build_instance(payload, config or RunConfig())
    v = create_variables(inst)
    problem = LpProblem("t", LpMaximize)
    registry = ConstraintRegistry()
    for module in modules:
        module.add(problem, inst, v, registry)
    return inst, v, registry


def coef(registered, var) -> float:
    return registered.constraint.get(var, 0.0)


def rhs(registered) -> float:
    return -registered.constraint.constant


# ---- balance + shelf life ----

def stored_lot_payload():
    return make_payload(
        lots=[lot("l1", 1000, day=1)],
        buyers=[buyer("b1")],
        crops=[crop(shelf_life_ambient_days=3, loss_rate_pct_per_day_ambient=10)],
        storage_facilities=[storage_facility("s", capacity=500, cost=0.1)],
    )


def test_balance_constraints() -> None:
    inst, v, reg = build(stored_lot_payload(), modules=[balance])
    split = reg.by_key[ConstraintKey("lot_split", ("l1",))]
    assert rhs(split) == 1000 and coef(split, v.z[("l1", DIRECT)]) == 1 and coef(split, v.z[("l1", "s")]) == 1

    direct = reg.by_key[ConstraintKey("direct_sale", ("l1",))]
    assert coef(direct, v.unsold["l1"]) == 1 and coef(direct, v.z[("l1", DIRECT)]) == -1
    assert coef(direct, v.x[("b1", "l1", DIRECT, 1)]) == 1

    # day 1 (harvest): stock == placed ; day 2: stock == 0.9 x previous - sales
    first = reg.by_key[ConstraintKey("balance", ("l1", "s"), 1)]
    assert coef(first, v.inv[("l1", "s", 1)]) == 1 and coef(first, v.z[("l1", "s")]) == -1
    second = reg.by_key[ConstraintKey("balance", ("l1", "s"), 2)]
    assert coef(second, v.inv[("l1", "s", 2)]) == 1
    assert coef(second, v.inv[("l1", "s", 1)]) == pytest.approx(-0.9)
    assert coef(second, v.x[("b1", "l1", "s", 2)]) == 1
    assert ("b1", "l1", "s", 1) not in v.x  # no storage sale on the harvest day
    assert {r.key.day for r in reg if r.key.family == "balance"} == {1, 2, 3}  # shelf life 3 days: days 1..3


def test_shelf_life_records_expiry_inside_horizon_only() -> None:
    inst, v, reg = build(stored_lot_payload(), modules=[shelf_life])
    expired = reg.by_key[ConstraintKey("shelf_life", ("l1", "s"))]
    assert coef(expired, v.expired[("l1", "s")]) == 1 and coef(expired, v.inv[("l1", "s", 3)]) == -1
    assert max(t for (_, _, _, t) in v.x) == 3  # no sale after the last shelf-life day

    _, v2, reg2 = build(stored_lot_payload(), RunConfig(horizon_days=3), modules=[shelf_life])
    assert v2.expired == {} and "shelf_life" not in reg2.families()  # day 3 is past a 3-day horizon


# ---- storage ----

def test_storage_capacity_per_facility_and_day() -> None:
    inst, v, reg = build(
        make_payload(
            lots=[lot("l1", 1000, day=0), lot("l2", 500, day=1)],
            buyers=[buyer("b1")],
            crops=[crop(shelf_life_ambient_days=3)],
            storage_facilities=[storage_facility("s", capacity=500)],
        ),
        modules=[storage],
    )
    day1 = reg.by_key[ConstraintKey("storage_capacity", ("s",), 1)]
    assert rhs(day1) == 500
    assert coef(day1, v.inv[("l1", "s", 1)]) == 1 and coef(day1, v.inv[("l2", "s", 1)]) == 1
    assert {r.key.day for r in reg} == {0, 1, 2, 3}


# ---- demand ----

def test_demand_max_day_min_and_moq() -> None:
    p = make_payload(
        lots=[lot("l1", 1000)],
        buyers=[
            buyer("plain", demand=800),
            buyer("daily", demand=900, max_per_day_kg=100, min_contract_kg=50),
            buyer("moq", demand=700, min_order_kg=300),
        ],
        crops=[crop(shelf_life_ambient_days=2)],
        storage_facilities=[storage_facility()],
    )
    inst, v, reg = build(p, modules=[demand])
    plain = reg.by_key[ConstraintKey("demand_max", ("plain",))]
    assert rhs(plain) == 800

    assert rhs(reg.by_key[ConstraintKey("demand_day", ("daily",), 0)]) == 100
    assert rhs(reg.by_key[ConstraintKey("demand_day", ("daily",), 1)]) == 100
    assert rhs(reg.by_key[ConstraintKey("demand_min", ("daily",))]) == 50

    moq_max = reg.by_key[ConstraintKey("demand_max", ("moq",))]
    assert rhs(moq_max) == 0 and coef(moq_max, v.y["moq"]) == -700  # sold <= 700 y
    moq_min = reg.by_key[ConstraintKey("moq_min", ("moq",))]
    assert coef(moq_min, v.y["moq"]) == -300  # sold >= 300 y
    assert "plain" not in v.y


def test_unreachable_contract_is_trivially_infeasible() -> None:
    p = make_payload(lots=[lot("l1", 100)], buyers=[buyer("b1", window_start_day=5, min_contract_kg=10, demand=50), buyer("b2")])
    inst, _, reg = build(p, RunConfig(horizon_days=3), modules=[demand])  # window after the horizon -> buyer dropped
    assert reg.trivially_infeasible == [] and any("B1" in w for w in inst.warnings)
    p2 = make_payload(lots=[lot("l1", 100)], buyers=[buyer("b1", window_start_day=2, min_contract_kg=10, demand=50)])
    _, _, reg2 = build(p2, RunConfig(horizon_days=3), modules=[demand])  # in window but lot cannot last until day 2
    assert reg2.trivially_infeasible == [ConstraintKey("demand_min", ("b1",))]


# ---- transport ----

def test_transport_constraints() -> None:
    p = make_payload(
        lots=[lot("l1", 5000)],
        buyers=[buyer("near"), buyer("far")],
        routes=[route("near", distance=50), route("far", distance=400)],
        vehicles=[
            vehicle("truck", capacity=1000, count=2, hours_per_day=10, avg_speed_kmh=50, loading_hours_per_trip=1),
            vehicle("van", capacity=300, count=1, max_trips_per_day=3),
        ],
    )
    inst, v, reg = build(p, modules=[transport])
    cap = reg.by_key[ConstraintKey("trip_capacity", ("near",), 0)]
    assert coef(cap, v.x[("near", "l1", DIRECT, 0)]) == 1
    assert coef(cap, v.n[("near", "truck", 0)]) == -1000 and coef(cap, v.n[("near", "van", 0)]) == -300

    time = reg.by_key[ConstraintKey("fleet_time", ("truck",), 0)]
    assert rhs(time) == 20 and coef(time, v.n[("near", "truck", 0)]) == pytest.approx(3.0)  # 100/50 + 1
    assert coef(time, v.n[("far", "truck", 0)]) == 0  # impossible trips do not consume hours

    too_long = reg.by_key[ConstraintKey("trip_duration", ("far", "truck"))]  # 800/50 + 1 = 17 h > 10 h
    assert rhs(too_long) == 0 and coef(too_long, v.n[("far", "truck", 0)]) == 1

    trips = reg.by_key[ConstraintKey("fleet_trips", ("van",), 0)]
    assert rhs(trips) == 3
    assert "fleet_time" not in {r.key.family for r in reg if r.key.entity == ("van",)}  # van has no hour limit


# ---- cold chain ----

def test_cold_chain_constraints() -> None:
    p = make_payload(
        lots=[lot("l1", 100)],
        buyers=[buyer("b1")],
        crops=[crop(requires_cold_chain=True, shelf_life_ambient_days=2)],
        storage_facilities=[storage_facility("amb"), storage_facility("cold", refrigerated=True)],
        vehicles=[vehicle("truck"), vehicle("reefer", refrigerated=True)],
    )
    inst, v, reg = build(p, modules=[cold_chain])
    blocked = reg.by_key[ConstraintKey("cold_chain_vehicle", ("b1", "truck"))]
    assert rhs(blocked) == 0 and coef(blocked, v.n[("b1", "truck", 0)]) == 1
    assert ConstraintKey("cold_chain_vehicle", ("b1", "reefer")) not in reg.by_key
    no_ambient = reg.by_key[ConstraintKey("cold_chain_storage", ("amb",))]
    assert coef(no_ambient, v.z[("l1", "amb")]) == 1
    assert ConstraintKey("cold_chain_storage", ("cold",)) not in reg.by_key


def test_keys_have_readable_labels() -> None:
    key = ConstraintKey("fleet_time", ("truck",), 3)
    assert str(key) == "fleet_time|truck|3"
    assert key.label({"truck": "Camion 3 t"}.get) == "Driving hours of the Camion 3 t fleet (day 3)"
    with pytest.raises(ValueError):
        ConstraintKey("nonsense")

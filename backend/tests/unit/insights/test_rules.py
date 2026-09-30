"""The 12 insight rules (plan §16): each is triggered by one case and silent on another, and its
evidence holds the numbers its message is built from."""

from __future__ import annotations

import pytest

from app.analytics.context import RunContext
from app.domain.enums import SolverOutcome
from app.domain.insight import InsightCandidate
from app.domain.results import ProbeResult, SensitivityReport, WasteRow
from app.domain.run_config import RunConfig
from app.insights.base import RuleContext, render
from app.insights.engine import InsightEngine, message_for
from app.insights.rules import ALL_RULES, RULES_BY_ID
from app.insights.thresholds import DEFAULT_THRESHOLDS, Thresholds
from tests.fixtures.builders import buyer, crop, lot, make_payload, storage, vehicle
from tests.fixtures.runs import solve_context
from tests.fixtures.solver import cases


def evaluate(rule_id: str, ctx: RunContext, thresholds: Thresholds = DEFAULT_THRESHOLDS) -> list[InsightCandidate]:
    return RULES_BY_ID[rule_id].evaluate(RuleContext(run=ctx, thresholds=thresholds))


def metrics(c: InsightCandidate) -> dict[str, object]:
    return {m.key: m.value for m in c.evidence.metrics}


def costly(trip_cost: float) -> RunContext:
    """1 000 kg sold at 1.0 with one trip of `trip_cost` (plus a cheaper second buyer never used)."""
    return solve_context(
        make_payload(lots=[lot("l1", 1000)], buyers=[buyer("x", price=1.0, demand=1000)], vehicles=[vehicle(capacity=1000, fixed_cost_per_trip=trip_cost)])
    )


def with_probe(ctx: RunContext, key: str, gain: float, significant: bool = True) -> RunContext:
    probe = ProbeResult(constraint_key=key, label=key, change={}, outcome=SolverOutcome.OPTIMAL, objective_value=0, delta_objective=gain, significant=significant)
    report = SensitivityReport(probes=[probe], probes_computed=True)
    return RunContext.build(ctx.run_id, ctx.payload, ctx.config, ctx.result.model_copy(update={"sensitivity": report}), report)


def test_there_are_twelve_rules_with_unique_ids() -> None:
    assert len(ALL_RULES) == 12 and len(RULES_BY_ID) == 12


# ---- HIGH_WASTE ----

def test_high_waste_warning() -> None:
    (c,) = evaluate("HIGH_WASTE", solve_context(cases.direct_sale().payload))  # 200 / 1 000 = 20 % -> warning (not > 20)
    assert c.severity == "warning" and metrics(c)["waste_rate_pct"] == 20 and metrics(c)["lost_kg"] == 200
    assert {t.key: t.value for t in c.evidence.thresholds} == {"warning_pct": 10, "critical_pct": 20}
    assert message_for("HIGH_WASTE", c.message_params) == "20 % of the harvest is lost (200 kg), above the 10 % threshold."


def test_high_waste_critical_and_silent() -> None:
    payload = make_payload(lots=[lot("l1", 1000)], buyers=[buyer("b1", demand=700)])
    (c,) = evaluate("HIGH_WASTE", solve_context(payload))
    assert c.severity == "critical" and c.evidence.formula_id.startswith("waste_rate_pct")
    assert evaluate("HIGH_WASTE", solve_context(cases.storage_profitable().payload, cases.storage_profitable().config)) == []


# ---- EXPIRY_LOSS ----

def test_expiry_loss() -> None:
    c = cases.forced_expiry()
    ctx = solve_context(c.payload, c.config)
    expired = [WasteRow(day=1, lot_id="l1", facility_id="store", kind="expired", kg=1000, value_lost=1000)]
    ctx = RunContext.build("r", c.payload, c.config, ctx.result.model_copy(update={"waste": expired}))
    (found,) = evaluate("EXPIRY_LOSS", ctx)
    assert found.severity == "critical" and metrics(found) == {"expired_kg": 1000, "expired_share_pct": 100, "expired_value": 1000}
    assert found.suggested_changes == [{"op": "shelf_life", "target": "c", "params": {"field": "ambient", "mode": "delta", "value": 1}}]
    assert evaluate("EXPIRY_LOSS", solve_context(cases.direct_sale().payload)) == []  # lost unsold, not expired


# ---- ENDING_STOCK_UNSOLD ----

def _ending_stock(salvage: float) -> RunContext:
    """Demand 500, free storage, shelf life 10 > horizon 3, disposal 0.1/kg: keeping stock is cheaper than losing it."""
    payload = make_payload(
        lots=[lot("l1", 1000)],
        buyers=[buyer("b1", demand=500)],
        crops=[crop(shelf_life_ambient_days=10)],
        storage_facilities=[storage(capacity=1000, cost=0.0)],
    )
    return solve_context(payload, RunConfig(horizon_days=3, disposal_cost_per_kg=0.1, salvage_value_pct=salvage))


def test_ending_stock_unsold() -> None:
    (c,) = evaluate("ENDING_STOCK_UNSOLD", _ending_stock(0))
    assert metrics(c) == {"ending_inventory_kg": 500, "salvage_value_pct": 0}
    assert evaluate("ENDING_STOCK_UNSOLD", _ending_stock(50)) == []


# ---- STORAGE_NEAR_FULL / STORAGE_IDLE ----

def test_storage_near_full() -> None:
    c = cases.storage_saturated()
    (found,) = evaluate("STORAGE_NEAR_FULL", solve_context(c.payload, c.config))
    assert metrics(found)["peak_pct"] == 100 and metrics(found)["capacity_kg"] == 600
    assert found.entity_ref == {"type": "storage", "id": "store"}
    assert found.suggested_changes[0]["op"] == "storage_capacity"
    idle = cases.storage_not_profitable()
    assert evaluate("STORAGE_NEAR_FULL", solve_context(idle.payload, idle.config)) == []


def test_storage_idle() -> None:
    """direct_sale + an expensive store: 200 kg lost while the store stays empty."""
    payload = make_payload(lots=[lot("l1", 1000)], buyers=[buyer("b1", price=2.0, demand=800)], storage_facilities=[storage(cost=5.0)])
    (found,) = evaluate("STORAGE_IDLE", solve_context(payload))
    assert metrics(found)["peak_pct"] == 0 and metrics(found)["lost_kg"] == 200
    c = cases.storage_saturated()
    assert evaluate("STORAGE_IDLE", solve_context(c.payload, c.config)) == []
    assert evaluate("STORAGE_IDLE", solve_context(payload), Thresholds(storage_idle_min_lost_kg=500)) == []


# ---- LOW_MARGIN_BUYER ----

def test_low_margin_buyer() -> None:
    (c,) = evaluate("LOW_MARGIN_BUYER", costly(900))  # net 0.1 / price 1.0 = 10 % < 20 %
    assert metrics(c)["net_to_price_pct"] == 10 and metrics(c)["net_price_per_kg"] == pytest.approx(0.1)
    assert evaluate("LOW_MARGIN_BUYER", solve_context(cases.direct_sale().payload)) == []


# ---- DEMAND_BOTTLENECK ----

def test_demand_bottleneck_from_a_significant_probe() -> None:
    ctx = with_probe(solve_context(cases.direct_sale().payload), "demand_max|b1|", 160)
    (c,) = evaluate("DEMAND_BOTTLENECK", ctx)
    assert metrics(c)["gain"] == 160 and c.message_params["basis"] == "for +10 % demand"
    assert c.suggested_changes[0]["params"]["field"] == "max_demand_kg"


def test_demand_bottleneck_from_a_reliable_dual() -> None:
    ctx = solve_context(cases.direct_sale().payload)
    constraints = [c.model_copy(update={"dual": 2.0, "dual_reliable": True}) if c.key == "demand_max|b1|" else c for c in ctx.result.constraints]
    ctx = RunContext.build("r", ctx.payload, ctx.config, ctx.result.model_copy(update={"constraints": constraints}))
    (c,) = evaluate("DEMAND_BOTTLENECK", ctx)
    assert c.message_params["basis"] == "per extra kg" and metrics(c)["gain"] == 2.0


def test_demand_bottleneck_silent_without_evidence_of_gain() -> None:
    ctx = solve_context(cases.direct_sale().payload)  # degenerate dual (unreliable), no probe
    assert evaluate("DEMAND_BOTTLENECK", ctx) == []
    assert evaluate("DEMAND_BOTTLENECK", with_probe(ctx, "demand_max|b1|", 5, significant=False)) == []


# ---- UNSERVED_PROFITABLE_BUYER ----

def test_unserved_profitable_buyer() -> None:
    (c,) = evaluate("UNSERVED_PROFITABLE_BUYER", solve_context(cases.minimum_order().payload))
    assert c.entity_ref == {"type": "buyer", "id": "a"} and metrics(c)["estimated_net_price_per_kg"] == 3.0
    refused = cases.profit_refuses_costly_trip()
    assert evaluate("UNSERVED_PROFITABLE_BUYER", solve_context(refused.payload, refused.config)) == []


# ---- HIGH_TRANSPORT_SHARE ----

@pytest.mark.parametrize(("trip_cost", "severity"), [(400, "warning"), (600, "critical")])
def test_high_transport_share(trip_cost: float, severity: str) -> None:
    (c,) = evaluate("HIGH_TRANSPORT_SHARE", costly(trip_cost))
    assert c.severity == severity and metrics(c)["transport_share_pct"] == trip_cost / 10


def test_high_transport_share_silent() -> None:
    assert evaluate("HIGH_TRANSPORT_SHARE", solve_context(cases.direct_sale().payload)) == []  # 50 / 1 600


# ---- FLEET_BOTTLENECK ----

def test_fleet_bottleneck() -> None:
    ctx = solve_context(cases.fleet_limiting().payload)
    (c,) = evaluate("FLEET_BOTTLENECK", ctx)
    assert metrics(c)["binding_days"] == 1 and c.message_params["gain"] == "not computed yet"
    (c,) = evaluate("FLEET_BOTTLENECK", with_probe(ctx, "fleet_time|truck|", 1000))
    assert metrics(c)["gain_one_more_vehicle"] == 1000 and c.suggested_changes[0]["op"] == "vehicle_count"
    assert evaluate("FLEET_BOTTLENECK", with_probe(ctx, "fleet_time|truck|", 3, significant=False)) == []
    assert evaluate("FLEET_BOTTLENECK", solve_context(cases.direct_sale().payload)) == []


# ---- COLD_CHAIN_GAP ----

def test_cold_chain_gap() -> None:
    perishable = make_payload(lots=[lot("l1", 1000)], buyers=[buyer("b1")], crops=[crop(type="perishable")])
    (c,) = evaluate("COLD_CHAIN_GAP", solve_context(perishable))
    assert c.severity == "warning" and metrics(c)["refrigerated_vehicles"] == 0
    cold_buyer = make_payload(lots=[lot("l1", 1000)], buyers=[buyer("b1"), buyer("b2", requires_cold_chain=True)])
    (c,) = evaluate("COLD_CHAIN_GAP", solve_context(cold_buyer))
    assert c.severity == "critical" and metrics(c)["cold_chain_buyers"] == 1
    assert evaluate("COLD_CHAIN_GAP", solve_context(cases.cold_chain().payload)) == []  # a reefer exists


# ---- CONCENTRATION ----

def test_concentration() -> None:
    (c,) = evaluate("CONCENTRATION", solve_context(cases.minimum_order().payload))  # everything to b
    assert c.severity == "critical" and metrics(c)["share_pct"] == 100
    balanced = make_payload(lots=[lot("l1", 1000)], buyers=[buyer("a", demand=500), buyer("b", demand=500)])
    assert evaluate("CONCENTRATION", solve_context(balanced)) == []
    assert evaluate("CONCENTRATION", solve_context(cases.direct_sale().payload)) == []  # single buyer


# ---- engine ----

def test_engine_orders_by_severity_and_renders_every_message() -> None:
    found = InsightEngine().evaluate(solve_context(cases.minimum_order().payload))
    severities = [c.severity for c in found]
    assert severities == sorted(severities, key={"critical": 0, "warning": 1, "info": 2}.get)
    for c in found:
        assert "{" not in render(RULES_BY_ID[c.rule_id].message, c.message_params)
        assert c.evidence.run_id == "run-1" and c.evidence.rule_version == 1


def test_each_rule_is_a_pure_function() -> None:
    rc = RuleContext(run=solve_context(cases.fleet_limiting().payload), thresholds=DEFAULT_THRESHOLDS)
    for rule in ALL_RULES:
        assert rule.evaluate(rc) == rule.evaluate(rc)

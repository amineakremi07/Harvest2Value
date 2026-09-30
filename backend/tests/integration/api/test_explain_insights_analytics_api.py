"""Explainability, insights and analytics endpoints (phase 4) on real runs."""

from __future__ import annotations

from collections.abc import Callable

import pytest
from fastapi.testclient import TestClient

from tests.fixtures.api import API, create_dataset, error_code, start_run, wait_for
from tests.fixtures.builders import buyer, lot, payload_dict, route, vehicle


@pytest.fixture
def client(make_client: Callable[..., TestClient]) -> TestClient:
    return make_client()


def fleet_limited() -> dict:
    """2 trucks x 10 h, 5 h per trip -> 4 000 of 5 000 kg delivered; +1 truck -> +1 000."""
    return payload_dict(
        lots=[lot("l1", 5000)],
        buyers=[buyer("b1", price=1.0, demand=10000)],
        vehicles=[vehicle(capacity=1000, count=2, hours_per_day=10, avg_speed_kmh=50, loading_hours_per_trip=1)],
        routes=[route("b1", distance=100)],
    )


def test_explanation_is_complete_and_cached(client: TestClient) -> None:
    run = start_run(client, create_dataset(client, template="tunisia_dates"))
    first = client.get(f"{API}/runs/{run['id']}/explanation")
    assert first.status_code == 200
    body = first.json()
    buyers = [d for d in body["decisions"] if d["kind"] == "buyer"]
    assert len(buyers) == 4 and all(d["limiting_factor"]["code"] for d in buyers)
    assert {d["kind"] for d in body["decisions"]} == {"buyer", "storage", "waste"}
    assert body["binding"] and body["bottlenecks"][0]["rank"] == 1 and body["sensitivity_computed"] is False
    assert client.get(f"{API}/runs/{run['id']}/explanation").json() == body


def test_constraints_and_bottlenecks(client: TestClient) -> None:
    run = start_run(client, create_dataset(client, payload=fleet_limited()))
    everything = client.get(f"{API}/runs/{run['id']}/constraints").json()
    binding = client.get(f"{API}/runs/{run['id']}/constraints", params={"binding_only": True}).json()
    assert len(binding) < len(everything) and all(c["binding"] for c in binding)
    bottlenecks = client.get(f"{API}/runs/{run['id']}/bottlenecks").json()
    assert bottlenecks[0]["key"] == "fleet_time|truck|" and bottlenecks[0]["suggested_change"]["op"] == "vehicle_count"


def test_marginal_values_lifecycle(client: TestClient) -> None:
    run = start_run(client, create_dataset(client, payload=fleet_limited()))
    r = client.get(f"{API}/runs/{run['id']}/marginal-values")
    assert r.status_code == 409 and error_code(r) == "NOT_COMPUTED" and r.json()["error"]["details"]["status"] == "not_requested"

    r = client.post(f"{API}/runs/{run['id']}/marginal-values?wait=15")
    assert r.status_code == 200 and r.json()["status"] == "computed"
    report = client.get(f"{API}/runs/{run['id']}/marginal-values").json()
    (probe,) = report["probes"]
    assert probe["label"] == "+1 vehicle of type Truck" and probe["delta_objective"] == 1000 and probe["significant"]
    assert report["probes_computed"] and report["probe_gap"] == 0.01

    explanation = client.get(f"{API}/runs/{run['id']}/explanation").json()  # cache was invalidated
    assert explanation["sensitivity_computed"] and explanation["bottlenecks"][0]["probe_gain"] == 1000
    insights = {i["rule_id"]: i for i in client.get(f"{API}/runs/{run['id']}/insights").json()}
    assert insights["FLEET_BOTTLENECK"]["message"] == "The Truck fleet is fully used on 1 day(s); one more vehicle: +1,000.00."

    again = client.post(f"{API}/runs/{run['id']}/marginal-values")
    assert again.status_code == 200 and again.json()["status"] == "computed"


def test_explain_endpoints_refuse_unfinished_or_infeasible_runs(client: TestClient) -> None:
    infeasible = payload_dict(lots=[lot("l1", 1000)], buyers=[buyer("b1", demand=3000, min_contract_kg=2000)])
    run = start_run(client, create_dataset(client, payload=infeasible))
    for path in ("explanation", "bottlenecks", "constraints", "network"):
        r = client.get(f"{API}/runs/{run['id']}/{path}")
        assert r.status_code == 409 and error_code(r) == "RUN_INFEASIBLE", path
    assert client.post(f"{API}/runs/{run['id']}/marginal-values").status_code == 409
    assert client.get(f"{API}/runs/nope/explanation").status_code == 404


def test_insights_dismiss_restore(client: TestClient) -> None:
    payload = payload_dict(lots=[lot("l1", 1000)], buyers=[buyer("b1", price=2.0, demand=700)])  # 30 % lost
    run = start_run(client, create_dataset(client, payload=payload))
    insights = client.get(f"{API}/runs/{run['id']}/insights").json()
    waste = next(i for i in insights if i["rule_id"] == "HIGH_WASTE")
    assert waste["severity"] == "critical" and waste["message"].startswith("30 % of the harvest is lost (300 kg)")
    assert {m["key"]: m["value"] for m in waste["evidence"]["metrics"]}["lost_kg"] == 300
    assert waste["evidence"]["run_id"] == run["id"]

    assert client.post(f"{API}/insights/{waste['id']}/dismiss").json()["dismissed"] is True
    assert waste["id"] not in [i["id"] for i in client.get(f"{API}/runs/{run['id']}/insights").json()]
    all_ = client.get(f"{API}/runs/{run['id']}/insights", params={"include_dismissed": True}).json()
    assert next(i for i in all_ if i["id"] == waste["id"])["dismissed"] is True
    assert client.post(f"{API}/insights/{waste['id']}/restore").json()["dismissed"] is False
    assert client.post(f"{API}/insights/nope/dismiss").status_code == 404


def test_dismissal_survives_regeneration(client: TestClient) -> None:
    run = start_run(client, create_dataset(client, payload=fleet_limited()))
    fleet = next(i for i in client.get(f"{API}/runs/{run['id']}/insights").json() if i["rule_id"] == "FLEET_BOTTLENECK")
    client.post(f"{API}/insights/{fleet['id']}/dismiss")
    client.post(f"{API}/runs/{run['id']}/marginal-values?wait=15")  # regenerates the insights
    regenerated = client.get(f"{API}/runs/{run['id']}/insights", params={"include_dismissed": True}).json()
    assert next(i for i in regenerated if i["rule_id"] == "FLEET_BOTTLENECK")["dismissed"] is True


def test_try_an_insight_creates_and_runs_a_scenario(client: TestClient) -> None:
    run = start_run(client, create_dataset(client, payload=fleet_limited()))
    fleet = next(i for i in client.get(f"{API}/runs/{run['id']}/insights").json() if i["rule_id"] == "FLEET_BOTTLENECK")
    r = client.post(f"{API}/insights/{fleet['id']}/try")
    assert r.status_code == 202
    trial = r.json()
    scenario = client.get(f"{API}/scenarios/{trial['scenario_id']}").json()
    assert [(c["op"], c["source"]) for c in scenario["changes"]] == [("vehicle_count", "recommendation")]
    done = wait_for(client, trial["run_id"])
    assert done["status"] == "succeeded" and done["scenario_id"] == trial["scenario_id"]
    assert done["headline"]["realized_profit"] == run["headline"]["realized_profit"] + 1000

    no_change = next(i for i in client.get(f"{API}/runs/{run['id']}/insights").json() if not i["suggested_changes"])
    r = client.post(f"{API}/insights/{no_change['id']}/try")
    assert r.status_code == 422 and error_code(r) == "NO_SUGGESTED_CHANGE"


@pytest.mark.parametrize("section", ["financial", "operational", "buyers", "logistics", "crops"])
def test_analytics_sections(client: TestClient, section: str) -> None:
    run = start_run(client, create_dataset(client))
    r = client.get(f"{API}/analytics/runs/{run['id']}/{section}")
    assert r.status_code == 200 and r.json()["run_id"] == run["id"]


def test_network_and_market(client: TestClient) -> None:
    dataset_id = create_dataset(client)
    run = start_run(client, dataset_id)
    graph = client.get(f"{API}/runs/{run['id']}/network").json()
    kinds = {n["kind"] for n in graph["nodes"]}
    assert {"producer", "lot", "storage", "direct", "vehicle", "buyer"} <= kinds
    assert client.get(f"{API}/runs/{run['id']}/network", params={"day": 0}).json()["day"] == 0
    market = client.get(f"{API}/datasets/{dataset_id}/market").json()
    assert market["crop_id"] and [r["rank"] for r in market["rows"] if r["rank"]] == sorted(r["rank"] for r in market["rows"] if r["rank"])
    assert client.get(f"{API}/datasets/nope/market").status_code == 404


def test_dashboard(client: TestClient) -> None:
    r = client.get(f"{API}/analytics/dashboard")
    assert r.status_code == 404 and error_code(r) == "NO_RUN"
    dataset_id = create_dataset(client)
    baseline = start_run(client, dataset_id)
    dash = client.get(f"{API}/analytics/dashboard").json()
    assert dash["run"]["run_id"] == baseline["id"] and dash["baseline_run_id"] is None and dash["kpi_deltas"] == {}
    assert dash["best_buyer"] and dash["history"][0]["run_id"] == baseline["id"] and len(dash["series"]) > 0

    scenario = client.post(
        f"{API}/scenarios",
        json={"name": "-10 %", "dataset_id": dataset_id, "changes": [{"op": "buyer_price", "target": "*", "params": {"mode": "relative_pct", "value": -10}}]},
    ).json()
    run = client.post(f"{API}/scenarios/{scenario['scenario']['id']}/run?wait=15").json()
    dash = client.get(f"{API}/analytics/dashboard", params={"run_id": run["id"]}).json()
    assert dash["baseline_run_id"] == baseline["id"]
    assert dash["kpi_deltas"]["realized_profit"]["abs"] < 0
    assert len(dash["history"]) == 2

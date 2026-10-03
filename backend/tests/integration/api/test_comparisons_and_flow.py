"""Comparisons API, the end-to-end Swagger flow of steps 3-5, and the frozen v2 route contract."""

from __future__ import annotations

from collections.abc import Callable

import pytest
from fastapi.testclient import TestClient

from tests.fixtures.api import API, SlowEngine, create_dataset, error_code, start_run

PRICE_MINUS_10 = {"op": "buyer_price", "target": "*", "params": {"mode": "relative_pct", "value": -10}}


@pytest.fixture
def client(make_client: Callable[..., TestClient]) -> TestClient:
    return make_client()


def test_compare_baseline_with_scenarios(client: TestClient) -> None:
    dataset_id = create_dataset(client)
    buyers = client.get(f"{API}/datasets/{dataset_id}").json()["current_version"]["payload"]["buyers"]
    baseline = start_run(client, dataset_id)
    cheaper = client.post(f"{API}/scenarios", json={"name": "-10 %", "dataset_id": dataset_id, "changes": [PRICE_MINUS_10]}).json()
    # buyer_tn_03: removing buyer_tn_01 or _04 makes this MIP take 8-17 s (solver variance, see report)
    lost = next(b for b in buyers if b["id"] == "buyer_tn_03")
    no_top = client.post(
        f"{API}/scenarios", json={"name": "lose a buyer", "dataset_id": dataset_id, "changes": [{"op": "remove_buyer", "target": lost["id"]}]}
    ).json()
    run_a = client.post(f"{API}/scenarios/{cheaper['scenario']['id']}/run?wait=15").json()
    run_b = client.post(f"{API}/scenarios/{no_top['scenario']['id']}/run?wait=15").json()

    r = client.post(f"{API}/comparisons", json={"baseline_run_id": baseline["id"], "run_ids": [run_a["id"], run_b["id"]]})
    assert r.status_code == 200
    body = r.json()
    revenue = next(k for k in body["kpi_table"] if k["kpi"] == "realized_revenue")
    assert revenue["deltas"][run_a["id"]]["pct"] == pytest.approx(-10, abs=0.01)  # same plan, prices -10 %
    removed = next(row for row in body["buyer_matrix"] if row["buyer_id"] == lost["id"])
    assert removed["cells"][run_b["id"]]["status"] == "removed" and removed["cells"][run_b["id"]]["sold_kg"] is None
    assert any(c["code"] == "BUYER_REMOVED" and c["run_id"] == run_b["id"] for c in body["notable_changes"])
    assert body["runs"][0]["run_id"] == baseline["id"] and set(body["series"]) == {"sold_kg_by_day", "stock_kg_by_day"}


def test_comparison_errors(client: TestClient) -> None:
    olives = start_run(client, create_dataset(client))
    dates = start_run(client, create_dataset(client, template="tunisia_dates"))
    r = client.post(f"{API}/comparisons", json={"baseline_run_id": olives["id"], "run_ids": [dates["id"]]})
    assert r.status_code == 422 and error_code(r) == "INCOMPARABLE"
    r = client.post(f"{API}/comparisons", json={"baseline_run_id": olives["id"], "run_ids": [olives["id"]]})
    assert r.status_code == 422
    r = client.post(f"{API}/comparisons", json={"baseline_run_id": olives["id"], "run_ids": ["a", "b", "c", "d"]})
    assert r.status_code == 422 and error_code(r) == "VALIDATION_ERROR"
    assert client.post(f"{API}/comparisons", json={"baseline_run_id": "nope", "run_ids": [olives["id"]]}).status_code == 404

    dataset_id = create_dataset(client)
    client.app.state.optimization_engine = SlowEngine(1.0)
    pending = start_run(client, dataset_id, wait=0, config={"objective": "revenue"})
    r = client.post(f"{API}/comparisons", json={"baseline_run_id": olives["id"], "run_ids": [pending["id"]]})
    assert r.status_code == 409 and error_code(r) == "RUN_NOT_FINISHED"


def test_swagger_flow_dataset_run_explain_insights_analytics_scenario_compare(client: TestClient) -> None:
    """Global success criterion of step 3: everything the Swagger UI lets a user do, in order."""
    dataset_id = client.post(f"{API}/datasets", json={"template_key": "tunisia_tomatoes"}).json()["dataset"]["id"]
    run = client.post(f"{API}/runs?wait=15", json={"dataset_id": dataset_id, "label": "baseline"}).json()
    assert run["status"] == "succeeded"
    run_id = run["id"]

    assert client.get(f"{API}/runs/{run_id}/result").json()["kpis"]["realized_profit"] == run["headline"]["realized_profit"]
    assert client.get(f"{API}/runs/{run_id}/explanation").json()["decisions"]
    assert client.post(f"{API}/runs/{run_id}/marginal-values?wait=15").json()["status"] == "computed"
    assert client.get(f"{API}/runs/{run_id}/marginal-values").json()["probes_computed"] is True
    assert client.get(f"{API}/runs/{run_id}/insights").status_code == 200
    for section in ("financial", "operational", "buyers", "logistics", "crops"):
        assert client.get(f"{API}/analytics/runs/{run_id}/{section}").status_code == 200
    assert client.get(f"{API}/analytics/dashboard").json()["run"]["run_id"] == run_id

    scenario = client.post(f"{API}/scenarios", json={"name": "Prix -10 %", "dataset_id": dataset_id, "changes": [PRICE_MINUS_10]}).json()
    scenario_run = client.post(f"{API}/scenarios/{scenario['scenario']['id']}/run?wait=15").json()
    assert scenario_run["status"] == "succeeded"
    comparison = client.post(f"{API}/comparisons", json={"baseline_run_id": run_id, "run_ids": [scenario_run["id"]]}).json()
    profit = next(k for k in comparison["kpi_table"] if k["kpi"] == "realized_profit")
    assert profit["deltas"][scenario_run["id"]]["abs"] < 0 and comparison["notable_changes"]


V2_ROUTES = {
    ("GET", "/api/v2/health"),
    ("GET", "/api/v2/health/ready"),
    ("GET", "/api/v2/meta"),
    ("GET", "/api/v2/templates"),
    ("GET", "/api/v2/datasets"),
    ("POST", "/api/v2/datasets"),
    ("POST", "/api/v2/datasets/import"),
    ("GET", "/api/v2/datasets/{dataset_id}"),
    ("PATCH", "/api/v2/datasets/{dataset_id}"),
    ("DELETE", "/api/v2/datasets/{dataset_id}"),
    ("PUT", "/api/v2/datasets/{dataset_id}/payload"),
    ("POST", "/api/v2/datasets/{dataset_id}/duplicate"),
    ("GET", "/api/v2/datasets/{dataset_id}/export"),
    ("POST", "/api/v2/datasets/{dataset_id}/validate"),
    ("GET", "/api/v2/datasets/{dataset_id}/versions"),
    ("GET", "/api/v2/datasets/{dataset_id}/versions/{version_no}"),
    ("GET", "/api/v2/datasets/{dataset_id}/diff"),
    ("GET", "/api/v2/datasets/{dataset_id}/market"),
    ("POST", "/api/v2/runs"),
    ("GET", "/api/v2/runs"),
    ("GET", "/api/v2/runs/{run_id}"),
    ("DELETE", "/api/v2/runs/{run_id}"),
    ("GET", "/api/v2/runs/{run_id}/result"),
    ("GET", "/api/v2/runs/{run_id}/diagnostics"),
    ("POST", "/api/v2/runs/{run_id}/cancel"),
    ("POST", "/api/v2/runs/{run_id}/rerun"),
    ("GET", "/api/v2/runs/{run_id}/explanation"),
    ("GET", "/api/v2/runs/{run_id}/constraints"),
    ("GET", "/api/v2/runs/{run_id}/bottlenecks"),
    ("POST", "/api/v2/runs/{run_id}/marginal-values"),
    ("GET", "/api/v2/runs/{run_id}/marginal-values"),
    ("GET", "/api/v2/runs/{run_id}/insights"),
    ("GET", "/api/v2/runs/{run_id}/network"),
    ("POST", "/api/v2/insights/{insight_id}/dismiss"),
    ("POST", "/api/v2/insights/{insight_id}/restore"),
    ("POST", "/api/v2/insights/{insight_id}/try"),
    ("GET", "/api/v2/analytics/dashboard"),
    ("GET", "/api/v2/analytics/runs/{run_id}/financial"),
    ("GET", "/api/v2/analytics/runs/{run_id}/operational"),
    ("GET", "/api/v2/analytics/runs/{run_id}/buyers"),
    ("GET", "/api/v2/analytics/runs/{run_id}/logistics"),
    ("GET", "/api/v2/analytics/runs/{run_id}/crops"),
    ("POST", "/api/v2/scenarios"),
    ("GET", "/api/v2/scenarios"),
    ("POST", "/api/v2/scenarios/apply-preview"),
    ("GET", "/api/v2/scenarios/{scenario_id}"),
    ("PATCH", "/api/v2/scenarios/{scenario_id}"),
    ("DELETE", "/api/v2/scenarios/{scenario_id}"),
    ("POST", "/api/v2/scenarios/{scenario_id}/duplicate"),
    ("POST", "/api/v2/scenarios/{scenario_id}/branch"),
    ("POST", "/api/v2/scenarios/{scenario_id}/changes"),
    ("PUT", "/api/v2/scenarios/{scenario_id}/changes/order"),
    ("PATCH", "/api/v2/scenarios/{scenario_id}/changes/{change_id}"),
    ("DELETE", "/api/v2/scenarios/{scenario_id}/changes/{change_id}"),
    ("POST", "/api/v2/scenarios/{scenario_id}/preview"),
    ("POST", "/api/v2/scenarios/{scenario_id}/rebase"),
    ("POST", "/api/v2/scenarios/{scenario_id}/run"),
    ("POST", "/api/v2/comparisons"),
    # phase 11 — copilot and AI text
    ("POST", "/api/v2/copilot/conversations"),
    ("GET", "/api/v2/copilot/conversations"),
    ("GET", "/api/v2/copilot/conversations/{conversation_id}"),
    ("DELETE", "/api/v2/copilot/conversations/{conversation_id}"),
    ("POST", "/api/v2/copilot/conversations/{conversation_id}/messages"),
    ("POST", "/api/v2/copilot/actions/{action_id}/confirm"),
    ("POST", "/api/v2/copilot/actions/{action_id}/reject"),
    ("GET", "/api/v2/copilot/tools"),
    ("POST", "/api/v2/runs/{run_id}/explanation/narrative"),
    ("POST", "/api/v2/comparisons/narrative"),
    ("POST", "/api/v2/scenarios/parse"),
    # phase 13 — reports
    ("POST", "/api/v2/reports"),
    ("GET", "/api/v2/reports"),
    ("GET", "/api/v2/reports/sections"),
    ("GET", "/api/v2/reports/{report_id}"),
    ("DELETE", "/api/v2/reports/{report_id}"),
    ("GET", "/api/v2/reports/{report_id}/export.json"),
    ("GET", "/api/v2/reports/{report_id}/export.csv"),
}


def test_v2_route_contract_is_frozen(client: TestClient) -> None:
    """Adding, renaming or removing a v2 route must be a deliberate change of this list."""
    spec = client.get("/openapi.json").json()
    routes = {(method.upper(), path) for path, item in spec["paths"].items() if path.startswith("/api/v2") for method in item}
    assert routes == V2_ROUTES
    for path, item in spec["paths"].items():
        if path.startswith("/api/v2"):
            for method, operation in item.items():
                assert {"200", "201", "202", "204"} & set(operation["responses"]), (method, path)

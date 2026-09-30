"""Scenarios API (phase 5): CRUD, changes, order, preview, lineage, stale + rebase, runs and cache."""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

import pytest
from fastapi.testclient import TestClient

from tests.fixtures.api import API, create_dataset, error_code, start_run

PRICE_MINUS_10 = {"op": "buyer_price", "target": "*", "params": {"mode": "relative_pct", "value": -10}}
PLUS_TRUCK = {"op": "vehicle_count", "target": "truck_3t", "params": {"mode": "delta", "value": 1}}


@pytest.fixture
def client(make_client: Callable[..., TestClient]) -> TestClient:
    return make_client()


@pytest.fixture
def dataset_id(client: TestClient) -> str:
    return create_dataset(client)


def create(client: TestClient, dataset_id: str | None = None, *, expect: int = 201, **body: Any) -> dict[str, Any]:
    body.setdefault("name", "Scenario")
    if dataset_id is not None:
        body["dataset_id"] = dataset_id
    r = client.post(f"{API}/scenarios", json=body)
    assert r.status_code == expect, r.text
    return r.json()


def vehicle_id(client: TestClient, dataset_id: str) -> str:
    return client.get(f"{API}/datasets/{dataset_id}").json()["current_version"]["payload"]["vehicle_types"][0]["id"]


def test_create_read_list_patch(client: TestClient, dataset_id: str) -> None:
    detail = create(client, dataset_id, name="Prix -10 %", description="stress", changes=[PRICE_MINUS_10], tags=["price"])
    s = detail["scenario"]
    assert s["status"] == "draft" and s["base_version_no"] == 1 and s["tags"] == ["price"] and s["parent_id"] is None
    assert [c["op"] for c in detail["changes"]] == ["buyer_price"] and detail["changes"][0]["position"] == 0
    assert detail["lineage"] == [{"id": s["id"], "name": "Prix -10 %"}] and detail["stale"] is False and detail["runs"] == []

    assert client.get(f"{API}/scenarios/{s['id']}").json() == detail
    listing = client.get(f"{API}/scenarios", params={"dataset_id": dataset_id}).json()
    assert listing["total"] == 1 and listing["items"][0]["id"] == s["id"]

    patched = client.patch(f"{API}/scenarios/{s['id']}", json={"name": "Renamed", "archived": True}).json()
    assert patched["name"] == "Renamed" and patched["status"] == "archived"
    assert client.get(f"{API}/scenarios", params={"status": "archived"}).json()["total"] == 1
    assert client.patch(f"{API}/scenarios/{s['id']}", json={"archived": False}).json()["status"] == "draft"


def test_invalid_change_is_rejected_with_its_index(client: TestClient, dataset_id: str) -> None:
    payload = client.get(f"{API}/datasets/{dataset_id}").json()["current_version"]["payload"]
    removals = [{"op": "remove_buyer", "target": b["id"]} for b in payload["buyers"]]
    r = client.post(f"{API}/scenarios", json={"name": "x", "dataset_id": dataset_id, "changes": removals})
    assert r.status_code == 422 and error_code(r) == "SCENARIO_APPLY_ERROR"
    details = r.json()["error"]["details"]
    assert details["change_index"] == len(removals) - 1 and details["reason"] == "at least one buyer must remain"
    assert client.get(f"{API}/scenarios").json()["total"] == 0  # nothing saved

    r = client.post(f"{API}/scenarios", json={"name": "x", "dataset_id": dataset_id, "changes": [{"op": "teleport"}]})
    assert r.status_code == 422 and error_code(r) == "VALIDATION_ERROR"


def test_changes_crud_and_order(client: TestClient, dataset_id: str) -> None:
    truck = {**PLUS_TRUCK, "target": vehicle_id(client, dataset_id)}
    sid = create(client, dataset_id)["scenario"]["id"]
    detail = client.post(f"{API}/scenarios/{sid}/changes", json=PRICE_MINUS_10).json()
    detail = client.post(f"{API}/scenarios/{sid}/changes", json=truck).json()
    first, second = detail["changes"]
    assert (first["op"], second["op"], second["position"]) == ("buyer_price", "vehicle_count", 1)

    detail = client.put(f"{API}/scenarios/{sid}/changes/order", json={"ids": [second["id"], first["id"]]}).json()
    assert [c["op"] for c in detail["changes"]] == ["vehicle_count", "buyer_price"]
    r = client.put(f"{API}/scenarios/{sid}/changes/order", json={"ids": [first["id"]]})
    assert r.status_code == 422 and error_code(r) == "INVALID_ORDER"

    detail = client.patch(f"{API}/scenarios/{sid}/changes/{first['id']}", json={"params": {"mode": "relative_pct", "value": -20}, "note": "worse"}).json()
    changed = next(c for c in detail["changes"] if c["id"] == first["id"])
    assert changed["params"]["value"] == -20 and changed["note"] == "worse"
    r = client.patch(f"{API}/scenarios/{sid}/changes/{first['id']}", json={"params": {"mode": "relative_pct", "value": -200}})
    assert r.status_code == 422 and error_code(r) == "SCENARIO_APPLY_ERROR"  # price would be negative; nothing saved
    detail = client.patch(f"{API}/scenarios/{sid}/changes/{first['id']}", json={"enabled": False}).json()
    assert next(c for c in detail["changes"] if c["id"] == first["id"])["enabled"] is False

    detail = client.delete(f"{API}/scenarios/{sid}/changes/{second['id']}").json()
    assert [(c["op"], c["position"]) for c in detail["changes"]] == [("buyer_price", 0)]
    assert client.delete(f"{API}/scenarios/{sid}/changes/nope").status_code == 404


def test_preview_is_computed_by_the_backend_r7(client: TestClient, dataset_id: str) -> None:
    """R7: '-10 %' is a typed change; the backend computes every new price."""
    base = client.get(f"{API}/datasets/{dataset_id}").json()["current_version"]["payload"]["buyers"]
    sid = create(client, dataset_id, changes=[PRICE_MINUS_10])["scenario"]["id"]
    preview = client.post(f"{API}/scenarios/{sid}/preview").json()
    assert [b["price_per_kg"] for b in preview["effective_payload"]["buyers"]] == [round(b["price_per_kg"] * 0.9, 6) for b in base]
    assert preview["validation"]["errors"] == [] and preview["base_version_no"] == 1
    assert {d["path"] for d in preview["diff"]} >= {f"buyers[{b['id']}].price_per_kg" for b in base}
    assert preview["applied"][0]["summary"].startswith("price_per_kg")


def test_apply_preview_stores_nothing(client: TestClient, dataset_id: str) -> None:
    r = client.post(f"{API}/scenarios/apply-preview", json={"dataset_id": dataset_id, "changes": [PRICE_MINUS_10]})
    assert r.status_code == 200 and len(r.json()["applied"]) == 1
    assert client.get(f"{API}/scenarios").json()["total"] == 0
    bad = client.post(f"{API}/scenarios/apply-preview", json={"dataset_id": dataset_id, "changes": [{"op": "remove_buyer", "target": "ghost"}]})
    assert bad.status_code == 422 and bad.json()["error"]["details"]["change_index"] == 0


def test_branch_chain_keeps_its_lineage_r8(client: TestClient, dataset_id: str) -> None:
    """R8 (audit): chained What-Ifs lost the previous data. A child applies its parent's changes first."""
    truck_id = vehicle_id(client, dataset_id)
    parent = create(client, dataset_id, name="A", changes=[PRICE_MINUS_10])["scenario"]
    child = client.post(f"{API}/scenarios/{parent['id']}/branch", json={"name": "A1"}).json()
    assert child["scenario"]["parent_id"] == parent["id"] and [x["name"] for x in child["lineage"]] == ["A", "A1"]
    child_id = child["scenario"]["id"]
    client.post(f"{API}/scenarios/{child_id}/changes", json={**PLUS_TRUCK, "target": truck_id})
    grandchild = client.post(f"{API}/scenarios/{child_id}/branch", json={"name": "A1a"}).json()
    assert [x["name"] for x in grandchild["lineage"]] == ["A", "A1", "A1a"]

    preview = client.post(f"{API}/scenarios/{grandchild['scenario']['id']}/preview").json()
    assert [(a["op"], a["scenario_id"]) for a in preview["applied"]] == [("buyer_price", parent["id"]), ("vehicle_count", child_id)]

    run = client.post(f"{API}/scenarios/{grandchild['scenario']['id']}/run?wait=15").json()
    assert run["status"] == "succeeded" and [a["op"] for a in run["applied_changes"]] == ["buyer_price", "vehicle_count"]
    assert run["scenario_id"] == grandchild["scenario"]["id"]


def test_create_child_with_parent_id(client: TestClient, dataset_id: str) -> None:
    parent = create(client, dataset_id, changes=[PRICE_MINUS_10])["scenario"]
    child = create(client, name="child", parent_id=parent["id"], changes=[{"op": "harvest_quantity", "target": "*", "params": {"mode": "relative_pct", "value": 20}}])
    assert child["scenario"]["dataset_id"] == dataset_id and len(child["lineage"]) == 2
    other = create_dataset(client, template="tunisia_dates")
    r = client.post(f"{API}/scenarios", json={"name": "x", "dataset_id": other, "parent_id": parent["id"]})
    assert r.status_code == 422 and error_code(r) == "SCENARIO_PARENT_MISMATCH"


def test_duplicate_and_delete(client: TestClient, dataset_id: str) -> None:
    parent = create(client, dataset_id, name="A", changes=[PRICE_MINUS_10])["scenario"]
    copy = client.post(f"{API}/scenarios/{parent['id']}/duplicate", json={}).json()
    assert copy["scenario"]["name"] == "A (copy)" and [c["op"] for c in copy["changes"]] == ["buyer_price"]
    assert copy["changes"][0]["id"] != client.get(f"{API}/scenarios/{parent['id']}").json()["changes"][0]["id"]

    child = client.post(f"{API}/scenarios/{parent['id']}/branch", json={"name": "A1"}).json()["scenario"]
    r = client.delete(f"{API}/scenarios/{parent['id']}")
    assert r.status_code == 409 and error_code(r) == "HAS_CHILDREN"
    run = client.post(f"{API}/scenarios/{child['id']}/run?wait=15").json()
    assert client.delete(f"{API}/scenarios/{parent['id']}", params={"cascade": True}).status_code == 204
    assert client.get(f"{API}/scenarios/{child['id']}").status_code == 404
    kept = client.get(f"{API}/runs/{run['id']}").json()
    assert kept["status"] == "succeeded" and kept["scenario_id"] is None  # runs keep their frozen data


def test_stale_and_rebase(client: TestClient, dataset_id: str) -> None:
    sid = create(client, dataset_id, changes=[PRICE_MINUS_10])["scenario"]["id"]
    dataset = client.get(f"{API}/datasets/{dataset_id}").json()
    payload = dataset["current_version"]["payload"]
    payload["harvest_lots"][0]["quantity_kg"] += 1000
    r = client.put(f"{API}/datasets/{dataset_id}/payload", json={"payload": payload}, headers={"If-Match": '"1"'})
    assert r.status_code == 200

    detail = client.get(f"{API}/scenarios/{sid}").json()
    assert detail["stale"] is True and detail["scenario"]["status"] == "stale" and detail["current_version_no"] == 2
    stale_run = client.post(f"{API}/scenarios/{sid}/run?wait=15").json()  # still runs on its base version
    assert stale_run["version_no"] == 1

    rebased = client.post(f"{API}/scenarios/{sid}/rebase").json()
    assert rebased["stale"] is False and rebased["scenario"]["base_version_no"] == 2 and rebased["scenario"]["status"] == "draft"
    run = client.post(f"{API}/scenarios/{sid}/run?wait=15").json()
    assert run["version_no"] == 2 and run["headline"]["realized_profit"] != stale_run["headline"]["realized_profit"]
    assert client.get(f"{API}/scenarios/{sid}").json()["scenario"]["status"] == "ready"


def test_rebase_fails_when_a_change_no_longer_applies(client: TestClient, dataset_id: str) -> None:
    dataset = client.get(f"{API}/datasets/{dataset_id}").json()
    payload = dataset["current_version"]["payload"]
    gone = payload["buyers"][-1]["id"]
    sid = create(client, dataset_id, changes=[{"op": "buyer_price", "target": gone, "params": {"mode": "delta", "value": 0.1}}])["scenario"]["id"]
    payload["buyers"] = payload["buyers"][:-1]
    payload["routes"] = [r for r in payload["routes"] if r["buyer_id"] != gone]
    client.put(f"{API}/datasets/{dataset_id}/payload", json={"payload": payload}, headers={"If-Match": '"1"'})
    r = client.post(f"{API}/scenarios/{sid}/rebase")
    assert r.status_code == 422 and error_code(r) == "SCENARIO_APPLY_ERROR"
    assert client.get(f"{API}/scenarios/{sid}").json()["scenario"]["base_version_no"] == 1


def test_scenario_runs_use_the_cache(client: TestClient, dataset_id: str) -> None:
    baseline = start_run(client, dataset_id)
    empty = create(client, dataset_id, name="no change")["scenario"]["id"]
    r = client.post(f"{API}/scenarios/{empty}/run")
    assert r.status_code == 200 and r.json()["id"] == baseline["id"] and r.json()["cache_hit"] is True
    assert client.get(f"{API}/scenarios/{empty}").json()["scenario"]["latest_run_id"] == baseline["id"]

    sid = create(client, dataset_id, changes=[PRICE_MINUS_10])["scenario"]["id"]
    first = client.post(f"{API}/scenarios/{sid}/run?wait=15").json()
    twin = create(client, dataset_id, name="twin", changes=[PRICE_MINUS_10])["scenario"]["id"]
    second = client.post(f"{API}/scenarios/{twin}/run").json()
    assert second["id"] == first["id"] and second["cache_hit"] is True
    assert first["effective_input_hash"] != baseline["effective_input_hash"]
    runs = client.get(f"{API}/runs", params={"scenario_id": sid}).json()
    assert runs["total"] == 1 and client.get(f"{API}/scenarios/{sid}").json()["runs"][0]["id"] == first["id"]


def test_scenario_run_errors(client: TestClient) -> None:
    r = client.post(f"{API}/scenarios/nope/run")
    assert r.status_code == 404
    r = client.post(f"{API}/runs", json={"scenario_id": "nope"})
    assert r.status_code == 404

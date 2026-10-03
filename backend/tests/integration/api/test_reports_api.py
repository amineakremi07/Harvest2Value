"""Frozen reports: the snapshot never changes when data, scenarios or runs change; CSV / JSON exports."""

from __future__ import annotations

import csv
import io
from collections.abc import Callable

import pytest
from fastapi.testclient import TestClient

from tests.fixtures.api import API, create_dataset, error_code, start_run

ALL = ["summary", "financial", "operational", "buyers", "logistics", "crops", "insights", "comparison"]


@pytest.fixture
def client(make_client: Callable[..., TestClient]) -> TestClient:
    return make_client()


def two_runs(client: TestClient) -> tuple[str, str, str]:
    dataset_id = create_dataset(client, template="tunisia_olives")
    base = start_run(client, dataset_id)
    other = start_run(client, dataset_id, config={"objective": "revenue"}, use_cache=False)
    assert base["status"] == other["status"] == "succeeded"
    return dataset_id, base["id"], other["id"]


def test_report_is_a_frozen_copy(client: TestClient) -> None:
    dataset_id, base, other = two_runs(client)
    r = client.post(f"{API}/reports", json={"title": "Bilan", "run_id": base, "compare_run_ids": [other], "sections": ALL})
    assert r.status_code == 201, r.text
    created = r.json()
    assert set(created["snapshot"]["sections"]) == set(ALL) and created["snapshot"]["narrative"] is None
    assert created["snapshot"]["run"]["dataset_name"] and created["snapshot"]["currency"] == "TND"

    # Change everything the report was computed from.
    payload = client.get(f"{API}/datasets/{dataset_id}").json()["current_version"]["payload"]
    payload["buyers"][0]["price_per_kg"] = payload["buyers"][0]["price_per_kg"] * 3
    assert client.put(f"{API}/datasets/{dataset_id}/payload", json={"payload": payload}, headers={"If-Match": '"1"'}).status_code == 200
    start_run(client, dataset_id)
    assert client.delete(f"{API}/runs/{other}").status_code == 204
    assert client.delete(f"{API}/runs/{base}").status_code == 204

    again = client.get(f"{API}/reports/{created['id']}").json()
    assert again["snapshot"] == created["snapshot"] and again["snapshot_hash"] == created["snapshot_hash"]
    listed = client.get(f"{API}/reports").json()
    assert listed["total"] == 1 and listed["items"][0]["sections"] == ALL


def test_csv_export_per_section_and_json_export(client: TestClient) -> None:
    _dataset_id, base, other = two_runs(client)
    report = client.post(f"{API}/reports", json={"title": "Export", "run_id": base, "compare_run_ids": [other], "sections": ["summary", "buyers", "comparison"]}).json()

    r = client.get(f"{API}/reports/{report['id']}/export.csv", params={"section": "buyers"})
    assert r.status_code == 200 and r.headers["content-type"].startswith("text/csv")
    assert 'filename="export-buyers-buyers.csv"' in r.headers["content-disposition"]
    text = r.content.decode("utf-8")
    assert text.startswith("﻿")
    rows = list(csv.DictReader(io.StringIO(text.lstrip("﻿"))))
    assert len(rows) == 4 and "buyer_id" in rows[0] and "sold_kg" in rows[0]

    kpis = list(csv.DictReader(io.StringIO(client.get(f"{API}/reports/{report['id']}/export.csv", params={"section": "comparison", "table": "kpis"}).content.decode("utf-8").lstrip("﻿"))))
    assert any(row["kpi"] == "realized_profit" for row in kpis)

    assert error_code(client.get(f"{API}/reports/{report['id']}/export.csv", params={"section": "logistics"})) == "NOT_FOUND"
    assert error_code(client.get(f"{API}/reports/{report['id']}/export.csv", params={"section": "buyers", "table": "nope"})) == "NOT_FOUND"

    exported = client.get(f"{API}/reports/{report['id']}/export.json")
    assert exported.status_code == 200 and "attachment" in exported.headers["content-disposition"]
    assert exported.json()["snapshot"] == report["snapshot"]


def test_invalid_specs(client: TestClient) -> None:
    _dataset_id, base, _other = two_runs(client)
    r = client.post(f"{API}/reports", json={"title": "X", "run_id": base, "sections": ["comparison"]})
    assert r.status_code == 422
    r = client.post(f"{API}/reports", json={"title": "X", "run_id": base, "sections": ["summary", "summary"]})
    assert r.status_code == 422
    assert client.post(f"{API}/reports", json={"title": "X", "run_id": "missing"}).status_code == 404
    assert client.get(f"{API}/reports/sections").json()["comparison"] == ["kpis", "buyers", "notable_changes"]


def test_delete_report(client: TestClient) -> None:
    _dataset_id, base, _other = two_runs(client)
    report = client.post(f"{API}/reports", json={"title": "X", "run_id": base}).json()
    assert client.delete(f"{API}/reports/{report['id']}").status_code == 204
    assert client.get(f"{API}/reports/{report['id']}").status_code == 404


def test_csv_cells_cannot_inject_formulas() -> None:
    from app.services.reports import rows_to_csv

    out = rows_to_csv([{"name": "=HYPERLINK(\"x\")", "delta": "-12.5"}]).decode("utf-8")
    assert "'=HYPERLINK" in out and ",-12.5" in out

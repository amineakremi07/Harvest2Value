"""Dataset registry API: lifecycle, versions and optimistic concurrency, import/export, validation."""

from __future__ import annotations

import copy
import io
import json
import zipfile
from collections.abc import Callable

import pytest
from fastapi.testclient import TestClient

from tests.fixtures.builders import TEMPLATES, V1_FIXTURES, load_json

API = "/api/v2"


@pytest.fixture
def client(make_client: Callable[..., TestClient]) -> TestClient:
    return make_client()


def create_from_template(client: TestClient, key: str = "tunisia_olives", **kw) -> dict:
    r = client.post(f"{API}/datasets", json={"template_key": key, **kw})
    assert r.status_code == 201, r.text
    return r.json()


def error_code(r) -> str:
    return r.json()["error"]["code"]


def test_templates_are_listed(client: TestClient) -> None:
    templates = client.get(f"{API}/templates").json()
    assert sorted(t["key"] for t in templates) == sorted(p.stem for p in TEMPLATES)
    olives = next(t for t in templates if t["key"] == "tunisia_olives")
    assert olives["harvest_kg"] == 12000 and olives["lot_count"] == 3 and olives["buyer_count"] == 4


def test_unknown_template_is_404(client: TestClient) -> None:
    r = client.post(f"{API}/datasets", json={"template_key": "atlantis"})
    assert r.status_code == 404 and error_code(r) == "NOT_FOUND"


def test_create_requires_exactly_one_source(client: TestClient) -> None:
    r = client.post(f"{API}/datasets", json={"name": "x"})
    assert r.status_code == 422 and error_code(r) == "VALIDATION_ERROR"


def test_full_lifecycle(client: TestClient) -> None:
    detail = create_from_template(client, name="My olives")
    dataset_id = detail["dataset"]["id"]
    assert detail["dataset"]["current_version_no"] == 1 and detail["dataset"]["is_valid"] is True
    assert detail["dataset"]["source"] == "template" and detail["current_version"]["payload"]["currency"] == "TND"

    # read
    r = client.get(f"{API}/datasets/{dataset_id}")
    assert r.status_code == 200 and r.headers["etag"] == '"1"'
    listing = client.get(f"{API}/datasets").json()
    assert listing["total"] == 1 and listing["items"][0]["harvest_kg"] == 12000

    # new version with If-Match
    payload = copy.deepcopy(detail["current_version"]["payload"])
    payload["buyers"][0]["price_per_kg"] = 2.6
    r = client.put(f"{API}/datasets/{dataset_id}/payload", json={"payload": payload, "note": "price update"}, headers={"If-Match": '"1"'})
    assert r.status_code == 200, r.text
    assert r.json()["version_no"] == 2 and r.headers["etag"] == '"2"'
    assert client.get(f"{API}/datasets/{dataset_id}").json()["current_version"]["payload"]["buyers"][0]["price_per_kg"] == 2.6

    # versions + diff
    versions = client.get(f"{API}/datasets/{dataset_id}/versions").json()
    assert [v["version_no"] for v in versions["items"]] == [2, 1]
    assert client.get(f"{API}/datasets/{dataset_id}/versions/1").json()["payload"]["buyers"][0]["price_per_kg"] == 2.4
    diff = client.get(f"{API}/datasets/{dataset_id}/diff").json()
    assert (diff["from_version"], diff["to_version"]) == (1, 2)
    assert diff["changes"] == [{"path": "buyers[buyer_tn_01].price_per_kg", "kind": "changed", "before": 2.4, "after": 2.6}]

    # metadata
    r = client.patch(f"{API}/datasets/{dataset_id}", json={"name": "Renamed", "archived": True})
    assert r.json()["name"] == "Renamed" and r.json()["archived"] is True
    assert client.get(f"{API}/datasets").json()["total"] == 0
    assert client.get(f"{API}/datasets", params={"archived": "true"}).json()["total"] == 1

    # delete
    assert client.delete(f"{API}/datasets/{dataset_id}").status_code == 204
    r = client.get(f"{API}/datasets/{dataset_id}")
    assert r.status_code == 404 and error_code(r) == "NOT_FOUND"
    assert client.get(f"{API}/datasets/{dataset_id}/versions/1").status_code == 404


def test_stale_if_match_is_409_version_conflict(client: TestClient) -> None:
    detail = create_from_template(client)
    dataset_id, payload = detail["dataset"]["id"], detail["current_version"]["payload"]
    assert client.put(f"{API}/datasets/{dataset_id}/payload", json={"payload": payload}, headers={"If-Match": "1"}).status_code == 200

    r = client.put(f"{API}/datasets/{dataset_id}/payload", json={"payload": payload}, headers={"If-Match": "1"})
    assert r.status_code == 409 and error_code(r) == "VERSION_CONFLICT"
    assert r.json()["error"]["details"]["current_version_no"] == 2


def test_missing_if_match_is_428(client: TestClient) -> None:
    detail = create_from_template(client)
    r = client.put(f"{API}/datasets/{detail['dataset']['id']}/payload", json={"payload": detail["current_version"]["payload"]})
    assert r.status_code == 428 and error_code(r) == "PRECONDITION_REQUIRED"


def test_invalid_payload_update_is_422(client: TestClient) -> None:
    detail = create_from_template(client)
    payload = copy.deepcopy(detail["current_version"]["payload"])
    payload["routes"].pop()
    r = client.put(f"{API}/datasets/{detail['dataset']['id']}/payload", json={"payload": payload}, headers={"If-Match": "1"})
    assert r.status_code == 422 and "missing route" in json.dumps(r.json())


def test_duplicate(client: TestClient) -> None:
    detail = create_from_template(client, name="Base")
    r = client.post(f"{API}/datasets/{detail['dataset']['id']}/duplicate", json={})
    assert r.status_code == 201
    copy_ = r.json()
    assert copy_["dataset"]["name"] == "Base (copy)" and copy_["dataset"]["source"] == "duplicate"
    assert copy_["dataset"]["id"] != detail["dataset"]["id"]
    assert copy_["current_version"]["content_hash"] == detail["current_version"]["content_hash"]


@pytest.mark.parametrize("path", V1_FIXTURES, ids=lambda p: p.stem)
def test_import_v1_file(client: TestClient, path) -> None:
    r = client.post(f"{API}/datasets/import", files={"file": (path.name, path.read_bytes(), "application/json")})
    assert r.status_code == 201, r.text
    body = r.json()
    assert body["source_format"] == "v1"
    codes = {a["code"] for a in body["assumptions"]}
    assert "V1_COMPATIBILITY_MODE" in codes
    stored_assumptions = {a["code"] for a in body["dataset"]["current_version"]["validation"]["assumptions"]}
    assert codes <= stored_assumptions
    assert body["dataset"]["dataset"]["source"] == "import" and body["dataset"]["dataset"]["name"] == path.stem


def test_import_v2_file_with_custom_name(client: TestClient) -> None:
    path = TEMPLATES[0]
    r = client.post(f"{API}/datasets/import", files={"file": (path.name, path.read_bytes())}, data={"name": "Imported v2"})
    assert r.status_code == 201
    body = r.json()
    assert body["source_format"] == "v2" and body["assumptions"] == []
    assert body["dataset"]["dataset"]["name"] == "Imported v2"
    assert body["dataset"]["current_version"]["payload"] == load_json(path)


@pytest.mark.parametrize(
    ("filename", "content", "status", "code"),
    [
        ("bad.json", b"{not json", 422, "IMPORT_PARSE_ERROR"),
        ("unknown.json", b'{"hello": 1}', 422, "IMPORT_PARSE_ERROR"),
        ("broken_v2.json", b'{"schema_version": "2.0", "producer": {}}', 422, "DATASET_INVALID"),
        ("broken_v1.json", b'{"producer": {"harvest_kg": -1}, "crop": {}, "buyers": [], "logistics": {}}', 422, "IMPORT_PARSE_ERROR"),
        ("data.csv", b"a,b\n1,2\n", 415, "UNSUPPORTED_IMPORT_FORMAT"),
    ],
)
def test_import_errors(client: TestClient, filename: str, content: bytes, status: int, code: str) -> None:
    r = client.post(f"{API}/datasets/import", files={"file": (filename, content)})
    assert r.status_code == status and error_code(r) == code
    assert client.get(f"{API}/datasets").json()["total"] == 0  # nothing half-created


def test_export_json_and_csv(client: TestClient) -> None:
    detail = create_from_template(client, name="Olives")
    dataset_id = detail["dataset"]["id"]

    r = client.get(f"{API}/datasets/{dataset_id}/export")
    assert r.status_code == 200 and r.headers["content-type"].startswith("application/json")
    assert 'filename="Olives_v1.json"' in r.headers["content-disposition"]
    assert r.json() == detail["current_version"]["payload"]

    r = client.get(f"{API}/datasets/{dataset_id}/export", params={"format": "csv"})
    assert r.headers["content-type"] == "application/zip"
    with zipfile.ZipFile(io.BytesIO(r.content)) as zf:
        assert sorted(zf.namelist()) == sorted(
            ["dataset.csv", "producer.csv", "crops.csv", "harvest_lots.csv", "buyers.csv", "storage_facilities.csv", "vehicle_types.csv", "routes.csv"]
        )
        buyers = zf.read("buyers.csv").decode("utf-8").splitlines()
    assert buyers[0].startswith("id,name,location,crop_ids,price_per_kg") and len(buyers) == 5

    assert client.get(f"{API}/datasets/{dataset_id}/export", params={"version": 9}).status_code == 404


def test_validate_current_and_draft(client: TestClient) -> None:
    detail = create_from_template(client)
    dataset_id = detail["dataset"]["id"]
    current = client.post(f"{API}/datasets/{dataset_id}/validate").json()
    assert current["errors"] == []

    draft = copy.deepcopy(detail["current_version"]["payload"])
    draft["harvest_lots"][0]["quantity_kg"] = -3
    report = client.post(f"{API}/datasets/{dataset_id}/validate", json={"payload": draft}).json()
    assert report["errors"][0]["code"] == "SCHEMA_ERROR" and report["errors"][0]["path"] == "harvest_lots.0.quantity_kg"

    draft = copy.deepcopy(detail["current_version"]["payload"])
    for v in draft["vehicle_types"]:
        v["count"] = 0
    report = client.post(f"{API}/datasets/{dataset_id}/validate", json={"payload": draft}).json()
    assert "NO_VEHICLE" in {e["code"] for e in report["errors"]}
    # a draft is never saved
    assert client.get(f"{API}/datasets/{dataset_id}").json()["dataset"]["current_version_no"] == 1


def test_business_invalid_payload_is_saved_but_flagged(client: TestClient) -> None:
    payload = load_json(TEMPLATES[0])
    for v in payload["vehicle_types"]:
        v["count"] = 0
    r = client.post(f"{API}/datasets", json={"name": "No trucks", "payload": payload})
    assert r.status_code == 201
    assert r.json()["dataset"]["is_valid"] is False
    assert "NO_VEHICLE" in {e["code"] for e in r.json()["current_version"]["validation"]["errors"]}


def test_datasets_survive_an_app_restart(make_client: Callable[..., TestClient], tmp_path) -> None:
    url = f"sqlite:///{(tmp_path / 'persist.db').as_posix()}"
    first = make_client(database_url=url)
    dataset_id = create_from_template(first)["dataset"]["id"]
    second = make_client(database_url=url)
    assert second.get(f"{API}/datasets/{dataset_id}").status_code == 200

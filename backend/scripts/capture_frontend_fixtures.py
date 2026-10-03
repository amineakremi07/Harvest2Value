"""Capture real /api/v2 responses as frontend test fixtures (frontend/test/fixtures/*.json).

Needs a running backend:  .venv/Scripts/python scripts/capture_frontend_fixtures.py [base_url]
"""

from __future__ import annotations

import json
import sys
import time
from pathlib import Path
from typing import Any

import httpx

OUT_DIR = Path(__file__).resolve().parents[2] / "frontend" / "test" / "fixtures"


def main(base_url: str = "http://localhost:8000/api/v2") -> None:
    client = httpx.Client(base_url=base_url, timeout=60)

    def dump(name: str, obj: Any) -> None:
        (OUT_DIR / f"{name}.json").write_text(json.dumps(obj, ensure_ascii=False, indent=1), encoding="utf-8")

    def wait(run: dict[str, Any]) -> dict[str, Any]:
        while run["status"] in ("queued", "running"):
            time.sleep(0.5)
            run = client.get(f"/runs/{run['id']}").json()
        return run

    dump("meta", client.get("/meta").json())
    dataset = client.post("/datasets", json={"template_key": "tunisia_olives", "name": "fixture olives"}).json()
    dataset_id = dataset["dataset"]["id"]
    dump("olives_payload", dataset["current_version"]["payload"])

    config = {"objective": "profit"}
    base = wait(client.post("/runs", params={"wait": 15}, json={"dataset_id": dataset_id, "config": config, "label": "Référence", "use_cache": False}).json())
    dump("olives_run", base)
    result = client.get(f"/runs/{base['id']}/result").json()
    result["constraints"] = result["constraints"][:3]  # keep the fixture small
    result["sensitivity"] = None
    dump("olives_result", result)

    change = {"op": "buyer_price", "target": "*", "params": {"mode": "relative_pct", "value": -10}}
    scenario = client.post("/scenarios", json={"name": "Prix -10 %", "dataset_id": dataset_id, "changes": [change]}).json()
    scenario_id = scenario["scenario"]["id"]
    run = wait(client.post(f"/scenarios/{scenario_id}/run", params={"wait": 15}, json={"config": config, "label": "Prix -10 %"}).json())
    dump("olives_comparison", client.post("/comparisons", json={"baseline_run_id": base["id"], "run_ids": [run["id"]]}).json())
    dump("olives_scenario", client.get(f"/scenarios/{scenario_id}").json())
    dump("olives_preview", client.post(f"/scenarios/{scenario_id}/preview").json())
    # Explainability (after the probes, so cards carry measured effects) and network.
    client.post(f"/runs/{base['id']}/marginal-values", params={"wait": 15})
    explanation = client.get(f"/runs/{base['id']}/explanation").json()
    explanation["binding"] = explanation["binding"][:20]  # keep the fixture small
    dump("olives_explanation", explanation)
    marginal = client.get(f"/runs/{base['id']}/marginal-values").json()
    marginal["duals"] = marginal["duals"][:15]
    dump("olives_marginal_values", marginal)
    dump("olives_network", client.get(f"/runs/{base['id']}/network").json())
    dump("olives_network_day0", client.get(f"/runs/{base['id']}/network", params={"day": 0}).json())

    # Wheat: an insight with a suggested change (DEMAND_BOTTLENECK).
    wheat = client.post("/datasets", json={"template_key": "tunisia_wheat", "name": "fixture wheat"}).json()
    wheat_run = wait(client.post("/runs", params={"wait": 15}, json={"dataset_id": wheat["dataset"]["id"], "config": config, "use_cache": False}).json())
    dump("wheat_insights", client.get(f"/runs/{wheat_run['id']}/insights").json())
    capture_analytics_and_report(client, base["id"], run["id"], dump)
    print(f"Wrote fixtures to {OUT_DIR}")


def capture_analytics_and_report(client: httpx.Client, base_id: str, other_id: str, dump: Any) -> None:
    """Phases 12-13: the five analytics sections of the base run and a frozen report."""
    for section in ("financial", "operational", "buyers", "logistics", "crops"):
        dump(f"olives_analytics_{section}", client.get(f"/analytics/runs/{base_id}/{section}").json())
    spec = {
        "title": "Rapport olives",
        "run_id": base_id,
        "compare_run_ids": [other_id],
        "sections": ["summary", "financial", "operational", "buyers", "logistics", "crops", "insights", "comparison"],
    }
    dump("olives_report", client.post("/reports", json=spec).json())


if __name__ == "__main__":
    main(*sys.argv[1:])

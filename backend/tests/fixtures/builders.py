"""Terse builders for small v2 payloads: every field not given gets a neutral default
(zero costs, zero distance, one big truck, no time limit), so a test states only what matters."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from app.domain.dataset import DatasetPayload

REPO_DIR = Path(__file__).resolve().parents[3]
V1_FIXTURES = sorted((REPO_DIR / "data").glob("tunisia_*.json"))
TEMPLATES = sorted((REPO_DIR / "data" / "templates").glob("*.json"))


def load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def crop(**kw: Any) -> dict[str, Any]:
    return {
        "id": "c",
        "name": "Crop",
        "type": "semi_perishable",
        "reference_price_per_kg": 1.0,
        "shelf_life_ambient_days": 1,
        **kw,
    }


def lot(id: str, kg: float, day: int = 0, crop_id: str = "c") -> dict[str, Any]:
    return {"id": id, "crop_id": crop_id, "quantity_kg": kg, "available_day": day}


def buyer(id: str, price: float = 1.0, demand: float = 1e6, **kw: Any) -> dict[str, Any]:
    return {
        "id": id,
        "name": id.title(),
        "location": "Town",
        "crop_ids": ["c"],
        "price_per_kg": price,
        "max_demand_kg": demand,
        **kw,
    }


def storage(id: str = "store", capacity: float = 1e6, cost: float = 0.0, refrigerated: bool = False) -> dict[str, Any]:
    return {"id": id, "name": id.title(), "capacity_kg": capacity, "refrigerated": refrigerated, "cost_per_kg_per_day": cost}


def vehicle(id: str = "truck", capacity: float = 1e6, count: int = 1, **kw: Any) -> dict[str, Any]:
    return {
        "id": id,
        "name": id.title(),
        "capacity_kg": capacity,
        "count": count,
        "fixed_cost_per_trip": 0.0,
        "cost_per_km": 0.0,
        "hours_per_day": None,
        "loading_hours_per_trip": 0.0,
        **kw,
    }


def route(buyer_id: str, distance: float = 0.0, **kw: Any) -> dict[str, Any]:
    return {"buyer_id": buyer_id, "distance_km": distance, "road_factor_override": 1.0, **kw}


def payload_dict(
    *,
    lots: list[dict[str, Any]],
    buyers: list[dict[str, Any]],
    crops: list[dict[str, Any]] | None = None,
    storage_facilities: list[dict[str, Any]] | None = None,
    vehicles: list[dict[str, Any]] | None = None,
    routes: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    known_routes = {r["buyer_id"] for r in routes or []}
    return {
        "schema_version": "2.0",
        "currency": "TND",
        "producer": {"name": "Test Farm", "region": "Sfax", "country": "Tunisia"},
        "crops": crops or [crop()],
        "harvest_lots": lots,
        "buyers": buyers,
        "storage_facilities": storage_facilities or [],
        "vehicle_types": vehicles or [vehicle()],
        "routes": (routes or []) + [route(b["id"]) for b in buyers if b["id"] not in known_routes],
    }


def make_payload(**kw: Any) -> DatasetPayload:
    return DatasetPayload.model_validate(payload_dict(**kw))

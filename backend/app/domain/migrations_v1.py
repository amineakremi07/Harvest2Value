"""Convert a v1 dataset (shape of `tests/fixtures/v1/tunisia_olives.json`) into a v2 payload.

Compatibility mode (plan §10): a single lot on day 0 and a 1-day ambient shelf life, so
the automatic horizon is 1 day and the plan is "sell today or lose it"; one vehicle type
with `count = available_vehicles`, one trip each per day and no driving-time limit
(capacity = vehicles x capacity, as in v1); v1 per-kg-per-km transport costs kept as-is.
Every default applied is returned as an assumption.
"""

from __future__ import annotations

import re
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, ValidationError

from .dataset import (
    Buyer,
    Crop,
    DatasetPayload,
    HarvestLot,
    Producer,
    Route,
    StorageFacility,
    VehicleType,
)
from .enums import CropType, RoadCondition
from .validation import ValidationIssue


class V1FormatError(ValueError):
    """The document is not a valid v1 dataset."""


class _V1Producer(BaseModel):
    model_config = ConfigDict(extra="ignore")
    id: str | None = None
    name: str
    region: str
    country: str
    harvest_kg: float = Field(gt=0)
    storage_capacity_kg: float = Field(ge=0)
    storage_cost_per_kg_per_day: float | None = Field(default=None, ge=0)
    shelf_life_days: int = Field(ge=1)


class _V1Crop(BaseModel):
    model_config = ConfigDict(extra="ignore")
    name: str
    type: CropType
    unit: str = "kg"


class _V1Buyer(BaseModel):
    model_config = ConfigDict(extra="ignore")
    id: str
    name: str
    location: str
    max_demand_kg: float = Field(gt=0)
    price_per_kg: float = Field(ge=0)
    distance_km: float | None = Field(default=None, ge=0)
    transport_cost_per_kg_per_km: float | None = Field(default=None, ge=0)


class _V1Logistics(BaseModel):
    model_config = ConfigDict(extra="ignore")
    available_vehicles: int = Field(ge=1)
    vehicle_capacity_kg: float = Field(gt=0)
    refrigerated_required: bool = False
    road_condition: RoadCondition = RoadCondition.FAIR


class _V1Dataset(BaseModel):
    model_config = ConfigDict(extra="ignore")
    producer: _V1Producer
    crop: _V1Crop
    buyers: list[_V1Buyer] = Field(min_length=1)
    logistics: _V1Logistics


V1_STORAGE_COST_DEFAULT = 0.05  # v1 schema default


def detect_format(document: Any) -> Literal["v1", "v2", "unknown"]:
    if not isinstance(document, dict):
        return "unknown"
    if "schema_version" in document:
        return "v2"
    producer = document.get("producer")
    if isinstance(producer, dict) and "harvest_kg" in producer and "crop" in document:
        return "v1"
    return "unknown"


def _slug(text: str) -> str:
    slug = re.sub(r"[^A-Za-z0-9_.\-]+", "_", text.strip().lower()).strip("_")
    return slug[:64] or "crop"


def migrate_v1_to_v2(document: dict[str, Any]) -> tuple[DatasetPayload, list[ValidationIssue]]:
    try:
        v1 = _V1Dataset.model_validate(document)
    except ValidationError as e:
        problems = "; ".join(
            f"{'.'.join(str(p) for p in err['loc'])}: {err['msg']}" for err in e.errors()
        )
        raise V1FormatError(f"Invalid v1 dataset: {problems}") from e

    assumptions: list[ValidationIssue] = []

    def assume(code: str, message: str) -> None:
        assumptions.append(ValidationIssue(code=code, message=message))

    p, logistics = v1.producer, v1.logistics
    crop_id = _slug(v1.crop.name)
    reference_price = sum(b.price_per_kg for b in v1.buyers) / len(v1.buyers)

    assume(
        "V1_COMPATIBILITY_MODE",
        "Imported from v1: one harvest lot on day 0 and a 1-day shelf life, so the plan covers a "
        "single day (sell today or lose it). Add lots, shelf life and storage to plan over time.",
    )
    assume(
        "V1_SHELF_LIFE_REPLACED",
        f"v1 shelf_life_days ({p.shelf_life_days}) is not used in compatibility mode "
        "(shelf_life_ambient_days set to 1).",
    )
    assume(
        "V1_REFERENCE_PRICE",
        f"Crop reference price set to the average buyer price ({reference_price:.4g} per kg).",
    )
    assume(
        "V1_FLEET",
        f"{logistics.available_vehicles} vehicle(s) of {logistics.vehicle_capacity_kg:,.0f} kg, one trip "
        "each per day, no driving-time limit and no per-trip cost (v1 capacity rule).",
    )
    if p.storage_cost_per_kg_per_day is None:
        assume("V1_STORAGE_COST_DEFAULT", f"Storage cost defaulted to {V1_STORAGE_COST_DEFAULT} per kg per day (v1 default).")
    if p.id:
        assume("V1_PRODUCER_ID_DROPPED", f"v1 producer id '{p.id}' is not kept (v2 has one producer per dataset).")
    missing_distance = [b.id for b in v1.buyers if b.distance_km is None]
    if missing_distance:
        assume("V1_DISTANCE_DEFAULT", f"Distance set to 0 km for buyers {missing_distance}.")
    missing_cost = [b.id for b in v1.buyers if b.transport_cost_per_kg_per_km is None]
    if missing_cost:
        assume("V1_TRANSPORT_COST_DEFAULT", f"Transport cost set to 0 for buyers {missing_cost}.")

    storage: list[StorageFacility] = []
    if p.storage_capacity_kg > 0:
        storage.append(
            StorageFacility(
                id="storage_1",
                name="Storage (v1)",
                capacity_kg=p.storage_capacity_kg,
                refrigerated=logistics.refrigerated_required,
                cost_per_kg_per_day=p.storage_cost_per_kg_per_day
                if p.storage_cost_per_kg_per_day is not None
                else V1_STORAGE_COST_DEFAULT,
            )
        )

    payload = DatasetPayload(
        producer=Producer(name=p.name, region=p.region, country=p.country),
        crops=[
            Crop(
                id=crop_id,
                name=v1.crop.name,
                type=v1.crop.type,
                reference_price_per_kg=reference_price,
                shelf_life_ambient_days=1,
                requires_cold_chain=logistics.refrigerated_required,
            )
        ],
        harvest_lots=[HarvestLot(id="lot_1", crop_id=crop_id, quantity_kg=p.harvest_kg, available_day=0)],
        buyers=[
            Buyer(
                id=b.id,
                name=b.name,
                location=b.location,
                crop_ids=[crop_id],
                price_per_kg=b.price_per_kg,
                max_demand_kg=b.max_demand_kg,
            )
            for b in v1.buyers
        ],
        storage_facilities=storage,
        vehicle_types=[
            VehicleType(
                id="vehicle_1",
                name="Vehicle (v1)",
                capacity_kg=logistics.vehicle_capacity_kg,
                count=logistics.available_vehicles,
                refrigerated=logistics.refrigerated_required,
                fixed_cost_per_trip=0.0,
                cost_per_km=0.0,
                hours_per_day=None,
                loading_hours_per_trip=0.0,
                max_trips_per_day=1,
            )
        ],
        routes=[
            Route(
                buyer_id=b.id,
                distance_km=b.distance_km or 0.0,
                road_condition=logistics.road_condition,
                road_factor_override=1.0,  # v1 costs had no road factor
                legacy_cost_per_kg_per_km=b.transport_cost_per_kg_per_km or 0.0,
            )
            for b in v1.buyers
        ],
    )
    return payload, assumptions

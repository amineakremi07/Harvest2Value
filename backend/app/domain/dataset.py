"""Dataset schema v2 (plan §7.2): one immutable JSON document per dataset version.

Structural rules (types, bounds, unique ids, cross references) are enforced here and
raise a ValidationError. Softer business checks live in `domain.validation`.
"""

from __future__ import annotations

from collections import Counter
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, StringConstraints, model_validator

from .enums import BuyerPriority, CropType, RoadCondition

SCHEMA_VERSION = "2.0"

EntityId = Annotated[str, StringConstraints(pattern=r"^[A-Za-z0-9_.\-]{1,64}$")]
Name = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=120)]
Percent = Annotated[float, Field(ge=0, le=100)]
Day = Annotated[int, Field(ge=0, le=365)]

# Distance multiplier applied to trip cost and trip duration when no override is given.
DEFAULT_ROAD_FACTORS: dict[RoadCondition, float] = {
    RoadCondition.GOOD: 1.0,
    RoadCondition.FAIR: 1.15,
    RoadCondition.POOR: 1.35,
}


class DomainModel(BaseModel):
    model_config = ConfigDict(extra="forbid", allow_inf_nan=False, validate_assignment=True)


class Producer(DomainModel):
    name: Name
    region: Name
    country: Name
    latitude: float | None = Field(default=None, ge=-90, le=90)
    longitude: float | None = Field(default=None, ge=-180, le=180)
    farm_size_ha: float | None = Field(default=None, gt=0)


class Crop(DomainModel):
    id: EntityId
    name: Name
    variety: Name | None = None
    type: CropType
    unit: Literal["kg"] = "kg"
    reference_price_per_kg: float = Field(ge=0)
    shelf_life_ambient_days: int = Field(ge=1, le=730)
    shelf_life_cold_days: int | None = Field(default=None, ge=1, le=730)
    quality_decay_pct_per_day: Percent = 0.0
    loss_rate_pct_per_day_ambient: Percent = 0.0
    loss_rate_pct_per_day_cold: Percent | None = None
    requires_cold_chain: bool = False

    @model_validator(mode="after")
    def _cold_not_shorter(self) -> Crop:
        if self.shelf_life_cold_days is not None and self.shelf_life_cold_days < self.shelf_life_ambient_days:
            raise ValueError("shelf_life_cold_days must be >= shelf_life_ambient_days")
        return self


class HarvestLot(DomainModel):
    id: EntityId
    crop_id: EntityId
    quantity_kg: float = Field(gt=0, le=1e8)
    available_day: Day = 0
    quality_grade: Name | None = None


class PricePoint(DomainModel):
    """From `day` on (until the next point), the buyer pays `price`."""

    day: Day
    price: float = Field(ge=0, le=1e4)


class Buyer(DomainModel):
    id: EntityId
    name: Name
    location: Name
    crop_ids: list[EntityId] = Field(min_length=1)
    price_per_kg: float = Field(ge=0, le=1e4)
    price_schedule: list[PricePoint] | None = None
    max_demand_kg: float = Field(gt=0, le=1e8)
    max_per_day_kg: float | None = Field(default=None, gt=0, le=1e8)
    min_contract_kg: float | None = Field(default=None, ge=0, le=1e8)
    min_order_kg: float | None = Field(default=None, ge=0, le=1e8)
    window_start_day: Day | None = None
    window_end_day: Day | None = None
    requires_cold_chain: bool = False
    payment_terms_days: int | None = Field(default=None, ge=0, le=365)
    priority: BuyerPriority = BuyerPriority.SPOT

    @model_validator(mode="after")
    def _consistent(self) -> Buyer:
        if len(set(self.crop_ids)) != len(self.crop_ids):
            raise ValueError("crop_ids must be unique")
        for field in ("min_contract_kg", "min_order_kg"):
            value = getattr(self, field)
            if value is not None and value > self.max_demand_kg:
                raise ValueError(f"{field} ({value}) cannot exceed max_demand_kg ({self.max_demand_kg})")
        if (
            self.window_start_day is not None
            and self.window_end_day is not None
            and self.window_end_day < self.window_start_day
        ):
            raise ValueError("window_end_day must be >= window_start_day")
        if self.price_schedule:
            days = [p.day for p in self.price_schedule]
            if len(set(days)) != len(days):
                raise ValueError("price_schedule days must be unique")
            if days != sorted(days):
                raise ValueError("price_schedule must be sorted by day")
        return self

    def price_on(self, day: int) -> float:
        price = self.price_per_kg
        for point in self.price_schedule or []:
            if point.day <= day:
                price = point.price
        return price


class StorageFacility(DomainModel):
    id: EntityId
    name: Name
    capacity_kg: float = Field(ge=0, le=1e8)
    refrigerated: bool = False
    cost_per_kg_per_day: float = Field(ge=0, le=1e3)


class VehicleType(DomainModel):
    id: EntityId
    name: Name
    capacity_kg: float = Field(gt=0, le=1e6)
    count: int = Field(ge=0, le=1000)
    refrigerated: bool = False
    fixed_cost_per_trip: float = Field(default=0.0, ge=0, le=1e6)
    cost_per_km: float = Field(default=0.0, ge=0, le=1e4)
    avg_speed_kmh: float = Field(default=50.0, gt=0, le=200)
    # None = no daily time limit (v1 compatibility); otherwise hours each vehicle can drive per day.
    hours_per_day: float | None = Field(default=10.0, gt=0, le=24)
    loading_hours_per_trip: float = Field(default=0.5, ge=0, le=24)
    # None = unlimited; the v1 import sets 1 so capacity equals vehicles x capacity per day.
    max_trips_per_day: int | None = Field(default=None, ge=1, le=100)


class Route(DomainModel):
    buyer_id: EntityId
    distance_km: float = Field(ge=0, le=5000)
    road_condition: RoadCondition = RoadCondition.FAIR
    road_factor_override: float | None = Field(default=None, ge=1, le=5)
    # v1 compatibility: cost per kg per km, charged on delivered kg (no road factor).
    legacy_cost_per_kg_per_km: float | None = Field(default=None, ge=0, le=100)
    toll_per_trip: float | None = Field(default=None, ge=0, le=1e5)

    @property
    def road_factor(self) -> float:
        if self.road_factor_override is not None:
            return self.road_factor_override
        return DEFAULT_ROAD_FACTORS[self.road_condition]


def trip_hours(route: Route, vehicle: VehicleType) -> float:
    """Round trip driving time (distance x road factor, both ways) plus loading time."""
    return 2 * route.distance_km * route.road_factor / vehicle.avg_speed_kmh + vehicle.loading_hours_per_trip


def trip_cost(route: Route, vehicle: VehicleType) -> float:
    """Cost of one round trip: fixed cost + per-km cost on the road-adjusted distance + toll."""
    return (
        vehicle.fixed_cost_per_trip
        + 2 * route.distance_km * route.road_factor * vehicle.cost_per_km
        + (route.toll_per_trip or 0.0)
    )


def _duplicates(ids: list[str]) -> list[str]:
    return sorted(i for i, n in Counter(ids).items() if n > 1)


class DatasetPayload(DomainModel):
    schema_version: Literal["2.0"] = "2.0"
    currency: Annotated[str, StringConstraints(pattern=r"^[A-Z]{3}$")] | None = None
    producer: Producer
    crops: list[Crop] = Field(min_length=1, max_length=20)
    harvest_lots: list[HarvestLot] = Field(min_length=1, max_length=60)
    buyers: list[Buyer] = Field(min_length=1, max_length=50)
    storage_facilities: list[StorageFacility] = Field(default_factory=list, max_length=20)
    vehicle_types: list[VehicleType] = Field(min_length=1, max_length=20)
    routes: list[Route] = Field(min_length=1, max_length=50)

    @model_validator(mode="after")
    def _references(self) -> DatasetPayload:
        problems: list[str] = []
        for label, ids in (
            ("crops", [c.id for c in self.crops]),
            ("harvest_lots", [h.id for h in self.harvest_lots]),
            ("buyers", [b.id for b in self.buyers]),
            ("storage_facilities", [s.id for s in self.storage_facilities]),
            ("vehicle_types", [v.id for v in self.vehicle_types]),
        ):
            dup = _duplicates(ids)
            if dup:
                problems.append(f"{label}: duplicate id(s) {dup}")

        crop_ids = {c.id for c in self.crops}
        buyer_ids = {b.id for b in self.buyers}
        for lot in self.harvest_lots:
            if lot.crop_id not in crop_ids:
                problems.append(f"harvest_lots[{lot.id}]: unknown crop_id '{lot.crop_id}'")
        for buyer in self.buyers:
            unknown = sorted(set(buyer.crop_ids) - crop_ids)
            if unknown:
                problems.append(f"buyers[{buyer.id}]: unknown crop_ids {unknown}")

        route_buyers = [r.buyer_id for r in self.routes]
        dup_routes = _duplicates(route_buyers)
        if dup_routes:
            problems.append(f"routes: more than one route for buyer(s) {dup_routes}")
        orphan = sorted(set(route_buyers) - buyer_ids)
        if orphan:
            problems.append(f"routes: unknown buyer_id(s) {orphan}")
        missing = sorted(buyer_ids - set(route_buyers))
        if missing:
            problems.append(f"routes: missing route for buyer(s) {missing}")

        if problems:
            raise ValueError("; ".join(problems))
        return self

    def crop(self, crop_id: str) -> Crop:
        return next(c for c in self.crops if c.id == crop_id)

    def route_for(self, buyer_id: str) -> Route:
        return next(r for r in self.routes if r.buyer_id == buyer_id)

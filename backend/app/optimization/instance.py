"""ProblemInstance: every coefficient the model needs, precomputed, immutable and PuLP-free.

Conventions (plan §10):
- day t in 0..T-1; a lot is available from the morning of its `available_day`;
- `DIRECT` is the pseudo-facility "no storage": a lot placed there can only be sold on
  its harvest day, the rest is lost that day;
- in a real facility, a lot can be sold from the day after its harvest until its last
  shelf-life day; what is left then expires (or is ending inventory if the shelf life
  goes beyond the horizon).
"""

from __future__ import annotations

import math
from collections.abc import Mapping
from dataclasses import dataclass, replace

from ..core.errors import ValidationFailed
from ..domain.dataset import DatasetPayload, trip_cost, trip_hours
from ..domain.run_config import MAX_HORIZON_DAYS, RunConfig

DIRECT = "__direct__"


@dataclass(frozen=True)
class LotData:
    id: str
    quantity: float
    day: int


@dataclass(frozen=True)
class FacilityData:
    id: str
    name: str
    capacity: float
    cost_per_kg_day: float
    refrigerated: bool
    shelf_life: int
    loss_rate: float  # fraction lost per day in storage
    usable: bool  # False: ambient storage for a cold-chain crop


@dataclass(frozen=True)
class BuyerData:
    id: str
    name: str
    max_demand: float
    max_per_day: float | None
    min_contract: float
    min_order: float
    window: tuple[int, int]  # first and last day, clipped to the horizon
    requires_cold_chain: bool
    legacy_cost_per_kg: float  # v1: cost per kg per km x distance, charged per kg delivered


@dataclass(frozen=True)
class VehicleData:
    id: str
    name: str
    capacity: float
    count: int
    refrigerated: bool
    hours_per_day: float | None
    max_trips_per_day: int | None


@dataclass(frozen=True)
class ProblemInstance:
    crop_id: str
    crop_name: str
    reference_price: float
    requires_cold_chain: bool
    horizon: int
    lots: tuple[LotData, ...]
    facilities: tuple[FacilityData, ...]
    buyers: tuple[BuyerData, ...]
    vehicles: tuple[VehicleData, ...]
    price: Mapping[tuple[str, str, int], float]  # (buyer, lot, day) -> price after decay
    trip_cost: Mapping[tuple[str, str], float]  # (buyer, vehicle)
    trip_hours: Mapping[tuple[str, str], float]
    allow: Mapping[tuple[str, str], bool]  # cold-chain compatibility (buyer, vehicle)
    last_day: Mapping[tuple[str, str], int]  # (lot, facility|DIRECT) -> last day it can be held/sold
    expires: Mapping[tuple[str, str], bool]  # shelf life ends inside the horizon
    salvage_per_kg: float
    disposal_cost_per_kg: float
    warnings: tuple[str, ...]

    @property
    def harvest_kg(self) -> float:
        return sum(lot.quantity for lot in self.lots)

    def sale_days(self, buyer: BuyerData, lot: LotData, facility_id: str) -> range:
        """Days on which `buyer` can receive `lot` taken from `facility_id`."""
        first = lot.day if facility_id == DIRECT else lot.day + 1
        last = self.last_day[(lot.id, facility_id)]
        start, end = max(first, buyer.window[0]), min(last, buyer.window[1])
        return range(start, end + 1)

    def trip_possible(self, buyer_id: str, vehicle: VehicleData) -> bool:
        if not self.allow[(buyer_id, vehicle.id)]:
            return False
        return vehicle.hours_per_day is None or self.trip_hours[(buyer_id, vehicle.id)] <= vehicle.hours_per_day

    def name_of(self, entity_id: str) -> str:
        return self._names.get(entity_id, entity_id)

    @property
    def _names(self) -> dict[str, str]:
        names = {b.id: b.name for b in self.buyers}
        names.update({f.id: f.name for f in self.facilities})
        names.update({v.id: v.name for v in self.vehicles})
        names[DIRECT] = "direct sale"
        return names


def _select_crop(payload: DatasetPayload, config: RunConfig) -> str:
    harvested = sorted({lot.crop_id for lot in payload.harvest_lots})
    if config.crop_id is not None:
        if config.crop_id not in {c.id for c in payload.crops}:
            raise ValidationFailed(f"Unknown crop_id '{config.crop_id}'.", code="CONFIG_INVALID")
        if config.crop_id not in harvested:
            raise ValidationFailed(f"Crop '{config.crop_id}' has no harvest lot.", code="CONFIG_INVALID")
        return config.crop_id
    if len(harvested) > 1:
        raise ValidationFailed(
            f"The dataset has several harvested crops {harvested}: set crop_id.", code="CONFIG_INVALID"
        )
    return harvested[0]


def build_instance(payload: DatasetPayload, config: RunConfig) -> ProblemInstance:
    crop_id = _select_crop(payload, config)
    crop = payload.crop(crop_id)
    warnings: list[str] = []

    facilities_all: list[FacilityData] = []
    for sf in payload.storage_facilities:
        if sf.capacity_kg <= 0:
            continue
        cold = sf.refrigerated
        facilities_all.append(
            FacilityData(
                id=sf.id,
                name=sf.name,
                capacity=sf.capacity_kg,
                cost_per_kg_day=sf.cost_per_kg_per_day,
                refrigerated=cold,
                shelf_life=(crop.shelf_life_cold_days or crop.shelf_life_ambient_days) if cold else crop.shelf_life_ambient_days,
                loss_rate=(
                    (crop.loss_rate_pct_per_day_cold if crop.loss_rate_pct_per_day_cold is not None else crop.loss_rate_pct_per_day_ambient)
                    if cold
                    else crop.loss_rate_pct_per_day_ambient
                )
                / 100.0,
                usable=cold or not crop.requires_cold_chain,
            )
        )
        if crop.requires_cold_chain and not cold:
            warnings.append(f"Storage '{sf.name}' is not refrigerated and cannot hold cold-chain crop '{crop.name}'.")

    crop_lots = [lot for lot in payload.harvest_lots if lot.crop_id == crop_id]
    longest_shelf = max([1] + [f.shelf_life for f in facilities_all if f.usable])
    if config.horizon_days is not None:
        horizon = config.horizon_days
    else:
        horizon = min(MAX_HORIZON_DAYS, max(lot.available_day + longest_shelf for lot in crop_lots))

    lots = tuple(LotData(lot.id, lot.quantity_kg, lot.available_day) for lot in crop_lots if lot.available_day < horizon)
    for raw_lot in crop_lots:
        if raw_lot.available_day >= horizon:
            warnings.append(f"Lot '{raw_lot.id}' (day {raw_lot.available_day}) is after the {horizon}-day horizon and is ignored.")
    if not lots:
        raise ValidationFailed(f"No harvest lot of '{crop.name}' falls within the {horizon}-day horizon.", code="CONFIG_INVALID")

    buyers: list[BuyerData] = []
    for pb in payload.buyers:
        if crop_id not in pb.crop_ids:
            continue
        start = pb.window_start_day or 0
        end = min(pb.window_end_day if pb.window_end_day is not None else horizon - 1, horizon - 1)
        if start > end:
            warnings.append(f"Buyer '{pb.name}' receives nothing within the {horizon}-day horizon (delivery window).")
            continue
        route = payload.route_for(pb.id)
        buyers.append(
            BuyerData(
                id=pb.id,
                name=pb.name,
                max_demand=pb.max_demand_kg,
                max_per_day=pb.max_per_day_kg,
                min_contract=pb.min_contract_kg or 0.0,
                min_order=pb.min_order_kg or 0.0,
                window=(start, end),
                requires_cold_chain=pb.requires_cold_chain or crop.requires_cold_chain,
                legacy_cost_per_kg=(route.legacy_cost_per_kg_per_km or 0.0) * route.distance_km,
            )
        )
    if not buyers:
        raise ValidationFailed(f"No buyer can receive '{crop.name}' within the horizon.", code="CONFIG_INVALID")

    vehicles = tuple(
        VehicleData(v.id, v.name, v.capacity_kg, v.count, v.refrigerated, v.hours_per_day, v.max_trips_per_day)
        for v in payload.vehicle_types
        if v.count > 0
    )
    vehicle_by_id = {v.id: v for v in payload.vehicle_types}

    trip_cost_map: dict[tuple[str, str], float] = {}
    trip_hours_map: dict[tuple[str, str], float] = {}
    allow: dict[tuple[str, str], bool] = {}
    for b in buyers:
        route = payload.route_for(b.id)
        for v in vehicles:
            trip_cost_map[(b.id, v.id)] = trip_cost(route, vehicle_by_id[v.id])
            trip_hours_map[(b.id, v.id)] = trip_hours(route, vehicle_by_id[v.id])
            allow[(b.id, v.id)] = v.refrigerated or not b.requires_cold_chain

    last_day: dict[tuple[str, str], int] = {}
    expires: dict[tuple[str, str], bool] = {}
    for lot in lots:
        last_day[(lot.id, DIRECT)] = lot.day
        expires[(lot.id, DIRECT)] = True
        for f in facilities_all:
            end_of_life = lot.day + f.shelf_life - 1
            last_day[(lot.id, f.id)] = min(end_of_life, horizon - 1)
            expires[(lot.id, f.id)] = end_of_life <= horizon - 1

    decay = crop.quality_decay_pct_per_day / 100.0
    payload_buyers = {b.id: b for b in payload.buyers}
    price: dict[tuple[str, str, int], float] = {}
    for b in buyers:
        source = payload_buyers[b.id]
        for lot in lots:
            last = max(last_day[(lot.id, f)] for f in [DIRECT, *(f.id for f in facilities_all)])
            for day in range(max(lot.day, b.window[0]), min(last, b.window[1]) + 1):
                age = day - lot.day
                price[(b.id, lot.id, day)] = source.price_on(day) * max(0.0, 1.0 - decay * age)

    instance = ProblemInstance(
        crop_id=crop_id,
        crop_name=crop.name,
        reference_price=crop.reference_price_per_kg,
        requires_cold_chain=crop.requires_cold_chain,
        horizon=horizon,
        lots=lots,
        facilities=tuple(facilities_all),
        buyers=tuple(buyers),
        vehicles=vehicles,
        price=price,
        trip_cost=trip_cost_map,
        trip_hours=trip_hours_map,
        allow=allow,
        last_day=last_day,
        expires=expires,
        salvage_per_kg=config.salvage_value_pct / 100.0 * crop.reference_price_per_kg,
        disposal_cost_per_kg=config.disposal_cost_per_kg,
        warnings=tuple(warnings),
    )
    for b in buyers:
        if not any(instance.trip_possible(b.id, v) for v in vehicles):
            warnings.append(f"Buyer '{b.name}' cannot be reached by any available vehicle (cold chain or trip length).")
    return replace(instance, warnings=tuple(warnings))


def trips_upper_bound(instance: ProblemInstance, buyer: BuyerData, vehicle: VehicleData) -> int:
    """Largest useful number of trips of `vehicle` to `buyer` on one day."""
    need = min(buyer.max_demand, buyer.max_per_day or math.inf, instance.harvest_kg)
    bound = math.ceil(need / vehicle.capacity)
    if vehicle.max_trips_per_day is not None:
        bound = min(bound, vehicle.count * vehicle.max_trips_per_day)
    if vehicle.hours_per_day is not None:
        hours = instance.trip_hours[(buyer.id, vehicle.id)]
        bound = min(bound, math.floor(vehicle.count * vehicle.hours_per_day / hours) if hours > 0 else bound)
    return max(bound, 0)

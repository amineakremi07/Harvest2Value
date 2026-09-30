"""Buyer ranking before optimization: estimated net price per kg for each outlet.

net_price_per_kg = price_per_kg - transport cost per kg of the cheapest usable vehicle at full load
(useful load = min(vehicle capacity, what the buyer takes in a day)) - legacy v1 cost per kg.
It is an estimate for ranking and explanations; the plan's realized net prices come from the solver.
"""

from __future__ import annotations

from pydantic import BaseModel, Field

from ..core.errors import ValidationFailed
from ..domain.dataset import DatasetPayload, trip_cost, trip_hours


class MarketRow(BaseModel):
    buyer_id: str
    buyer_name: str
    location: str
    price_per_kg: float
    best_scheduled_price: float | None = Field(description="Highest price in the price schedule, if any")
    max_demand_kg: float
    distance_km: float
    road_factor: float
    requires_cold_chain: bool
    reachable: bool
    unreachable_reason: str | None
    best_vehicle_id: str | None
    trip_cost: float | None
    useful_load_kg: float | None
    transport_cost_per_kg: float | None
    net_price_per_kg: float | None
    rank: int | None = Field(description="1 = best estimated net price among reachable buyers")


class MarketAnalysis(BaseModel):
    crop_id: str
    crop_name: str
    reference_price_per_kg: float
    rows: list[MarketRow]


def select_crop(payload: DatasetPayload, crop_id: str | None) -> str:
    harvested = sorted({lot.crop_id for lot in payload.harvest_lots})
    if crop_id is not None:
        if crop_id not in {c.id for c in payload.crops}:
            raise ValidationFailed(f"Unknown crop_id '{crop_id}'.", code="CONFIG_INVALID")
        return crop_id
    if len(harvested) > 1:
        raise ValidationFailed(f"The dataset has several harvested crops {harvested}: set crop_id.", code="CONFIG_INVALID")
    return harvested[0]


def analyze_market(payload: DatasetPayload, crop_id: str | None = None) -> MarketAnalysis:
    crop = payload.crop(select_crop(payload, crop_id))
    rows: list[MarketRow] = []
    for buyer in payload.buyers:
        if crop.id not in buyer.crop_ids:
            continue
        route = payload.route_for(buyer.id)
        cold = buyer.requires_cold_chain or crop.requires_cold_chain
        daily = min(buyer.max_per_day_kg or buyer.max_demand_kg, buyer.max_demand_kg)
        legacy = (route.legacy_cost_per_kg_per_km or 0.0) * route.distance_km

        best: tuple[float, str, float, float] | None = None  # cost/kg, vehicle id, trip cost, load
        reason: str | None = None
        candidates = [v for v in payload.vehicle_types if v.count > 0]
        if not candidates:
            reason = "no vehicle available"
        for vehicle in candidates:
            if cold and not vehicle.refrigerated:
                reason = reason or "needs a refrigerated vehicle"
                continue
            if vehicle.hours_per_day is not None and trip_hours(route, vehicle) > vehicle.hours_per_day:
                reason = "round trip longer than a working day"
                continue
            load = min(vehicle.capacity_kg, daily)
            cost = trip_cost(route, vehicle)
            per_kg = cost / load + legacy
            if best is None or per_kg < best[0]:
                best = (per_kg, vehicle.id, cost, load)

        schedule = [p.price for p in buyer.price_schedule or []]
        rows.append(
            MarketRow(
                buyer_id=buyer.id,
                buyer_name=buyer.name,
                location=buyer.location,
                price_per_kg=buyer.price_per_kg,
                best_scheduled_price=max(schedule) if schedule else None,
                max_demand_kg=buyer.max_demand_kg,
                distance_km=route.distance_km,
                road_factor=route.road_factor,
                requires_cold_chain=cold,
                reachable=best is not None,
                unreachable_reason=None if best is not None else reason,
                best_vehicle_id=best[1] if best else None,
                trip_cost=round(best[2], 4) if best else None,
                useful_load_kg=best[3] if best else None,
                transport_cost_per_kg=round(best[0], 4) if best else None,
                net_price_per_kg=round(buyer.price_per_kg - best[0], 4) if best else None,
                rank=None,
            )
        )
    ranked = sorted((r for r in rows if r.net_price_per_kg is not None), key=lambda r: (-r.net_price_per_kg, r.buyer_id))  # type: ignore[operator]
    for position, row in enumerate(ranked, start=1):
        row.rank = position
    rows.sort(key=lambda r: (r.rank is None, r.rank or 0, r.buyer_id))
    return MarketAnalysis(crop_id=crop.id, crop_name=crop.name, reference_price_per_kg=crop.reference_price_per_kg, rows=rows)

"""Logistics section: trips, cost per trip and per kg, fleet hours and utilization, routes."""

from __future__ import annotations

from collections import defaultdict

from pydantic import BaseModel

from .context import RunContext


class VehicleUsage(BaseModel):
    vehicle_type_id: str
    name: str
    count: int
    refrigerated: bool
    trips: int
    capacity_sent_kg: float
    cost: float
    hours: float
    hours_available: float | None
    utilization_pct: float | None
    binding_days: list[int]


class RouteUsage(BaseModel):
    buyer_id: str
    buyer_name: str
    distance_km: float
    trips: int
    delivered_kg: float
    cost: float
    cost_per_kg: float | None


class DailyTrips(BaseModel):
    day: int
    trips: int
    cost: float
    hours: float


class LogisticsSection(BaseModel):
    run_id: str
    trips: int
    transport_cost: float
    cost_per_trip: float | None
    cost_per_kg: float | None
    load_factor_pct: float | None
    vehicle_utilization_pct: float | None
    vehicles: list[VehicleUsage]
    routes: list[RouteUsage]
    daily: list[DailyTrips]


def logistics(ctx: RunContext) -> LogisticsSection:
    k = ctx.result.kpis
    by_vehicle: dict[str, dict[str, float]] = defaultdict(lambda: defaultdict(float))
    by_buyer: dict[str, dict[str, float]] = defaultdict(lambda: defaultdict(float))
    daily: dict[int, dict[str, float]] = defaultdict(lambda: defaultdict(float))
    for t in ctx.result.trips:
        for bucket in (by_vehicle[t.vehicle_type_id], by_buyer[t.buyer_id], daily[t.day]):
            bucket["trips"] += t.trips
            bucket["cost"] += t.cost
            bucket["hours"] += t.hours
        by_vehicle[t.vehicle_type_id]["capacity"] += t.capacity_kg

    binding_days: dict[str, list[int]] = defaultdict(list)
    for family in ("fleet_time", "fleet_trips"):
        for c in ctx.binding(family):
            if c.day is not None and c.day not in binding_days[c.entity[0]]:
                binding_days[c.entity[0]].append(c.day)

    horizon = ctx.instance.horizon
    vehicles = []
    for v in ctx.instance.vehicles:
        used = by_vehicle.get(v.id, {})
        available = v.count * v.hours_per_day * horizon if v.hours_per_day is not None else None
        hours = used.get("hours", 0.0)
        vehicles.append(
            VehicleUsage(
                vehicle_type_id=v.id,
                name=v.name,
                count=v.count,
                refrigerated=v.refrigerated,
                trips=int(used.get("trips", 0)),
                capacity_sent_kg=round(used.get("capacity", 0.0), 2),
                cost=round(used.get("cost", 0.0), 2),
                hours=round(hours, 2),
                hours_available=round(available, 2) if available is not None else None,
                utilization_pct=round(100 * hours / available, 2) if available else None,
                binding_days=sorted(binding_days.get(v.id, [])),
            )
        )

    routes = []
    for b in ctx.result.buyers:
        used = by_buyer.get(b.buyer_id, {})
        routes.append(
            RouteUsage(
                buyer_id=b.buyer_id,
                buyer_name=b.buyer_name,
                distance_km=ctx.payload.route_for(b.buyer_id).distance_km,
                trips=int(used.get("trips", 0)),
                delivered_kg=b.sold_kg,
                cost=b.transport_cost,
                cost_per_kg=round(b.transport_cost / b.sold_kg, 4) if b.sold_kg > 0 else None,
            )
        )

    return LogisticsSection(
        run_id=ctx.run_id,
        trips=k.trips,
        transport_cost=k.transport_cost,
        cost_per_trip=round(k.transport_cost / k.trips, 2) if k.trips else None,
        cost_per_kg=k.avg_transport_cost_per_kg,
        load_factor_pct=k.load_factor_pct,
        vehicle_utilization_pct=k.vehicle_utilization_pct,
        vehicles=vehicles,
        routes=routes,
        daily=[
            DailyTrips(day=d, trips=int(v["trips"]), cost=round(v["cost"], 2), hours=round(v["hours"], 2))
            for d, v in sorted(daily.items())
        ],
    )

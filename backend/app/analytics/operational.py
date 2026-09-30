"""Operational section: sold / lost / stored shares, daily flows, storage usage."""

from __future__ import annotations

from pydantic import BaseModel

from .context import RunContext


class Rates(BaseModel):
    sold_rate_pct: float
    waste_rate_pct: float
    storage_rate_pct: float
    fulfillment_rate_pct: float | None
    vehicle_utilization_pct: float | None
    load_factor_pct: float | None
    storage_utilization_peak_pct: float | None
    storage_utilization_avg_pct: float | None


class DailyFlow(BaseModel):
    day: int
    sold_kg: float
    stock_end_kg: float
    lost_kg: float


class StorageUsage(BaseModel):
    facility_id: str
    name: str
    capacity_kg: float
    usable: bool
    stored_kg: float
    peak_kg: float
    peak_pct: float | None
    avg_pct: float | None
    full_days: list[int]
    cost: float


class OperationalSection(BaseModel):
    run_id: str
    harvest_kg: float
    sold_kg: float
    lost_kg: float
    ending_inventory_kg: float
    rates: Rates
    waste_by_kind: dict[str, float]
    daily: list[DailyFlow]
    storage: list[StorageUsage]


def operational(ctx: RunContext) -> OperationalSection:
    k = ctx.result.kpis
    return OperationalSection(
        run_id=ctx.run_id,
        harvest_kg=k.harvest_kg,
        sold_kg=k.sold_kg,
        lost_kg=k.lost_kg,
        ending_inventory_kg=k.ending_inventory_kg,
        rates=Rates(
            sold_rate_pct=k.sold_rate_pct,
            waste_rate_pct=k.waste_rate_pct,
            storage_rate_pct=k.storage_rate_pct,
            fulfillment_rate_pct=k.fulfillment_rate_pct,
            vehicle_utilization_pct=k.vehicle_utilization_pct,
            load_factor_pct=k.load_factor_pct,
            storage_utilization_peak_pct=k.storage_utilization_peak_pct,
            storage_utilization_avg_pct=k.storage_utilization_avg_pct,
        ),
        waste_by_kind=ctx.waste_by_kind,
        daily=[
            DailyFlow(
                day=t,
                sold_kg=round(ctx.sold_by_day.get(t, 0.0), 2),
                stock_end_kg=round(ctx.stock_by_day.get(t, 0.0), 2),
                lost_kg=round(ctx.lost_by_day.get(t, 0.0), 2),
            )
            for t in range(ctx.result.horizon_days)
        ],
        storage=[StorageUsage(**usage.__dict__) for usage in ctx.facility_usage],
    )

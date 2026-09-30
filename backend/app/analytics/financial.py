"""Financial section: revenue, costs, profit, margin and a revenue-to-profit waterfall."""

from __future__ import annotations

from collections import defaultdict
from typing import Literal

from pydantic import BaseModel

from .context import RunContext


class CostBreakdown(BaseModel):
    transport: float
    storage: float
    disposal: float
    total: float


class WaterfallStep(BaseModel):
    label: str
    value: float
    kind: Literal["start", "decrease", "total"]


class BuyerMoney(BaseModel):
    buyer_id: str
    buyer_name: str
    revenue: float
    transport_cost: float
    net_revenue: float
    share_of_revenue_pct: float | None


class DailyMoney(BaseModel):
    day: int
    revenue: float
    transport_cost: float
    storage_cost: float
    disposal_cost: float


class FinancialSection(BaseModel):
    run_id: str
    currency: str | None
    realized_revenue: float
    realized_profit: float
    margin_pct: float | None
    ending_inventory_value: float
    economic_value: float
    lost_value: float
    costs: CostBreakdown
    waterfall: list[WaterfallStep]
    by_buyer: list[BuyerMoney]
    daily: list[DailyMoney]


def financial(ctx: RunContext) -> FinancialSection:
    k = ctx.result.kpis
    revenue_day: dict[int, float] = defaultdict(float)
    transport_day: dict[int, float] = defaultdict(float)
    storage_day: dict[int, float] = defaultdict(float)
    disposal_day: dict[int, float] = defaultdict(float)
    legacy = {b.id: b.legacy_cost_per_kg for b in ctx.instance.buyers}
    for a in ctx.result.allocations:
        revenue_day[a.day] += a.revenue
        transport_day[a.day] += legacy.get(a.buyer_id, 0.0) * a.kg
    for t in ctx.result.trips:
        transport_day[t.day] += t.cost
    for row in ctx.result.inventory:
        storage_day[row.day] += row.cost
    for w in ctx.result.waste:
        disposal_day[w.day] += ctx.instance.disposal_cost_per_kg * w.kg

    days = sorted(set(revenue_day) | set(transport_day) | set(storage_day) | set(disposal_day))
    return FinancialSection(
        run_id=ctx.run_id,
        currency=ctx.payload.currency,
        realized_revenue=k.realized_revenue,
        realized_profit=k.realized_profit,
        margin_pct=k.margin_pct,
        ending_inventory_value=k.ending_inventory_value,
        economic_value=k.economic_value,
        lost_value=k.lost_value,
        costs=CostBreakdown(transport=k.transport_cost, storage=k.storage_cost, disposal=k.disposal_cost, total=k.total_cost),
        waterfall=[
            WaterfallStep(label="Realized revenue", value=k.realized_revenue, kind="start"),
            WaterfallStep(label="Transport", value=-k.transport_cost, kind="decrease"),
            WaterfallStep(label="Storage", value=-k.storage_cost, kind="decrease"),
            WaterfallStep(label="Disposal", value=-k.disposal_cost, kind="decrease"),
            WaterfallStep(label="Realized profit", value=k.realized_profit, kind="total"),
        ],
        by_buyer=[
            BuyerMoney(
                buyer_id=b.buyer_id,
                buyer_name=b.buyer_name,
                revenue=b.revenue,
                transport_cost=b.transport_cost,
                net_revenue=b.net_revenue,
                share_of_revenue_pct=round(100 * b.revenue / k.realized_revenue, 2) if k.realized_revenue > 0 else None,
            )
            for b in sorted(ctx.result.buyers, key=lambda b: -b.revenue)
        ],
        daily=[
            DailyMoney(
                day=d,
                revenue=round(revenue_day[d], 2),
                transport_cost=round(transport_day[d], 2),
                storage_cost=round(storage_day[d], 2),
                disposal_cost=round(disposal_day[d], 2),
            )
            for d in days
        ],
    )

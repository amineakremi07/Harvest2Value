"""Buyers section: demand, price, realized and estimated net price, share, fulfillment, distance."""

from __future__ import annotations

from pydantic import BaseModel

from .context import RunContext


class BuyerAnalytics(BaseModel):
    buyer_id: str
    buyer_name: str
    location: str
    price_per_kg: float
    max_demand_kg: float
    sold_kg: float
    share_of_sales_pct: float | None
    fulfillment_pct: float
    revenue: float
    transport_cost: float
    net_revenue: float
    net_price_per_kg: float | None
    estimated_net_price_per_kg: float | None
    market_rank: int | None
    distance_km: float
    served_days: list[int]


class BuyersSection(BaseModel):
    run_id: str
    best_buyer_id: str | None
    buyers: list[BuyerAnalytics]


def buyers(ctx: RunContext) -> BuyersSection:
    sold_total = ctx.result.kpis.sold_kg
    served: dict[str, set[int]] = {}
    for a in ctx.result.allocations:
        served.setdefault(a.buyer_id, set()).add(a.day)
    source = {b.id: b for b in ctx.payload.buyers}
    rows = []
    for b in ctx.result.buyers:
        market = ctx.market_rows.get(b.buyer_id)
        rows.append(
            BuyerAnalytics(
                buyer_id=b.buyer_id,
                buyer_name=b.buyer_name,
                location=source[b.buyer_id].location,
                price_per_kg=source[b.buyer_id].price_per_kg,
                max_demand_kg=b.max_demand_kg,
                sold_kg=b.sold_kg,
                share_of_sales_pct=round(100 * b.sold_kg / sold_total, 2) if sold_total > 0 else None,
                fulfillment_pct=b.fulfillment_pct,
                revenue=b.revenue,
                transport_cost=b.transport_cost,
                net_revenue=b.net_revenue,
                net_price_per_kg=b.net_price_per_kg,
                estimated_net_price_per_kg=market.net_price_per_kg if market else None,
                market_rank=market.rank if market else None,
                distance_km=ctx.payload.route_for(b.buyer_id).distance_km,
                served_days=sorted(served.get(b.buyer_id, set())),
            )
        )
    rows.sort(key=lambda r: (-r.sold_kg, r.buyer_id))
    return BuyersSection(run_id=ctx.run_id, best_buyer_id=ctx.result.kpis.best_buyer_id, buyers=rows)

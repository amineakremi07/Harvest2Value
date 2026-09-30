"""What stopped a buyer from receiving more (plan §15). Checked in this exact order:

1. UNPROFITABLE       not served and estimated net price <= 0
2. DEMAND_CAP         maximum demand reached
3. DAILY_DEMAND_CAP   daily demand limit reached
4. FLEET_TIME         fleet hours / trips binding on days the buyer could be served
5. COLD_CHAIN         no compatible vehicle (cold chain, or round trip longer than a working day)
6. SHELF_LIFE_WINDOW  stock expired or was lost unsold while the buyer still had demand
7. MOQ                minimum order not reachable (buyer not served)
8. OPPORTUNITY        better outlets absorbed the volume
"""

from __future__ import annotations

from ..analytics.context import RunContext
from ..domain.explanation import LimitingFactor
from .binding import really_binding


def limiting_factor(ctx: RunContext, buyer_id: str) -> LimitingFactor:
    inst = ctx.instance
    summary = ctx.buyers[buyer_id]
    buyer = next(b for b in inst.buyers if b.id == buyer_id)
    market = ctx.market_rows.get(buyer_id)
    name = summary.buyer_name
    sold = summary.sold_kg
    remaining = max(0.0, summary.max_demand_kg - sold)

    # 1. UNPROFITABLE
    if sold <= 0 and market is not None and market.net_price_per_kg is not None and market.net_price_per_kg <= 0:
        return LimitingFactor(
            code="UNPROFITABLE",
            message=f"{name} is not served: transport costs {market.transport_cost_per_kg:.3f}/kg for a price of "
            f"{market.price_per_kg:.3f}/kg, a net price of {market.net_price_per_kg:.3f}/kg.",
            evidence={
                "price_per_kg": market.price_per_kg,
                "transport_cost_per_kg": market.transport_cost_per_kg,
                "net_price_per_kg": market.net_price_per_kg,
            },
        )

    # 2. DEMAND_CAP
    cap = [c for c in ctx.binding("demand_max", buyer_id) if really_binding(c, ctx)]
    if cap:
        return LimitingFactor(
            code="DEMAND_CAP",
            message=f"{name} received its full maximum demand of {summary.max_demand_kg:,.0f} kg.",
            evidence={"sold_kg": sold, "max_demand_kg": summary.max_demand_kg},
            constraint_keys=[c.key for c in cap],
        )

    # 3. DAILY_DEMAND_CAP
    daily = ctx.binding("demand_day", buyer_id)
    if daily:
        days = [c.day for c in daily]
        return LimitingFactor(
            code="DAILY_DEMAND_CAP",
            message=f"{name} took its daily maximum of {buyer.max_per_day:,.0f} kg on {len(days)} day(s).",
            evidence={"max_per_day_kg": buyer.max_per_day, "days": days, "remaining_demand_kg": remaining},
            constraint_keys=[c.key for c in daily],
        )

    # 4. FLEET_TIME: fleet limits binding on a day this buyer could receive, for a vehicle it can use
    usable = {v.id for v in inst.vehicles if inst.trip_possible(buyer_id, v)}
    first, last = buyer.window
    fleet = [
        c
        for family in ("fleet_time", "fleet_trips")
        for c in ctx.binding(family)
        if c.entity[0] in usable and c.day is not None and first <= c.day <= last
    ]
    if fleet and remaining > 0:
        return LimitingFactor(
            code="FLEET_TIME",
            message=f"The fleet was fully used on {len({c.day for c in fleet})} day(s) when {name} could be served; "
            f"{remaining:,.0f} kg of its demand stayed open.",
            evidence={"days": sorted({c.day for c in fleet}), "remaining_demand_kg": remaining},
            constraint_keys=[c.key for c in fleet],
        )

    # 5. COLD_CHAIN (no compatible vehicle at all)
    if not usable:
        cold = buyer.requires_cold_chain
        reason = "it needs a refrigerated vehicle and none is available" if cold else "every round trip is longer than a working day"
        return LimitingFactor(
            code="COLD_CHAIN",
            message=f"{name} cannot be served: {reason}.",
            evidence={"requires_cold_chain": cold, "vehicle_types": len(inst.vehicles)},
        )

    # 6. SHELF_LIFE_WINDOW
    expired = ctx.waste_by_kind.get("expired", 0.0) + ctx.waste_by_kind.get("unsold_direct", 0.0)
    if expired > 0 and remaining > 0:
        window = None if buyer.window == (0, inst.horizon - 1) else list(buyer.window)
        return LimitingFactor(
            code="SHELF_LIFE_WINDOW",
            message=f"{expired:,.0f} kg expired or were lost unsold while {name} still had {remaining:,.0f} kg of demand"
            + (f" (it only receives on days {window[0]}-{window[1]})" if window else "")
            + ": the produce could not reach it within its shelf life.",
            evidence={"lost_unsold_kg": round(expired, 2), "remaining_demand_kg": remaining, "delivery_window": window},
        )

    # 7. MOQ
    if buyer.min_order > 0 and sold <= 0:
        return LimitingFactor(
            code="MOQ",
            message=f"{name} requires at least {buyer.min_order:,.0f} kg per order, which the plan could not fill profitably.",
            evidence={"min_order_kg": buyer.min_order},
            constraint_keys=[c.key for c in ctx.result.constraints if c.family == "moq_min" and c.entity[:1] == [buyer_id]],
        )

    # 8. OPPORTUNITY
    k = ctx.result.kpis
    if k.lost_kg <= 0 and k.ending_inventory_kg <= 0:
        return LimitingFactor(
            code="OPPORTUNITY",
            message=f"The whole harvest was sold ({k.sold_kg:,.0f} kg): there was nothing left to send to {name}.",
            evidence={"harvest_exhausted": True, "remaining_demand_kg": remaining},
        )
    better = [
        r.buyer_name
        for r in ctx.market.rows
        if r.buyer_id != buyer_id
        and r.net_price_per_kg is not None
        and market is not None
        and market.net_price_per_kg is not None
        and r.net_price_per_kg > market.net_price_per_kg
        and ctx.buyers.get(r.buyer_id) is not None
        and ctx.buyers[r.buyer_id].sold_kg > 0
    ]
    return LimitingFactor(
        code="OPPORTUNITY",
        message=(
            f"Better-paying outlets ({', '.join(better[:3])}) absorbed the volume before {name}."
            if better
            else f"The rest of the harvest was worth more elsewhere (storage for later sales or other buyers) than at {name}."
        ),
        evidence={"better_outlets": better, "remaining_demand_kg": remaining},
    )

"""Opportunity cost of each allocation and trade-offs between competing outlets."""

from __future__ import annotations

from collections import defaultdict

from ..analytics.context import RunContext
from ..domain.explanation import Alternative, Tradeoff


def best_alternative(ctx: RunContext, buyer_id: str) -> Alternative | None:
    """Best other outlet for the kg sent to `buyer_id`: highest estimated net price among reachable
    buyers with demand left. `difference_per_kg` < 0 means the chosen outlet pays more."""
    summary = ctx.buyers[buyer_id]
    if summary.sold_kg <= 0:
        return None
    own = summary.net_price_per_kg
    if own is None:
        return None
    candidates = [
        r
        for r in ctx.market.rows
        if r.buyer_id != buyer_id
        and r.net_price_per_kg is not None
        and r.buyer_id in ctx.buyers
        and ctx.buyers[r.buyer_id].max_demand_kg - ctx.buyers[r.buyer_id].sold_kg > 0
    ]
    if not candidates:
        return None
    alt = max(candidates, key=lambda r: (r.net_price_per_kg, r.buyer_id))  # type: ignore[arg-type,return-value]
    assert alt.net_price_per_kg is not None
    diff = round(alt.net_price_per_kg - own, 4)
    verdict = "would earn" if diff > 0 else "would lose"
    return Alternative(
        buyer_id=alt.buyer_id,
        buyer_name=alt.buyer_name,
        net_price_per_kg=alt.net_price_per_kg,
        difference_per_kg=diff,
        message=f"Sending these {summary.sold_kg:,.0f} kg to {alt.buyer_name} instead of {summary.buyer_name} "
        f"{verdict} {abs(diff):.3f} per kg (estimated at full truck load).",
    )


def tradeoffs(ctx: RunContext) -> list[Tradeoff]:
    """Buyers competing for the same binding fleet resource on the same day."""
    served: dict[tuple[str, int], set[str]] = defaultdict(set)
    for t in ctx.result.trips:
        served[(t.vehicle_type_id, t.day)].add(t.buyer_id)

    pairs: dict[tuple[str, tuple[str, ...]], list[int]] = defaultdict(list)
    labels: dict[str, str] = {}
    for family in ("fleet_time", "fleet_trips"):
        for c in ctx.binding(family):
            buyers = tuple(sorted(served.get((c.entity[0], c.day), set()) if c.day is not None else ()))
            if len(buyers) < 2:
                continue
            group = f"{c.family}|{c.entity[0]}|"
            labels[group] = c.label.split(" (day ")[0]
            pairs[(group, buyers)].append(c.day)  # type: ignore[arg-type]

    result = []
    for (group, buyers), days in sorted(pairs.items()):
        names = [ctx.name_of(b) for b in buyers]
        result.append(
            Tradeoff(
                constraint_key=group,
                label=labels[group],
                buyer_ids=list(buyers),
                message=f"{', '.join(names)} compete for {labels[group].lower()} on {len(days)} day(s) "
                f"({', '.join(str(d) for d in sorted(days)[:5])}{'...' if len(days) > 5 else ''}).",
            )
        )
    return result

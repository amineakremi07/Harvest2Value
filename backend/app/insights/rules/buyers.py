"""LOW_MARGIN_BUYER, DEMAND_BOTTLENECK and UNSERVED_PROFITABLE_BUYER."""

from __future__ import annotations

from ...domain.enums import InsightCategory, Severity
from ...domain.insight import InsightCandidate
from ...explain.binding import really_binding
from ..base import InsightRule, RuleContext, candidate, metric


def _low_margin(ctx: RuleContext) -> list[InsightCandidate]:
    limit = ctx.thresholds.low_margin_buyer_ratio_pct
    found = []
    for b in ctx.run.result.buyers:
        if b.sold_kg <= 0 or b.net_price_per_kg is None or b.revenue <= 0:
            continue
        price = b.revenue / b.sold_kg
        ratio = round(100 * b.net_price_per_kg / price, 2)
        if ratio >= limit:
            continue
        found.append(
            candidate(
                LOW_MARGIN_BUYER,
                ctx,
                severity=Severity.INFO,
                metrics=[
                    metric("net_price_per_kg", b.net_price_per_kg, "currency/kg", f"buyers[{b.buyer_id}].net_price_per_kg"),
                    metric("avg_price_per_kg", round(price, 4), "currency/kg", f"buyers[{b.buyer_id}].revenue / sold_kg"),
                    metric("net_to_price_pct", ratio, "%", "net_price_per_kg / avg_price_per_kg x 100"),
                    metric("sold_kg", b.sold_kg, "kg", f"buyers[{b.buyer_id}].sold_kg"),
                ],
                thresholds={"ratio_pct": limit},
                formula_id="net_price_per_kg = (revenue - transport_cost) / sold_kg",
                params={"buyer": b.buyer_name, "net_price_per_kg": b.net_price_per_kg, "ratio_pct": ratio},
                entity={"type": "buyer", "id": b.buyer_id},
            )
        )
    return found


LOW_MARGIN_BUYER = InsightRule(
    id="LOW_MARGIN_BUYER",
    version=1,
    category=InsightCategory.INFO,
    message="{buyer} keeps only {net_price_per_kg}/kg after transport ({ratio_pct} % of the price paid).",
    evaluate=_low_margin,
)


def _demand_bottleneck(ctx: RuleContext) -> list[InsightCandidate]:
    probes = {p.constraint_key: p for p in (ctx.run.sensitivity.probes if ctx.run.sensitivity else []) if p.constraint_key and p.significant}
    found = []
    for b in ctx.run.result.buyers:
        binding = [c for c in ctx.run.binding("demand_max", b.buyer_id) if really_binding(c, ctx.run)]
        if not binding:
            continue
        key = f"demand_max|{b.buyer_id}|"
        probe = probes.get(key)
        dual = next((c.dual for c in binding if c.dual is not None and c.dual_reliable), None)
        if probe is not None and probe.delta_objective is not None:
            gain, source, basis = probe.delta_objective, f"sensitivity.probes[{key}]", "probe"
        elif dual is not None:
            gain, source, basis = dual, f"constraints[{key}].dual", "dual"
        else:
            continue
        if gain <= ctx.thresholds.min_gain:
            continue
        found.append(
            candidate(
                DEMAND_BOTTLENECK,
                ctx,
                severity=Severity.WARNING,
                metrics=[
                    metric("sold_kg", b.sold_kg, "kg", f"buyers[{b.buyer_id}].sold_kg"),
                    metric("max_demand_kg", b.max_demand_kg, "kg", f"buyers[{b.buyer_id}].max_demand_kg"),
                    metric("gain", round(gain, 4), "currency" if basis == "probe" else "currency/kg", source),
                ],
                thresholds={"min_gain": ctx.thresholds.min_gain},
                formula_id="probe: objective(+10 % demand) - objective" if basis == "probe" else "dual of demand_max (fixed-integer LP)",
                params={
                    "buyer": b.buyer_name,
                    "max_demand_kg": b.max_demand_kg,
                    "gain": round(gain, 2),
                    "basis": "for +10 % demand" if basis == "probe" else "per extra kg",
                },
                entity={"type": "buyer", "id": b.buyer_id},
                suggested_changes=[
                    {"op": "buyer_demand", "target": b.buyer_id, "params": {"field": "max_demand_kg", "mode": "relative_pct", "value": 10}}
                ],
            )
        )
    return found


DEMAND_BOTTLENECK = InsightRule(
    id="DEMAND_BOTTLENECK",
    version=1,
    category=InsightCategory.OPPORTUNITY,
    message="{buyer} takes its full {max_demand_kg} kg; more demand there would add {gain} ({basis}).",
    evaluate=_demand_bottleneck,
)


def _unserved_profitable(ctx: RuleContext) -> list[InsightCandidate]:
    found = []
    for b in ctx.run.result.buyers:
        row = ctx.run.market_rows.get(b.buyer_id)
        if b.sold_kg > 0 or row is None or row.net_price_per_kg is None or row.net_price_per_kg <= 0:
            continue
        found.append(
            candidate(
                UNSERVED_PROFITABLE_BUYER,
                ctx,
                severity=Severity.INFO,
                metrics=[
                    metric("estimated_net_price_per_kg", row.net_price_per_kg, "currency/kg", f"market[{b.buyer_id}].net_price_per_kg"),
                    metric("market_rank", row.rank, "rank", f"market[{b.buyer_id}].rank"),
                    metric("max_demand_kg", b.max_demand_kg, "kg", f"buyers[{b.buyer_id}].max_demand_kg"),
                ],
                formula_id="net_price_per_kg = price - trip cost / useful load - legacy cost per kg",
                params={"buyer": b.buyer_name, "net_price_per_kg": row.net_price_per_kg, "rank": row.rank},
                entity={"type": "buyer", "id": b.buyer_id},
            )
        )
    return found


UNSERVED_PROFITABLE_BUYER = InsightRule(
    id="UNSERVED_PROFITABLE_BUYER",
    version=1,
    category=InsightCategory.OPPORTUNITY,
    message="{buyer} is not served although it would pay an estimated {net_price_per_kg}/kg net (rank {rank}); "
    "see its limiting factor in the explanation.",
    evaluate=_unserved_profitable,
)

RULES = [LOW_MARGIN_BUYER, DEMAND_BOTTLENECK, UNSERVED_PROFITABLE_BUYER]

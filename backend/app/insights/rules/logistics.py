"""HIGH_TRANSPORT_SHARE, FLEET_BOTTLENECK and COLD_CHAIN_GAP."""

from __future__ import annotations

from ...domain.enums import CropType, InsightCategory, Severity
from ...domain.insight import InsightCandidate
from ..base import InsightRule, RuleContext, candidate, metric


def _transport_share(ctx: RuleContext) -> list[InsightCandidate]:
    k = ctx.run.result.kpis
    t = ctx.thresholds
    if k.realized_revenue <= 0:
        return []
    share = round(100 * k.transport_cost / k.realized_revenue, 2)
    if share <= t.high_transport_share_pct:
        return []
    return [
        candidate(
            HIGH_TRANSPORT_SHARE,
            ctx,
            severity=Severity.CRITICAL if share > t.high_transport_critical_pct else Severity.WARNING,
            metrics=[
                metric("transport_share_pct", share, "%", "kpis.transport_cost / kpis.realized_revenue"),
                metric("transport_cost", k.transport_cost, "currency", "kpis.transport_cost"),
                metric("realized_revenue", k.realized_revenue, "currency", "kpis.realized_revenue"),
            ],
            thresholds={"warning_pct": t.high_transport_share_pct, "critical_pct": t.high_transport_critical_pct},
            formula_id="transport_share_pct = transport_cost / realized_revenue x 100",
            params={"share_pct": share, "transport_cost": k.transport_cost, "threshold_pct": t.high_transport_share_pct},
        )
    ]


HIGH_TRANSPORT_SHARE = InsightRule(
    id="HIGH_TRANSPORT_SHARE",
    version=1,
    category=InsightCategory.RISK,
    message="Transport costs {transport_cost}, {share_pct} % of revenue (threshold {threshold_pct} %).",
    evaluate=_transport_share,
)


def _fleet_bottleneck(ctx: RuleContext) -> list[InsightCandidate]:
    run = ctx.run
    probes = {p.constraint_key: p for p in (run.sensitivity.probes if run.sensitivity else []) if p.constraint_key}
    open_demand = sum(max(0.0, b.max_demand_kg - b.sold_kg) for b in run.result.buyers)
    found = []
    for v in run.instance.vehicles:
        days = sorted({c.day for f in ("fleet_time", "fleet_trips") for c in run.binding(f, v.id) if c.day is not None})
        if not days:
            continue
        probe = probes.get(f"fleet_time|{v.id}|") or probes.get(f"fleet_trips|{v.id}|")
        if probe is not None and probe.delta_objective is not None:
            if not probe.significant or probe.delta_objective <= ctx.thresholds.min_gain:
                continue  # measured: one more vehicle does not pay
            gain: float | None = probe.delta_objective
        elif run.result.kpis.lost_kg > 0 and open_demand > 0:
            gain = None  # binding while produce is lost and demand is open: worth probing
        else:
            continue
        metrics = [
            metric("binding_days", len(days), "days", f"constraints fleet_time|{v.id}| / fleet_trips|{v.id}|"),
            metric("vehicle_count", v.count, "vehicles", f"vehicle_types[{v.id}].count"),
            metric("lost_kg", run.result.kpis.lost_kg, "kg", "kpis.lost_kg"),
        ]
        if gain is not None:
            metrics.append(metric("gain_one_more_vehicle", round(gain, 4), "currency", f"sensitivity.probes[fleet|{v.id}]"))
        found.append(
            candidate(
                FLEET_BOTTLENECK,
                ctx,
                severity=Severity.WARNING,
                metrics=metrics,
                thresholds={"min_gain": ctx.thresholds.min_gain},
                formula_id="fleet hours or trips used = available on binding days",
                params={
                    "vehicle": v.name,
                    "days": len(days),
                    "gain": "not computed yet" if gain is None else f"+{gain:,.2f}",
                },
                entity={"type": "vehicle", "id": v.id},
                suggested_changes=[{"op": "vehicle_count", "target": v.id, "params": {"mode": "delta", "value": 1}}],
            )
        )
    return found


FLEET_BOTTLENECK = InsightRule(
    id="FLEET_BOTTLENECK",
    version=1,
    category=InsightCategory.OPPORTUNITY,
    message="The {vehicle} fleet is fully used on {days} day(s); one more vehicle: {gain}.",
    evaluate=_fleet_bottleneck,
)


def _cold_chain_gap(ctx: RuleContext) -> list[InsightCandidate]:
    run = ctx.run
    crop = run.payload.crop(run.result.crop_id)
    reefers = [v for v in run.instance.vehicles if v.refrigerated]
    cold_buyers = [b for b in run.instance.buyers if b.requires_cold_chain]
    sensitive = crop.requires_cold_chain or crop.type == CropType.PERISHABLE or bool(cold_buyers)
    if not sensitive or reefers:
        return []
    idle_reefers = [v for v in run.payload.vehicle_types if v.refrigerated and v.count == 0]
    suggestions = (
        [{"op": "vehicle_count", "target": idle_reefers[0].id, "params": {"mode": "absolute", "value": 1}}] if idle_reefers else []
    )
    return [
        candidate(
            COLD_CHAIN_GAP,
            ctx,
            severity=Severity.CRITICAL if crop.requires_cold_chain or cold_buyers else Severity.WARNING,
            metrics=[
                metric("refrigerated_vehicles", 0, "vehicles", "vehicle_types[refrigerated].count"),
                metric("crop_type", crop.type.value, "", f"crops[{crop.id}].type"),
                metric("cold_chain_buyers", len(cold_buyers), "buyers", "buyers[requires_cold_chain]"),
            ],
            formula_id="perishable or cold-chain crop/buyer and no refrigerated vehicle in service",
            params={"crop": crop.name, "cold_buyers": len(cold_buyers)},
            entity={"type": "crop", "id": crop.id},
            suggested_changes=suggestions,
        )
    ]


COLD_CHAIN_GAP = InsightRule(
    id="COLD_CHAIN_GAP",
    version=1,
    category=InsightCategory.RISK,
    message="{crop} is perishable or needs a cold chain ({cold_buyers} buyer(s) require it) but no refrigerated "
    "vehicle is in service.",
    evaluate=_cold_chain_gap,
)

RULES = [HIGH_TRANSPORT_SHARE, FLEET_BOTTLENECK, COLD_CHAIN_GAP]

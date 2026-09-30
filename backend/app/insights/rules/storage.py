"""STORAGE_NEAR_FULL (peak occupancy >= 90 %) and STORAGE_IDLE (peak < 20 % while produce is lost)."""

from __future__ import annotations

from ...domain.enums import InsightCategory, Severity
from ...domain.insight import InsightCandidate
from ..base import InsightRule, RuleContext, candidate, metric


def _near_full(ctx: RuleContext) -> list[InsightCandidate]:
    limit = ctx.thresholds.storage_near_full_pct
    found = []
    for u in ctx.run.facility_usage:
        if not u.usable or u.peak_pct is None or u.peak_pct < limit:
            continue
        found.append(
            candidate(
                STORAGE_NEAR_FULL,
                ctx,
                severity=Severity.WARNING,
                metrics=[
                    metric("peak_pct", u.peak_pct, "%", f"inventory[{u.facility_id}] peak / capacity"),
                    metric("peak_kg", u.peak_kg, "kg", f"inventory[{u.facility_id}]"),
                    metric("capacity_kg", u.capacity_kg, "kg", f"storage_facilities[{u.facility_id}].capacity_kg"),
                    metric("full_days", len(u.full_days), "days", f"constraints storage_capacity|{u.facility_id}|"),
                ],
                thresholds={"near_full_pct": limit},
                formula_id="peak_pct = max over days of end-of-day stock / capacity x 100",
                params={"facility": u.name, "peak_pct": u.peak_pct, "full_days": len(u.full_days)},
                entity={"type": "storage", "id": u.facility_id},
                suggested_changes=[
                    {"op": "storage_capacity", "target": u.facility_id, "params": {"mode": "relative_pct", "value": 25}}
                ],
            )
        )
    return found


STORAGE_NEAR_FULL = InsightRule(
    id="STORAGE_NEAR_FULL",
    version=1,
    category=InsightCategory.OPPORTUNITY,
    message="{facility} peaks at {peak_pct} % of its capacity (full on {full_days} day(s)).",
    evaluate=_near_full,
)


def _idle(ctx: RuleContext) -> list[InsightCandidate]:
    k = ctx.run.result.kpis
    if k.lost_kg <= ctx.thresholds.storage_idle_min_lost_kg:
        return []
    limit = ctx.thresholds.storage_idle_pct
    found = []
    for u in ctx.run.facility_usage:
        if not u.usable or u.peak_pct is None or u.peak_pct >= limit or u.capacity_kg <= 0:
            continue
        found.append(
            candidate(
                STORAGE_IDLE,
                ctx,
                severity=Severity.INFO,
                metrics=[
                    metric("peak_pct", u.peak_pct, "%", f"inventory[{u.facility_id}] peak / capacity"),
                    metric("lost_kg", k.lost_kg, "kg", "kpis.lost_kg"),
                    metric("cost_per_kg_per_day", next(f.cost_per_kg_day for f in ctx.run.instance.facilities if f.id == u.facility_id), "currency/kg/day", f"storage_facilities[{u.facility_id}].cost_per_kg_per_day"),
                ],
                thresholds={"idle_pct": limit, "min_lost_kg": ctx.thresholds.storage_idle_min_lost_kg},
                formula_id="peak_pct = max over days of end-of-day stock / capacity x 100",
                params={"facility": u.name, "peak_pct": u.peak_pct, "lost_kg": k.lost_kg},
                entity={"type": "storage", "id": u.facility_id},
            )
        )
    return found


STORAGE_IDLE = InsightRule(
    id="STORAGE_IDLE",
    version=1,
    category=InsightCategory.INFO,
    message="{facility} is barely used (peak {peak_pct} %) while {lost_kg} kg are lost: storing there does not pay "
    "(cost, shelf life or later prices).",
    evaluate=_idle,
)

RULES = [STORAGE_NEAR_FULL, STORAGE_IDLE]

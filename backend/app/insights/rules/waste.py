"""HIGH_WASTE: waste rate above 10 % (warning) or 20 % (critical)."""

from __future__ import annotations

from ...domain.enums import InsightCategory, Severity
from ...domain.insight import InsightCandidate
from ..base import InsightRule, RuleContext, candidate, metric


def _high_waste(ctx: RuleContext) -> list[InsightCandidate]:
    k = ctx.run.result.kpis
    t = ctx.thresholds
    if k.waste_rate_pct <= t.high_waste_warning_pct:
        return []
    severity = Severity.CRITICAL if k.waste_rate_pct > t.high_waste_critical_pct else Severity.WARNING
    suggestions = []
    full = [u for u in ctx.run.facility_usage if u.usable and u.peak_pct is not None and u.peak_pct >= t.storage_near_full_pct]
    if full:
        suggestions.append(
            {"op": "storage_capacity", "target": full[0].facility_id, "params": {"mode": "relative_pct", "value": 25}}
        )
    return [
        candidate(
            HIGH_WASTE,
            ctx,
            severity=severity,
            metrics=[
                metric("waste_rate_pct", k.waste_rate_pct, "%", "kpis.waste_rate_pct"),
                metric("lost_kg", k.lost_kg, "kg", "kpis.lost_kg"),
                metric("lost_value", k.lost_value, "currency", "kpis.lost_value"),
            ],
            thresholds={"warning_pct": t.high_waste_warning_pct, "critical_pct": t.high_waste_critical_pct},
            formula_id="waste_rate_pct = lost_kg / harvest_kg x 100",
            params={"waste_rate_pct": k.waste_rate_pct, "lost_kg": k.lost_kg, "threshold_pct": t.high_waste_warning_pct},
            suggested_changes=suggestions,
        )
    ]


HIGH_WASTE = InsightRule(
    id="HIGH_WASTE",
    version=1,
    category=InsightCategory.RISK,
    message="{waste_rate_pct} % of the harvest is lost ({lost_kg} kg), above the {threshold_pct} % threshold.",
    evaluate=_high_waste,
)

RULES = [HIGH_WASTE]

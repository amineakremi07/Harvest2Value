"""CONCENTRATION: more than 60 % of the sold kg go to a single buyer."""

from __future__ import annotations

from ...domain.enums import InsightCategory, Severity
from ...domain.insight import InsightCandidate
from ..base import InsightRule, RuleContext, candidate, metric


def _concentration(ctx: RuleContext) -> list[InsightCandidate]:
    k = ctx.run.result.kpis
    t = ctx.thresholds
    if k.sold_kg <= 0 or len(ctx.run.result.buyers) < 2:
        return []
    top = max(ctx.run.result.buyers, key=lambda b: (b.sold_kg, b.buyer_id))
    share = round(100 * top.sold_kg / k.sold_kg, 2)
    if share <= t.concentration_pct:
        return []
    return [
        candidate(
            CONCENTRATION,
            ctx,
            severity=Severity.CRITICAL if share > t.concentration_critical_pct else Severity.WARNING,
            metrics=[
                metric("share_pct", share, "%", f"buyers[{top.buyer_id}].sold_kg / kpis.sold_kg"),
                metric("buyer_sold_kg", top.sold_kg, "kg", f"buyers[{top.buyer_id}].sold_kg"),
                metric("sold_kg", k.sold_kg, "kg", "kpis.sold_kg"),
            ],
            thresholds={"warning_pct": t.concentration_pct, "critical_pct": t.concentration_critical_pct},
            formula_id="share_pct = buyer sold_kg / total sold_kg x 100",
            params={"buyer": top.buyer_name, "share_pct": share},
            entity={"type": "buyer", "id": top.buyer_id},
        )
    ]


CONCENTRATION = InsightRule(
    id="CONCENTRATION",
    version=1,
    category=InsightCategory.RISK,
    message="{buyer} receives {share_pct} % of the kg sold: the plan depends on a single buyer.",
    evaluate=_concentration,
)

RULES = [CONCENTRATION]

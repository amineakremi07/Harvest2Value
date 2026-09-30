"""EXPIRY_LOSS (stock expired before being sold) and ENDING_STOCK_UNSOLD (stock left at the end
of the horizon with no salvage value configured)."""

from __future__ import annotations

from ...domain.enums import InsightCategory, Severity
from ...domain.insight import InsightCandidate
from ..base import InsightRule, RuleContext, candidate, metric


def _expiry_loss(ctx: RuleContext) -> list[InsightCandidate]:
    expired = ctx.run.waste_by_kind.get("expired", 0.0)
    if expired <= 0:
        return []
    k = ctx.run.result.kpis
    share = round(100 * expired / k.harvest_kg, 2) if k.harvest_kg > 0 else 0.0
    value = round(sum(w.value_lost for w in ctx.run.result.waste if w.kind == "expired"), 2)
    lots = sorted({w.lot_id for w in ctx.run.result.waste if w.kind == "expired"})
    crop = ctx.run.payload.crop(ctx.run.result.crop_id)
    return [
        candidate(
            EXPIRY_LOSS,
            ctx,
            severity=Severity.CRITICAL if share > ctx.thresholds.expiry_critical_share_pct else Severity.WARNING,
            metrics=[
                metric("expired_kg", round(expired, 2), "kg", "waste[kind=expired].kg"),
                metric("expired_share_pct", share, "%", "expired_kg / kpis.harvest_kg"),
                metric("expired_value", value, "currency", "waste[kind=expired].value_lost"),
            ],
            thresholds={"critical_share_pct": ctx.thresholds.expiry_critical_share_pct},
            formula_id="expired_kg = sum of stock left on the last shelf-life day",
            params={"expired_kg": round(expired, 2), "lot_count": len(lots), "shelf_life_days": crop.shelf_life_ambient_days},
            entity={"type": "crop", "id": crop.id},
            suggested_changes=[{"op": "shelf_life", "target": crop.id, "params": {"field": "ambient", "mode": "delta", "value": 1}}],
        )
    ]


EXPIRY_LOSS = InsightRule(
    id="EXPIRY_LOSS",
    version=1,
    category=InsightCategory.RISK,
    message="{expired_kg} kg from {lot_count} lot(s) expired in storage before being sold "
    "(ambient shelf life {shelf_life_days} days).",
    evaluate=_expiry_loss,
)


def _ending_stock_unsold(ctx: RuleContext) -> list[InsightCandidate]:
    k = ctx.run.result.kpis
    salvage = ctx.run.config.salvage_value_pct
    if k.ending_inventory_kg <= 0 or salvage > 0:
        return []
    return [
        candidate(
            ENDING_STOCK_UNSOLD,
            ctx,
            severity=Severity.INFO,
            metrics=[
                metric("ending_inventory_kg", k.ending_inventory_kg, "kg", "kpis.ending_inventory_kg"),
                metric("salvage_value_pct", salvage, "%", "config.salvage_value_pct"),
            ],
            formula_id="ending_inventory_kg = stock still sellable at the end of the horizon",
            params={"ending_inventory_kg": k.ending_inventory_kg, "horizon_days": ctx.run.result.horizon_days},
        )
    ]


ENDING_STOCK_UNSOLD = InsightRule(
    id="ENDING_STOCK_UNSOLD",
    version=1,
    category=InsightCategory.INFO,
    message="{ending_inventory_kg} kg are still in stock after {horizon_days} days and count for nothing "
    "(salvage value 0 %): extend the horizon or set a salvage value.",
    evaluate=_ending_stock_unsold,
)

RULES = [EXPIRY_LOSS, ENDING_STOCK_UNSOLD]

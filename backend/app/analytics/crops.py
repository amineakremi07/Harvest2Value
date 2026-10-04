"""Crop section: shelf life, quality decay curve, value per storage day, lot outcomes, risk level."""

from __future__ import annotations

from collections import defaultdict
from typing import Literal

from pydantic import BaseModel, Field

from ..domain.enums import CropType
from .context import RunContext


class ValuePoint(BaseModel):
    age_days: int
    price_multiplier: float = Field(description="1 - quality decay x age, floored at 0")
    value_per_kg: float = Field(description="Reference price x multiplier")
    remaining_ambient_kg_per_kg: float = Field(description="Share left after daily ambient losses")


class LotOutcome(BaseModel):
    lot_id: str
    quantity_kg: float
    available_day: int
    sold_kg: float
    lost_kg: float
    ending_kg: float


class CropsSection(BaseModel):
    run_id: str
    crop_id: str
    crop_name: str
    type: CropType
    reference_price_per_kg: float
    shelf_life_ambient_days: int
    shelf_life_cold_days: int | None
    quality_decay_pct_per_day: float
    loss_rate_pct_per_day_ambient: float
    loss_rate_pct_per_day_cold: float | None
    requires_cold_chain: bool
    risk_level: Literal["high", "medium", "low"]
    risk_reasons: list[str]
    value_curve: list[ValuePoint]
    lots: list[LotOutcome]


def _risk(crop_type: CropType, shelf_ambient: int, lost_pct: float) -> tuple[Literal["high", "medium", "low"], list[str]]:
    reasons = []
    if crop_type == CropType.PERISHABLE:
        reasons.append("perishable crop")
    if shelf_ambient <= 3:
        reasons.append(f"ambient shelf life of {shelf_ambient} day(s)")
    if lost_pct > 10:
        reasons.append(f"{lost_pct:.1f} % of the harvest lost in this plan")
    if len(reasons) >= 2 or lost_pct > 20:
        return "high", reasons
    if reasons or shelf_ambient <= 14:
        return "medium", reasons or [f"ambient shelf life of {shelf_ambient} days"]
    return "low", reasons


def crops(ctx: RunContext) -> CropsSection:
    crop = ctx.payload.crop(ctx.result.crop_id)
    decay = crop.quality_decay_pct_per_day / 100
    loss = crop.loss_rate_pct_per_day_ambient / 100
    longest = max(crop.shelf_life_ambient_days, crop.shelf_life_cold_days or 0)
    curve = [
        ValuePoint(
            age_days=age,
            price_multiplier=round(max(0.0, 1 - decay * age), 4),
            value_per_kg=round(crop.reference_price_per_kg * max(0.0, 1 - decay * age), 4),
            remaining_ambient_kg_per_kg=round((1 - loss) ** age, 4),
        )
        for age in range(min(longest, 60) + 1)
    ]

    sold: dict[str, float] = defaultdict(float)
    for a in ctx.result.allocations:
        sold[a.lot_id] += a.kg
    lost: dict[str, float] = defaultdict(float)
    for w in ctx.result.waste:
        lost[w.lot_id] += w.kg
    lots = []
    for lot in ctx.instance.lots:
        ending = max(0.0, lot.quantity - sold[lot.id] - lost[lot.id])
        lots.append(
            LotOutcome(
                lot_id=lot.id,
                quantity_kg=lot.quantity,
                available_day=lot.day,
                sold_kg=round(sold[lot.id], 2),
                lost_kg=round(lost[lot.id], 2),
                ending_kg=round(ending, 2),
            )
        )

    level, reasons = _risk(crop.type, crop.shelf_life_ambient_days, ctx.result.kpis.waste_rate_pct)
    return CropsSection(
        run_id=ctx.run_id,
        crop_id=crop.id,
        crop_name=crop.name,
        type=crop.type,
        reference_price_per_kg=crop.reference_price_per_kg,
        shelf_life_ambient_days=crop.shelf_life_ambient_days,
        shelf_life_cold_days=crop.shelf_life_cold_days,
        quality_decay_pct_per_day=crop.quality_decay_pct_per_day,
        loss_rate_pct_per_day_ambient=crop.loss_rate_pct_per_day_ambient,
        loss_rate_pct_per_day_cold=crop.loss_rate_pct_per_day_cold,
        requires_cold_chain=crop.requires_cold_chain,
        risk_level=level,
        risk_reasons=reasons,
        value_curve=curve,
        lots=lots,
    )

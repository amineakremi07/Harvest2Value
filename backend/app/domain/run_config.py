"""What to optimize and how (plan §6.3, §9)."""

from __future__ import annotations

from pydantic import Field, model_validator

from .dataset import DomainModel, EntityId, Percent
from .enums import ObjectiveKind

MAX_HORIZON_DAYS = 60
# Relative MIP gap: CBC stops once the plan is proven within 1 % of the best possible one.
# Realistic multi-week instances reach 1 % in about a second but can take minutes for 0.1 %.
DEFAULT_GAP = 0.01


class ObjectiveWeights(DomainModel):
    """Relative importance of each criterion in `weighted` mode (normalized, see objectives.py)."""

    profit: float = Field(default=1.0, ge=0, le=100)
    waste: float = Field(default=0.0, ge=0, le=100)
    cost: float = Field(default=0.0, ge=0, le=100)

    @model_validator(mode="after")
    def _not_all_zero(self) -> ObjectiveWeights:
        if self.profit + self.waste + self.cost <= 0:
            raise ValueError("at least one weight must be > 0")
        return self


class RunConfig(DomainModel):
    crop_id: EntityId | None = Field(default=None, description="Required when the dataset has several harvested crops")
    objective: ObjectiveKind = ObjectiveKind.PROFIT
    weights: ObjectiveWeights | None = None
    horizon_days: int | None = Field(
        default=None, ge=1, le=MAX_HORIZON_DAYS, description="Default: last lot day + longest shelf life, capped at 60"
    )
    time_limit_s: int | None = Field(default=None, ge=1, le=600)
    gap: float | None = Field(default=None, ge=0, le=0.5, description=f"Relative MIP gap, default {DEFAULT_GAP}")
    salvage_value_pct: Percent = Field(
        default=0.0, description="Value of still-sellable ending inventory, in % of the crop reference price"
    )
    disposal_cost_per_kg: float = Field(default=0.0, ge=0, le=1e3)
    service_level_min: float | None = Field(
        default=None, ge=0, le=1, description="`cost` mode: minimum share of the harvest that must be sold"
    )
    min_profit: float | None = Field(default=None, description="`waste` mode: optional realized-profit floor")

    @model_validator(mode="after")
    def _mode_parameters(self) -> RunConfig:
        if self.objective == ObjectiveKind.WEIGHTED and self.weights is None:
            raise ValueError("objective 'weighted' requires weights")
        if self.objective == ObjectiveKind.COST and self.service_level_min is None:
            raise ValueError("objective 'cost' requires service_level_min (otherwise selling nothing is cheapest)")
        return self

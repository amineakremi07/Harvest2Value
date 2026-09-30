"""Alert thresholds (plan §16). One place, overridable per call (later: per workspace settings)."""

from __future__ import annotations

from pydantic import BaseModel, Field


class Thresholds(BaseModel):
    high_waste_warning_pct: float = Field(default=10.0, description="HIGH_WASTE warning above this waste rate")
    high_waste_critical_pct: float = Field(default=20.0, description="HIGH_WASTE critical above this waste rate")
    expiry_critical_share_pct: float = Field(default=10.0, description="EXPIRY_LOSS critical above this share of the harvest")
    storage_near_full_pct: float = Field(default=90.0, description="STORAGE_NEAR_FULL at or above this peak occupancy")
    storage_idle_pct: float = Field(default=20.0, description="STORAGE_IDLE below this peak occupancy (with losses)")
    storage_idle_min_lost_kg: float = Field(default=0.0, description="STORAGE_IDLE only when more than this is lost")
    low_margin_buyer_ratio_pct: float = Field(default=20.0, description="LOW_MARGIN_BUYER: net price / price below this")
    high_transport_share_pct: float = Field(default=25.0, description="HIGH_TRANSPORT_SHARE: transport / revenue above this")
    high_transport_critical_pct: float = Field(default=50.0, description="HIGH_TRANSPORT_SHARE critical above this")
    concentration_pct: float = Field(default=60.0, description="CONCENTRATION: one buyer takes more than this share of sold kg")
    concentration_critical_pct: float = Field(default=85.0, description="CONCENTRATION critical above this share")
    min_gain: float = Field(default=0.0, description="Bottleneck rules: minimum objective gain to report")


DEFAULT_THRESHOLDS = Thresholds()

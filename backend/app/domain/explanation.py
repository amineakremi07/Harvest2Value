"""Deterministic explanation of a run (plan §15). Built only from solver values and input data."""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field

from .results import ConstraintInfo

LimitingCode = Literal[
    "UNPROFITABLE",
    "DEMAND_CAP",
    "DAILY_DEMAND_CAP",
    "FLEET_TIME",
    "COLD_CHAIN",
    "SHELF_LIFE_WINDOW",
    "MOQ",
    "OPPORTUNITY",
    "STORAGE_CAP",  # storage cards only: the facility was full
]

# Buyer limiting factors are checked in this exact order (plan §15): the first one that applies is the limiting factor.
LIMITING_ORDER: tuple[LimitingCode, ...] = (
    "UNPROFITABLE",
    "DEMAND_CAP",
    "DAILY_DEMAND_CAP",
    "FLEET_TIME",
    "COLD_CHAIN",
    "SHELF_LIFE_WINDOW",
    "MOQ",
    "OPPORTUNITY",
)


class LimitingFactor(BaseModel):
    code: LimitingCode
    message: str
    evidence: dict[str, Any] = Field(default_factory=dict)
    constraint_keys: list[str] = Field(default_factory=list)


class MarginalValue(BaseModel):
    """`probe` (exact, re-optimized) is preferred; `dual` is a local indicator only."""

    kind: Literal["probe", "dual"]
    label: str
    delta_objective: float
    change: dict[str, Any] | None = None
    reliable: bool


class Alternative(BaseModel):
    buyer_id: str
    buyer_name: str
    net_price_per_kg: float
    difference_per_kg: float = Field(description="Alternative net price - chosen net price (negative: chosen is better)")
    message: str


class DecisionCard(BaseModel):
    kind: Literal["buyer", "storage", "waste"]
    entity_id: str
    name: str
    decision: str
    metrics: dict[str, float | int | str | None]
    limiting_factor: LimitingFactor | None = None
    marginal_values: list[MarginalValue] = Field(default_factory=list)
    alternative: Alternative | None = None


class Bottleneck(BaseModel):
    """A binding constraint family on one entity, over all the days it binds."""

    key: str = Field(description="family|entity| (day-independent)")
    family: str
    entity: list[str]
    label: str
    binding_days: list[int | None]
    dual: float | None = Field(default=None, description="Largest reliable dual over the binding days")
    probe_gain: float | None = Field(default=None, description="Objective gain of the matching probe, if computed")
    suggested_change: dict[str, Any] | None = Field(default=None, description="Scenario change that relaxes it (used by probes)")
    suggested_label: str | None = None
    rank: int = 0


class Tradeoff(BaseModel):
    constraint_key: str
    label: str
    buyer_ids: list[str]
    message: str


class RunExplanation(BaseModel):
    run_id: str
    decisions: list[DecisionCard]
    binding: list[ConstraintInfo]
    bottlenecks: list[Bottleneck]
    tradeoffs: list[Tradeoff]
    sensitivity_computed: bool

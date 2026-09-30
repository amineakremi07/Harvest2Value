"""Optimization output. Every number is computed by the backend from solver values (never by an LLM).

Money is in the dataset currency, quantities in kg, `*_pct` in percent (0-100).
"""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field

from .enums import ObjectiveKind, SolverOutcome


class Kpis(BaseModel):
    """Plan §11. There is deliberately no `net_profit`: realized profit and inventory value are separate."""

    harvest_kg: float
    sold_kg: float
    realized_revenue: float
    transport_cost: float
    storage_cost: float
    disposal_cost: float
    total_cost: float
    realized_profit: float = Field(description="realized_revenue - total_cost")
    margin_pct: float | None = Field(description="realized_profit / realized_revenue; None without revenue")
    ending_inventory_kg: float = Field(description="Still sellable at the end of the horizon")
    ending_inventory_value: float = Field(description="ending_inventory_kg x salvage value per kg")
    economic_value: float = Field(description="Valeur économique = realized_profit + ending_inventory_value (not a profit)")
    lost_kg: float
    lost_value: float = Field(description="lost_kg x crop reference price (informative)")
    waste_rate_pct: float
    sold_rate_pct: float
    storage_rate_pct: float = Field(description="Share of the harvest that went through a storage facility")
    fulfillment_rate_pct: float | None
    vehicle_utilization_pct: float | None = Field(description="Driving hours used / available (time-limited vehicles)")
    load_factor_pct: float | None = Field(description="kg shipped / capacity of the trips made")
    storage_utilization_peak_pct: float | None
    storage_utilization_avg_pct: float | None
    trips: int
    avg_transport_cost_per_kg: float | None
    avg_storage_days: float | None
    objective_value: float
    best_buyer_id: str | None


class BuyerSummary(BaseModel):
    buyer_id: str
    buyer_name: str
    sold_kg: float
    revenue: float
    transport_cost: float
    net_revenue: float = Field(description="revenue - transport_cost")
    net_price_per_kg: float | None
    max_demand_kg: float
    fulfillment_pct: float


class AllocationRow(BaseModel):
    buyer_id: str
    lot_id: str
    facility_id: str | None = Field(description="None = sold on the harvest day, without storage")
    day: int
    kg: float
    unit_price: float = Field(description="Price after quality decay for the lot's age")
    revenue: float


class InventoryRow(BaseModel):
    day: int
    facility_id: str
    lot_id: str
    kg_end: float
    cost: float


class TripRow(BaseModel):
    day: int
    buyer_id: str
    vehicle_type_id: str
    trips: int
    capacity_kg: float
    cost: float
    hours: float


class WasteRow(BaseModel):
    day: int
    lot_id: str
    facility_id: str | None
    kind: Literal["unsold_direct", "daily_loss", "expired"]
    kg: float
    value_lost: float


class ConstraintInfo(BaseModel):
    key: str
    family: str
    entity: list[str]
    day: int | None
    label: str
    sense: Literal["<=", ">="]
    lhs: float
    rhs: float
    slack: float
    binding: bool
    dual: float | None = None
    dual_reliable: bool | None = None


class DualValue(BaseModel):
    """Local marginal value from the fixed-integer LP: change of the objective per +1 unit of the
    constraint's right-hand side, trips and served-buyer decisions held at their optimal values."""

    key: str
    label: str
    family: str
    value: float
    reliable: bool
    reason: str | None = Field(default=None, description="Why the value is not reliable")


class ProbeResult(BaseModel):
    """Exact effect of a real scenario change, re-optimized with integers (plan §15, method 2)."""

    constraint_key: str | None = Field(default=None, description="Bottleneck the probe relaxes (family|entity|)")
    label: str
    change: dict[str, Any] = Field(description="The scenario change applied (ScenarioChange shape)")
    outcome: SolverOutcome
    objective_value: float | None
    delta_objective: float | None = Field(description="Probe objective - run objective (same gap)")
    significant: bool = Field(default=False, description="False when |delta| <= gap x |objective| (MIP-gap noise band)")
    delta_kpis: dict[str, float] = Field(default_factory=dict)


class SensitivityReport(BaseModel):
    duals: list[DualValue] = Field(default_factory=list)
    duals_available: bool = Field(default=False, description="False when the fixed-integer LP could not be solved")
    probes: list[ProbeResult] = Field(default_factory=list)
    probes_computed: bool = False
    probe_gap: float | None = Field(default=None, description="Relative MIP gap of the run and its probes")


class ConflictInfo(BaseModel):
    key: str
    family: str
    label: str
    relaxation_needed: float = Field(description="Amount by which the constraint must be relaxed (its own unit)")
    unit: str


class Diagnostics(BaseModel):
    """Why a model is infeasible: elastic relaxation of the soft constraints (plan §15)."""

    conflicts: list[ConflictInfo] = Field(default_factory=list)
    suggestions: list[str] = Field(default_factory=list)
    method: Literal["elastic", "none"] = "elastic"


class OptimizationResultModel(BaseModel):
    outcome: SolverOutcome
    outcome_label: str = Field(description="Plain-language meaning of the outcome, including the optimality gap")
    gap_requested: float = Field(description="Relative MIP gap the solver was allowed to stop at (0.01 = 1 %)")
    objective: ObjectiveKind
    crop_id: str
    horizon_days: int
    kpis: Kpis
    buyers: list[BuyerSummary]
    allocations: list[AllocationRow]
    inventory: list[InventoryRow]
    trips: list[TripRow]
    waste: list[WasteRow]
    constraints: list[ConstraintInfo]
    warnings: list[str]
    solve_seconds: float
    sensitivity: SensitivityReport | None = None
    diagnostics: Diagnostics | None = None

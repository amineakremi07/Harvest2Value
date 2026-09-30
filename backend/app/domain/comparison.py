"""Comparison of a baseline run with 1 to 3 other runs (plan §7.3). Computed on demand, not stored."""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field


class Delta(BaseModel):
    abs: float | None
    pct: float | None = Field(description="None when the baseline value is 0 or missing")


class KpiRow(BaseModel):
    kpi: str
    label: str
    unit: str
    better: Literal["higher", "lower", "neutral"]
    values: dict[str, float | None]
    deltas: dict[str, Delta] = Field(description="Per compared run, relative to the baseline")
    best_run_id: str | None


class BuyerCell(BaseModel):
    status: Literal["common", "added", "removed", "absent"]
    sold_kg: float | None
    delta_kg: float | None


class BuyerRow(BaseModel):
    buyer_id: str
    buyer_name: str
    cells: dict[str, BuyerCell]


class SeriesPoint(BaseModel):
    day: int
    values: dict[str, float]


class NotableChange(BaseModel):
    code: str
    run_id: str
    message: str
    params: dict[str, Any]
    magnitude: float = Field(description="Used for ordering (absolute size of the change)")


class RunRef(BaseModel):
    run_id: str
    label: str | None
    scenario_id: str | None
    objective: str


class ComparisonResult(BaseModel):
    baseline_run_id: str
    run_ids: list[str]
    runs: list[RunRef]
    crop_id: str
    kpi_table: list[KpiRow]
    buyer_matrix: list[BuyerRow]
    series: dict[str, list[SeriesPoint]]
    notable_changes: list[NotableChange]

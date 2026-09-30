"""Insights (plan §16): deterministic alerts whose message parameters are their evidence."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field

from .enums import InsightCategory, Severity


class EvidenceMetric(BaseModel):
    key: str
    value: float | int | str | None
    unit: str
    source: str = Field(description="Where the number comes from, e.g. kpis.waste_rate_pct")


class EvidenceThreshold(BaseModel):
    key: str
    value: float


class Evidence(BaseModel):
    metrics: list[EvidenceMetric]
    thresholds: list[EvidenceThreshold] = Field(default_factory=list)
    entities: list[dict[str, str]] = Field(default_factory=list)
    formula_id: str
    run_id: str
    rule_version: int


class InsightCandidate(BaseModel):
    rule_id: str
    rule_version: int
    category: InsightCategory
    severity: Severity
    entity_ref: dict[str, str] | None = None
    evidence: Evidence
    message_key: str
    message_params: dict[str, Any]
    suggested_changes: list[dict[str, Any]] = Field(default_factory=list)

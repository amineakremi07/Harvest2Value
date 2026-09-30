"""Explainability, insights and analytics DTOs that are not domain models."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel

from .runs import RunSummary


class MarginalValuesStatus(BaseModel):
    run_id: str
    status: Literal["computing", "computed"]


class TryInsightResult(BaseModel):
    scenario_id: str
    run_id: str
    run: RunSummary

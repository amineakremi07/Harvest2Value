"""Optimization run DTOs."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field, model_validator
from sqlalchemy.orm import Session

from ....db.models import DatasetVersion, OptimizationRun
from ....domain.enums import ObjectiveKind, RunStatus, SolverOutcome
from ....domain.results import Diagnostics
from ....domain.run_config import RunConfig
from ....domain.scenario import AppliedChange
from ....services.optimization import safe_error_message


class RunCreate(BaseModel):
    dataset_id: str | None = Field(default=None, description="Required unless scenario_id is given")
    version_no: int | None = Field(default=None, ge=1, description="Default: the dataset's current version")
    scenario_id: str | None = Field(default=None, description="Optimize the scenario's effective data")
    config: RunConfig = Field(default_factory=RunConfig)
    label: str | None = Field(default=None, max_length=120)
    use_cache: bool = Field(default=True, description="Reuse a succeeded run with the same effective input and config")

    @model_validator(mode="after")
    def _source(self) -> RunCreate:
        if self.dataset_id is None and self.scenario_id is None:
            raise ValueError("Provide dataset_id or scenario_id")
        return self


class RunRerun(BaseModel):
    config_overrides: dict[str, Any] = Field(default_factory=dict, description="RunConfig fields to change")
    label: str | None = Field(default=None, max_length=120)
    use_cache: bool = True


class RunError(BaseModel):
    code: str
    message: str | None


class RunHeadlineKpis(BaseModel):
    realized_profit: float
    realized_revenue: float
    sold_kg: float
    lost_kg: float
    waste_rate_pct: float


class RunSummary(BaseModel):
    id: str
    status: RunStatus
    solver_outcome: SolverOutcome | None
    label: str | None
    dataset_id: str
    version_no: int
    scenario_id: str | None
    objective: ObjectiveKind
    created_at: datetime
    finished_at: datetime | None
    headline: RunHeadlineKpis | None = None

    @classmethod
    def of(cls, run: OptimizationRun, session: Session, kpis: dict[str, Any] | None = None) -> RunSummary:
        version = session.get(DatasetVersion, run.dataset_version_id)
        return cls(
            id=run.id,
            status=RunStatus(run.status),
            solver_outcome=SolverOutcome(run.solver_outcome) if run.solver_outcome else None,
            label=run.label,
            dataset_id=run.dataset_id,
            version_no=version.version_no if version else 0,
            scenario_id=run.scenario_id,
            objective=ObjectiveKind(run.config.get("objective", "profit")),
            created_at=run.created_at,
            finished_at=run.finished_at,
            headline=RunHeadlineKpis.model_validate(kpis) if kpis else None,
        )


class RunDetail(RunSummary):
    dataset_version_id: str
    config: RunConfig
    config_hash: str
    effective_input_hash: str
    applied_changes: list[AppliedChange]
    mip_gap: float | None = Field(description="Relative gap the optimal plan is proven within (None if not proven)")
    started_at: datetime | None
    solve_seconds: float | None
    warnings: list[str]
    error: RunError | None
    diagnostics: Diagnostics | None = Field(description="Only for infeasible runs")
    cache_hit: bool = Field(default=False, description="True when POST /runs returned an existing identical run")

    @classmethod
    def of_run(
        cls, run: OptimizationRun, session: Session, *, kpis: dict[str, Any] | None = None, cache_hit: bool = False
    ) -> RunDetail:
        return cls(
            **RunSummary.of(run, session, kpis).model_dump(),
            dataset_version_id=run.dataset_version_id,
            config=RunConfig.model_validate(run.config),
            config_hash=run.config_hash,
            effective_input_hash=run.effective_input_hash,
            applied_changes=[AppliedChange.model_validate(a) for a in run.applied_changes or []],
            mip_gap=run.mip_gap,
            started_at=run.started_at,
            solve_seconds=run.solve_seconds,
            warnings=list(run.warnings or []),
            error=RunError(code=run.error_code, message=safe_error_message(run)) if run.error_code else None,
            diagnostics=Diagnostics.model_validate(run.diagnostics) if run.diagnostics else None,
            cache_hit=cache_hit,
        )

"""Scenario and comparison DTOs."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from ....db.models import DatasetVersion, Scenario, ScenarioChange
from ....domain.dataset import DatasetPayload, DomainModel
from ....domain.diff import FieldDiff
from ....domain.enums import ChangeSource, ScenarioStatus
from ....domain.run_config import RunConfig
from ....domain.scenario import AppliedChange, ScenarioChangeModel, Target
from ....domain.validation import ValidationReport
from ....services.scenarios import PreviewData, ScenarioDetailData
from .runs import RunSummary

class ScenarioCreate(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    description: str | None = Field(default=None, max_length=2000)
    dataset_id: str | None = Field(default=None, description="Required unless parent_id is given")
    version_no: int | None = Field(default=None, ge=1, description="Default: the parent's base version, else the current version")
    parent_id: str | None = None
    changes: list[ScenarioChangeModel] = Field(default_factory=list, max_length=100)
    tags: list[str] | None = Field(default=None, max_length=20)


class ScenarioPatch(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=120)
    description: str | None = Field(default=None, max_length=2000)
    tags: list[str] | None = Field(default=None, max_length=20)
    archived: bool | None = None


class ScenarioCopy(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=120)


class ScenarioBranch(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    description: str | None = Field(default=None, max_length=2000)


class ChangePatch(DomainModel):
    """Fields to replace in an existing change; the op cannot change (delete and add instead)."""

    target: Target | None = None
    params: dict[str, Any] | None = None
    enabled: bool | None = None
    note: str | None = Field(default=None, max_length=500)


class ChangeOrder(BaseModel):
    ids: list[str] = Field(description="Every change id of the scenario, in the new order")


class ScenarioRun(BaseModel):
    config: RunConfig = Field(default_factory=RunConfig)
    label: str | None = Field(default=None, max_length=120)
    use_cache: bool = True


class ApplyPreviewRequest(BaseModel):
    dataset_id: str
    version_no: int | None = Field(default=None, ge=1)
    changes: list[ScenarioChangeModel] = Field(max_length=100)


class ScenarioChangeOut(BaseModel):
    id: str
    position: int
    op: str
    target: str | None
    params: dict[str, Any]
    enabled: bool
    source: ChangeSource
    note: str | None

    @classmethod
    def of(cls, row: ScenarioChange) -> ScenarioChangeOut:
        return cls(
            id=row.id,
            position=row.position,
            op=row.op,
            target=row.target,
            params=row.params,
            enabled=row.enabled,
            source=ChangeSource(row.source),
            note=row.note,
        )


class ScenarioSummary(BaseModel):
    id: str
    name: str
    description: str | None
    dataset_id: str
    base_version_no: int
    parent_id: str | None
    status: ScenarioStatus
    tags: list[str]
    latest_run_id: str | None
    created_at: datetime
    updated_at: datetime

    @classmethod
    def of(cls, s: Scenario, session: Session) -> ScenarioSummary:
        version = session.get(DatasetVersion, s.base_version_id)
        return cls(
            id=s.id,
            name=s.name,
            description=s.description,
            dataset_id=s.dataset_id,
            base_version_no=version.version_no if version else 0,
            parent_id=s.parent_id,
            status=ScenarioStatus(s.status),
            tags=list(s.tags or []),
            latest_run_id=s.latest_run_id,
            created_at=s.created_at,
            updated_at=s.updated_at,
        )


class LineageItem(BaseModel):
    id: str
    name: str


class ScenarioDetail(BaseModel):
    scenario: ScenarioSummary
    changes: list[ScenarioChangeOut]
    lineage: list[LineageItem] = Field(description="Root first; the last item is this scenario")
    runs: list[RunSummary]
    stale: bool = Field(description="The dataset has a newer version than the scenario's base: POST /rebase")
    current_version_no: int | None

    @classmethod
    def of(cls, data: ScenarioDetailData, session: Session) -> ScenarioDetail:
        current = session.get(DatasetVersion, data.dataset.current_version_id) if data.dataset.current_version_id else None
        return cls(
            scenario=ScenarioSummary.of(data.scenario, session),
            changes=[ScenarioChangeOut.of(c) for c in data.changes],
            lineage=[LineageItem(id=s.id, name=s.name) for s in data.lineage],
            runs=[RunSummary.of(r, session) for r in data.runs],
            stale=data.stale,
            current_version_no=current.version_no if current else None,
        )


class ScenarioPreview(BaseModel):
    base_version_no: int
    effective_payload: DatasetPayload
    diff: list[FieldDiff]
    applied: list[AppliedChange]
    validation: ValidationReport

    @classmethod
    def of(cls, data: PreviewData) -> ScenarioPreview:
        return cls(
            base_version_no=data.base_version.version_no,
            effective_payload=data.effective,
            diff=data.diff,
            applied=data.applied,
            validation=data.validation,
        )


class ComparisonRequest(BaseModel):
    baseline_run_id: str
    run_ids: list[str] = Field(min_length=1, max_length=3)

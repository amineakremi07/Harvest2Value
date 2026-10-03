"""Report DTOs (phase 13)."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field

from ....db.models import Report
from ....domain.report import ReportSpec


class ReportSummary(BaseModel):
    id: str
    title: str
    run_id: str
    sections: list[str]
    compare_run_ids: list[str]
    include_narrative: bool
    snapshot_hash: str
    created_at: datetime

    @classmethod
    def of(cls, row: Report) -> ReportSummary:
        spec = ReportSpec.model_validate(row.spec)
        return cls(
            id=row.id,
            title=row.title,
            run_id=row.run_id,
            sections=list(spec.sections),
            compare_run_ids=spec.compare_run_ids,
            include_narrative=spec.include_narrative,
            snapshot_hash=row.snapshot_hash,
            created_at=row.created_at,
        )


class ReportDetail(ReportSummary):
    spec: ReportSpec
    snapshot: dict[str, Any] = Field(description="Frozen copy computed at creation; never recomputed")

    @classmethod
    def of(cls, row: Report) -> ReportDetail:
        summary = ReportSummary.of(row)
        return cls(**summary.model_dump(), spec=ReportSpec.model_validate(row.spec), snapshot=row.snapshot)

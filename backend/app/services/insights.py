"""Insights of a run: generation (after a run, and again once probes exist), listing, dismissal."""

from __future__ import annotations

import builtins
from datetime import datetime
from typing import Any

from pydantic import BaseModel
from sqlalchemy.orm import Session

from ..analytics.context import RunContext
from ..core.errors import NotFound, ValidationFailed
from ..core.hashing import canonical_json
from ..db.models import DEFAULT_WORKSPACE_ID, Insight, OptimizationRun
from ..domain.enums import InsightCategory, Severity
from ..domain.insight import Evidence
from ..insights.engine import InsightEngine, message_for
from ..repositories.insights import InsightRepository


class InsightView(BaseModel):
    id: str
    run_id: str
    rule_id: str
    rule_version: int
    category: InsightCategory
    severity: Severity
    entity_ref: dict[str, str] | None
    message_key: str
    message_params: dict[str, Any]
    message: str
    evidence: Evidence
    suggested_changes: list[dict[str, Any]]
    dismissed: bool
    created_at: datetime

    @classmethod
    def of(cls, row: Insight) -> InsightView:
        return cls(
            id=row.id,
            run_id=row.run_id,
            rule_id=row.rule_id,
            rule_version=row.rule_version,
            category=InsightCategory(row.category),
            severity=Severity(row.severity),
            entity_ref=row.entity_ref,
            message_key=row.message_key,
            message_params=row.message_params,
            message=message_for(row.rule_id, row.message_params),
            evidence=Evidence.model_validate(row.evidence),
            suggested_changes=list(row.suggested_changes or []),
            dismissed=row.dismissed,
            created_at=row.created_at,
        )


def _identity(rule_id: str, entity_ref: dict[str, str] | None) -> str:
    return f"{rule_id}:{canonical_json(entity_ref)}"


class InsightService:
    def __init__(self, session: Session, *, workspace_id: str = DEFAULT_WORKSPACE_ID, engine: InsightEngine | None = None) -> None:
        self.session = session
        self.repo = InsightRepository(session)
        self.workspace_id = workspace_id
        self.engine = engine or InsightEngine()

    def regenerate(self, ctx: RunContext) -> list[Insight]:
        """Replace the run's insights; an insight the user dismissed stays dismissed."""
        dismissed = {_identity(i.rule_id, i.entity_ref) for i in self.repo.for_run(ctx.run_id, include_dismissed=True) if i.dismissed}
        rows = [
            Insight(
                run_id=ctx.run_id,
                rule_id=c.rule_id,
                rule_version=c.rule_version,
                category=c.category,
                severity=c.severity,
                entity_ref=c.entity_ref,
                evidence=c.evidence.model_dump(mode="json"),
                message_key=c.message_key,
                message_params=c.message_params,
                suggested_changes=c.suggested_changes or None,
                dismissed=_identity(c.rule_id, c.entity_ref) in dismissed,
            )
            for c in self.engine.evaluate(ctx)
        ]
        self.repo.replace_for_run(ctx.run_id, rows)
        return rows

    def list(self, run_id: str, *, include_dismissed: bool = False) -> list[InsightView]:
        self._run(run_id)
        return [InsightView.of(row) for row in self.repo.for_run(run_id, include_dismissed=include_dismissed)]

    def get(self, insight_id: str) -> Insight:
        row = self.repo.get(insight_id)
        if row is None or self._run_or_none(row.run_id) is None:
            raise NotFound(f"Insight '{insight_id}' does not exist.", details={"insight_id": insight_id})
        return row

    def set_dismissed(self, insight_id: str, dismissed: bool) -> InsightView:
        row = self.get(insight_id)
        row.dismissed = dismissed
        self.session.flush()
        return InsightView.of(row)

    def suggested_changes(self, insight_id: str) -> tuple[Insight, builtins.list[dict[str, Any]]]:
        row = self.get(insight_id)
        if not row.suggested_changes:
            raise ValidationFailed("This insight has no suggested change to try.", code="NO_SUGGESTED_CHANGE")
        return row, list(row.suggested_changes)

    def _run_or_none(self, run_id: str) -> OptimizationRun | None:
        run = self.session.get(OptimizationRun, run_id)
        return run if run is not None and run.workspace_id == self.workspace_id else None

    def _run(self, run_id: str) -> OptimizationRun:
        run = self._run_or_none(run_id)
        if run is None:
            raise NotFound(f"Run '{run_id}' does not exist.", details={"run_id": run_id})
        return run

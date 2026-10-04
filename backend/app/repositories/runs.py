"""Optimization runs and their results."""

from __future__ import annotations

from collections.abc import Sequence

from sqlalchemy import func, select, update
from sqlalchemy.orm import Session

from ..db.base import utcnow
from ..db.models import OptimizationResult, OptimizationRun
from ..domain.enums import RunStatus


class RunRepository:
    def __init__(self, session: Session) -> None:
        self.session = session

    def add(self, run: OptimizationRun) -> None:
        self.session.add(run)
        self.session.flush()

    def get(self, run_id: str, workspace_id: str) -> OptimizationRun | None:
        run = self.session.get(OptimizationRun, run_id)
        if run is None or run.workspace_id != workspace_id:
            return None
        return run

    def list(
        self,
        workspace_id: str,
        *,
        dataset_id: str | None = None,
        scenario_id: str | None = None,
        status: str | None = None,
        offset: int = 0,
        limit: int = 20,
    ) -> tuple[list[OptimizationRun], int]:
        query = select(OptimizationRun).where(OptimizationRun.workspace_id == workspace_id)
        if dataset_id is not None:
            query = query.where(OptimizationRun.dataset_id == dataset_id)
        if scenario_id is not None:
            query = query.where(OptimizationRun.scenario_id == scenario_id)
        if status is not None:
            query = query.where(OptimizationRun.status == status)
        total = self.session.scalar(select(func.count()).select_from(query.subquery())) or 0
        runs = self.session.scalars(
            query.order_by(OptimizationRun.created_at.desc(), OptimizationRun.id).offset(offset).limit(limit)
        ).all()
        return list(runs), total

    def find_cached(self, workspace_id: str, effective_input_hash: str, config_hash: str) -> OptimizationRun | None:
        """Most recent succeeded run with the same effective input and configuration."""
        return self.session.scalars(
            select(OptimizationRun)
            .where(
                OptimizationRun.workspace_id == workspace_id,
                OptimizationRun.effective_input_hash == effective_input_hash,
                OptimizationRun.config_hash == config_hash,
                OptimizationRun.status == RunStatus.SUCCEEDED,
            )
            .order_by(OptimizationRun.created_at.desc())
            .limit(1)
        ).first()

    def latest_succeeded(
        self, workspace_id: str, *, dataset_id: str | None = None, baseline_only: bool = False
    ) -> OptimizationRun | None:
        query = select(OptimizationRun).where(
            OptimizationRun.workspace_id == workspace_id, OptimizationRun.status == RunStatus.SUCCEEDED
        )
        if dataset_id is not None:
            query = query.where(OptimizationRun.dataset_id == dataset_id)
        if baseline_only:
            query = query.where(OptimizationRun.scenario_id.is_(None))
        return self.session.scalars(query.order_by(OptimizationRun.created_at.desc()).limit(1)).first()

    def delete(self, run: OptimizationRun) -> None:
        self.session.delete(run)
        self.session.flush()

    def mark_unfinished_interrupted(self) -> int:
        """Startup recovery: queued/running runs lost their worker when the process stopped."""
        result = self.session.execute(
            update(OptimizationRun)
            .where(OptimizationRun.status.in_([RunStatus.QUEUED, RunStatus.RUNNING]))
            .values(
                status=RunStatus.INTERRUPTED,
                error_code="INTERRUPTED",
                error_message="The server stopped before this run finished.",
                finished_at=utcnow(),
                updated_at=utcnow(),
            )
        )
        return int(getattr(result, "rowcount", 0) or 0)  # CursorResult of an UPDATE

    # ---- results ----

    def add_result(self, result: OptimizationResult) -> None:
        self.session.add(result)
        self.session.flush()

    def get_result(self, run_id: str) -> OptimizationResult | None:
        return self.session.scalar(select(OptimizationResult).where(OptimizationResult.run_id == run_id))

    def results_for(self, run_ids: Sequence[str]) -> dict[str, OptimizationResult]:
        if not run_ids:
            return {}
        rows = self.session.scalars(select(OptimizationResult).where(OptimizationResult.run_id.in_(list(run_ids)))).all()
        return {r.run_id: r for r in rows}

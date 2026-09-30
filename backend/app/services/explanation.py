"""Explanations of a succeeded run: decision cards, binding constraints, bottlenecks, marginal values."""

from __future__ import annotations

from sqlalchemy.orm import Session

from ..core.errors import Conflict
from ..db.models import DEFAULT_WORKSPACE_ID
from ..domain.explanation import Bottleneck, RunExplanation
from ..domain.results import ConstraintInfo, SensitivityReport
from ..explain.binding import bottlenecks, really_binding
from ..explain.builder import ExplanationBuilder
from .optimization import OptimizationService


class ExplanationService:
    def __init__(self, session: Session, *, workspace_id: str = DEFAULT_WORKSPACE_ID) -> None:
        self.runs = OptimizationService(session, workspace_id=workspace_id)
        self.session = session

    def explanation(self, run_id: str) -> RunExplanation:
        _run, row = self.runs.require_result(run_id)
        if row.explanation is not None:
            return RunExplanation.model_validate(row.explanation)
        explanation = ExplanationBuilder().build(self.runs.context(run_id))
        row.explanation = explanation.model_dump(mode="json")
        self.session.flush()
        return explanation

    def constraints(self, run_id: str, *, binding_only: bool = False) -> list[ConstraintInfo]:
        if not binding_only:
            return self.runs.result(run_id).constraints
        ctx = self.runs.context(run_id)
        return [c for c in ctx.result.constraints if really_binding(c, ctx)]

    def bottlenecks(self, run_id: str) -> list[Bottleneck]:
        return bottlenecks(self.runs.context(run_id))

    def marginal_values(self, run_id: str, *, computing: bool) -> SensitivityReport:
        _run, row = self.runs.require_result(run_id)
        report = SensitivityReport.model_validate(row.sensitivity) if row.sensitivity else SensitivityReport()
        if not report.probes_computed:
            raise Conflict(
                "Marginal values are not computed yet: POST /runs/{id}/marginal-values to start them.",
                code="NOT_COMPUTED",
                details={"status": "computing" if computing else "not_requested", "duals_available": report.duals_available},
            )
        return report

    def sensitivity_state(self, run_id: str) -> bool:
        """True when probes are already computed (validates the run has a result)."""
        _run, row = self.runs.require_result(run_id)
        return bool(row.sensitivity and row.sensitivity.get("probes_computed"))

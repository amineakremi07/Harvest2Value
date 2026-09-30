"""Compare a baseline run with 1 to 3 other runs (all succeeded, same crop)."""

from __future__ import annotations

from sqlalchemy.orm import Session

from ..analytics.comparison import ComparedRun, compare
from ..core.errors import ValidationFailed
from ..db.models import DEFAULT_WORKSPACE_ID
from ..domain.comparison import ComparisonResult
from ..domain.dataset import DatasetPayload
from .optimization import OptimizationService, result_model

MAX_COMPARED = 3


class ComparisonService:
    def __init__(self, session: Session, *, workspace_id: str = DEFAULT_WORKSPACE_ID) -> None:
        self.runs = OptimizationService(session, workspace_id=workspace_id)

    def _load(self, run_id: str) -> ComparedRun:
        run, row = self.runs.require_result(run_id)
        return ComparedRun(
            run_id=run.id,
            label=run.label,
            scenario_id=run.scenario_id,
            result=result_model(run, row),
            payload=DatasetPayload.model_validate(run.effective_input),
        )

    def compare(self, baseline_run_id: str, run_ids: list[str]) -> ComparisonResult:
        if not 1 <= len(run_ids) <= MAX_COMPARED:
            raise ValidationFailed(f"Compare the baseline with 1 to {MAX_COMPARED} runs.")
        if len(set(run_ids)) != len(run_ids) or baseline_run_id in run_ids:
            raise ValidationFailed("run_ids must be distinct and must not include the baseline.")
        baseline = self._load(baseline_run_id)
        others = [self._load(run_id) for run_id in run_ids]
        crops = {r.run_id: r.result.crop_id for r in [baseline, *others]}
        if len(set(crops.values())) > 1:
            raise ValidationFailed("Runs optimize different crops and cannot be compared.", code="INCOMPARABLE", details={"crops": crops})
        return compare(baseline, others)

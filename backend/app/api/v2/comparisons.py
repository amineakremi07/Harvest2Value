"""Comparison endpoint (plan §8): baseline run vs 1 to 3 runs, computed on demand."""

from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from ...db.session import get_session
from ...domain.comparison import ComparisonResult
from ...services.comparisons import ComparisonService
from .schemas.scenarios import ComparisonRequest

router = APIRouter(tags=["comparisons"])


@router.post(
    "/comparisons",
    response_model=ComparisonResult,
    responses={
        404: {"description": "Run not found"},
        409: {"description": "RUN_NOT_FINISHED, RUN_INFEASIBLE or RUN_NO_RESULT"},
        422: {"description": "INCOMPARABLE (different crops) or invalid run list"},
    },
)
def compare_runs(body: ComparisonRequest, session: Session = Depends(get_session, scope="function")) -> ComparisonResult:
    return ComparisonService(session).compare(body.baseline_run_id, body.run_ids)

"""Explainability endpoints (plan §8): decision cards, constraints, bottlenecks, marginal values."""

from __future__ import annotations

from functools import partial
from typing import Annotated

from fastapi import APIRouter, Depends, Query, Request, Response, status
from sqlalchemy.orm import Session

from ...db.session import get_session
from ...domain.explanation import Bottleneck, RunExplanation
from ...domain.results import ConstraintInfo, SensitivityReport
from ...services.explanation import ExplanationService
from ...services.optimization import compute_sensitivity
from ..deps import get_engine, get_executor, in_transaction
from .schemas.explain import MarginalValuesStatus

router = APIRouter(tags=["explainability"])

NOT_READY = {404: {"description": "Run not found"}, 409: {"description": "RUN_NOT_FINISHED, RUN_INFEASIBLE or RUN_NO_RESULT"}}


def get_service(session: Session = Depends(get_session, scope="function")) -> ExplanationService:
    return ExplanationService(session)


Service = Annotated[ExplanationService, Depends(get_service)]


def _sensitivity_key(run_id: str) -> str:
    return f"sensitivity:{run_id}"


@router.get("/runs/{run_id}/explanation", response_model=RunExplanation, responses=NOT_READY)
def get_explanation(run_id: str, service: Service) -> RunExplanation:
    """Decision cards (buyers, storage, losses) with limiting factor, marginal values and best
    alternative; binding constraints; ranked bottlenecks; trade-offs. Deterministic."""
    return service.explanation(run_id)


@router.get("/runs/{run_id}/constraints", response_model=list[ConstraintInfo], responses=NOT_READY)
def get_constraints(run_id: str, service: Service, binding_only: bool = False) -> list[ConstraintInfo]:
    return service.constraints(run_id, binding_only=binding_only)


@router.get("/runs/{run_id}/bottlenecks", response_model=list[Bottleneck], responses=NOT_READY)
def get_bottlenecks(run_id: str, service: Service) -> list[Bottleneck]:
    return service.bottlenecks(run_id)


@router.post(
    "/runs/{run_id}/marginal-values",
    response_model=MarginalValuesStatus,
    status_code=status.HTTP_202_ACCEPTED,
    responses={200: {"model": MarginalValuesStatus, "description": "Already computed, or finished within `wait`"}, **NOT_READY},
)
async def start_marginal_values(
    run_id: str,
    request: Request,
    response: Response,
    wait: Annotated[float, Query(ge=0, le=15)] = 0,
) -> MarginalValuesStatus:
    """Start the perturbation probes (up to 8 re-optimizations of the top bottlenecks) in the
    background. Read them with GET."""
    done = await in_transaction(request, lambda s: ExplanationService(s).sensitivity_state(run_id))
    executor = get_executor(request)
    key = _sensitivity_key(run_id)
    if not done:
        executor.submit(key, partial(compute_sensitivity, request.app.state.session_factory, get_engine(request), run_id))
        done = await executor.wait(key, wait) and await in_transaction(request, lambda s: ExplanationService(s).sensitivity_state(run_id))
    response.status_code = status.HTTP_200_OK if done else status.HTTP_202_ACCEPTED
    return MarginalValuesStatus(run_id=run_id, status="computed" if done else "computing")


@router.get(
    "/runs/{run_id}/marginal-values",
    response_model=SensitivityReport,
    responses={404: {"description": "Run not found"}, 409: {"description": "NOT_COMPUTED (details.status: computing | not_requested)"}},
)
def get_marginal_values(run_id: str, request: Request, service: Service) -> SensitivityReport:
    return service.marginal_values(run_id, computing=get_executor(request).is_pending(_sensitivity_key(run_id)))

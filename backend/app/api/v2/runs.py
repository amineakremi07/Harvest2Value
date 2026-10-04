"""Optimization runs (plan §8 — optimisation): queue, status, result, diagnostics, cancel, rerun."""

from __future__ import annotations

from functools import partial
from typing import Annotated

from fastapi import APIRouter, Depends, Query, Request, Response, status
from sqlalchemy.orm import Session

from ...db.session import get_session
from ...domain.enums import RunStatus
from ...domain.results import Diagnostics, OptimizationResultModel
from ...services.optimization import TERMINAL, CreatedRun, OptimizationService, execute_run
from ..deps import get_engine, get_executor, in_transaction, rate_limit
from .schemas.common import Page, Responses
from .schemas.runs import RunCreate, RunDetail, RunRerun, RunSummary

router = APIRouter(tags=["runs"])

PageNo = Annotated[int, Query(ge=1)]
PageSize = Annotated[int, Query(ge=1, le=100)]
Wait = Annotated[float, Query(ge=0, le=15, description="Seconds to wait for the run to finish before answering 202")]

RUN_ERRORS: Responses = {
    404: {"description": "Dataset, version, scenario or run not found"},
    422: {"description": "DATASET_INVALID, CONFIG_INVALID or SCENARIO_APPLY_ERROR (details.change_index)"},
    429: {"description": "RATE_LIMITED"},
    503: {"description": "SOLVER_BUSY: the queue is full"},
}


def get_service(session: Session = Depends(get_session, scope="function")) -> OptimizationService:
    return OptimizationService(session)


Service = Annotated[OptimizationService, Depends(get_service)]


def detail_of(session: Session, run_id: str, *, cache_hit: bool = False) -> RunDetail:
    service = OptimizationService(session)
    run = service.get(run_id)
    row = service.runs.get_result(run.id)
    return RunDetail.of_run(run, session, kpis=row.kpis if row else None, cache_hit=cache_hit)


async def submit_and_wait(request: Request, response: Response, created: CreatedRun, wait: float) -> RunDetail:
    """Queue the run (unless it came from the cache), wait up to `wait` s, answer 200 if finished else 202."""
    if not created.cache_hit:
        executor = get_executor(request)
        executor.submit(created.run.id, partial(execute_run, request.app.state.session_factory, get_engine(request), created.run.id))
        await executor.wait(created.run.id, wait)
    detail = await in_transaction(request, lambda s: detail_of(s, created.run.id, cache_hit=created.cache_hit))
    response.status_code = status.HTTP_200_OK if detail.status in TERMINAL else status.HTTP_202_ACCEPTED
    return detail


@router.post(
    "/runs",
    response_model=RunDetail,
    status_code=status.HTTP_202_ACCEPTED,
    responses={200: {"model": RunDetail, "description": "Finished within `wait`, or identical run reused (cache_hit)"}, **RUN_ERRORS},
    dependencies=[Depends(rate_limit("runs"))],
)
async def create_run(body: RunCreate, request: Request, response: Response, wait: Wait = 0) -> RunDetail:
    """Queue an optimization. An infeasible model is not an HTTP error: the run ends with status
    `infeasible` and its diagnostics."""
    get_executor(request).ensure_capacity()
    created = await in_transaction(
        request,
        lambda s: OptimizationService(s).create_run(
            dataset_id=body.dataset_id,
            version_no=body.version_no,
            scenario_id=body.scenario_id,
            config=body.config,
            label=body.label,
            use_cache=body.use_cache,
        ),
    )
    return await submit_and_wait(request, response, created, wait)


@router.get("/runs", response_model=Page[RunSummary])
def list_runs(
    service: Service,
    dataset_id: str | None = None,
    scenario_id: str | None = None,
    run_status: Annotated[RunStatus | None, Query(alias="status")] = None,
    page: PageNo = 1,
    page_size: PageSize = 20,
) -> Page[RunSummary]:
    runs, total = service.list(dataset_id=dataset_id, scenario_id=scenario_id, status=run_status, page=page, page_size=page_size)
    results = service.runs.results_for([r.id for r in runs])
    items = [RunSummary.of(r, service.session, results[r.id].kpis if r.id in results else None) for r in runs]
    return Page(items=items, total=total, page=page, page_size=page_size)


@router.get("/runs/{run_id}", response_model=RunDetail, responses={404: {"description": "Run not found"}})
def get_run(run_id: str, service: Service) -> RunDetail:
    return detail_of(service.session, run_id)


@router.get(
    "/runs/{run_id}/result",
    response_model=OptimizationResultModel,
    responses={404: {"description": "Run not found"}, 409: {"description": "RUN_NOT_FINISHED, RUN_INFEASIBLE or RUN_NO_RESULT"}},
)
def get_result(run_id: str, service: Service) -> OptimizationResultModel:
    return service.result(run_id)


@router.get(
    "/runs/{run_id}/diagnostics",
    response_model=Diagnostics,
    responses={404: {"description": "Run not found"}, 409: {"description": "RUN_NOT_INFEASIBLE"}},
)
def get_diagnostics(run_id: str, service: Service) -> Diagnostics:
    return service.diagnostics(run_id)


@router.post(
    "/runs/{run_id}/cancel",
    response_model=RunSummary,
    responses={404: {"description": "Run not found"}, 409: {"description": "NOT_CANCELLABLE (only queued runs)"}},
)
def cancel_run(run_id: str, service: Service) -> RunSummary:
    return RunSummary.of(service.cancel(run_id), service.session)


@router.post(
    "/runs/{run_id}/rerun",
    response_model=RunDetail,
    status_code=status.HTTP_202_ACCEPTED,
    responses={200: {"model": RunDetail, "description": "Finished within `wait` or reused from the cache"}, **RUN_ERRORS},
    dependencies=[Depends(rate_limit("runs"))],
)
async def rerun(run_id: str, request: Request, response: Response, body: RunRerun | None = None, wait: Wait = 0) -> RunDetail:
    """New run on the same frozen effective input, with configuration overrides."""
    body = body or RunRerun()
    get_executor(request).ensure_capacity()
    created = await in_transaction(
        request,
        lambda s: OptimizationService(s).rerun(run_id, config_overrides=body.config_overrides, label=body.label, use_cache=body.use_cache),
    )
    return await submit_and_wait(request, response, created, wait)


@router.delete(
    "/runs/{run_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    responses={404: {"description": "Run not found"}, 409: {"description": "RUN_RUNNING"}},
)
def delete_run(run_id: str, service: Service) -> Response:
    service.delete(run_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)

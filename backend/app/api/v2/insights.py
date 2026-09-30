"""Insight endpoints (plan §8): list per run, dismiss / restore, try the suggested change."""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, Request, Response, status
from sqlalchemy.orm import Session

from ...db.session import get_session
from ...domain.enums import ChangeSource
from ...domain.run_config import RunConfig
from ...domain.scenario import parse_change
from ...services.insights import InsightService, InsightView
from ...services.optimization import CreatedRun, OptimizationService
from ...services.scenarios import ScenarioService
from ..deps import get_executor, in_transaction, rate_limit
from .runs import submit_and_wait
from .schemas.explain import TryInsightResult
from .schemas.runs import RunSummary

router = APIRouter(tags=["insights"])


def get_service(session: Session = Depends(get_session, scope="function")) -> InsightService:
    return InsightService(session)


Service = Annotated[InsightService, Depends(get_service)]


@router.get("/runs/{run_id}/insights", response_model=list[InsightView], responses={404: {"description": "Run not found"}})
def list_insights(run_id: str, service: Service, include_dismissed: bool = False) -> list[InsightView]:
    """Deterministic alerts, most severe first. `message` is rendered from `message_params`, which
    are the evidence values."""
    return service.list(run_id, include_dismissed=include_dismissed)


@router.post("/insights/{insight_id}/dismiss", response_model=InsightView, responses={404: {"description": "Insight not found"}})
def dismiss(insight_id: str, service: Service) -> InsightView:
    return service.set_dismissed(insight_id, True)


@router.post("/insights/{insight_id}/restore", response_model=InsightView, responses={404: {"description": "Insight not found"}})
def restore(insight_id: str, service: Service) -> InsightView:
    return service.set_dismissed(insight_id, False)


def _create_trial(session: Session, insight_id: str) -> tuple[str, CreatedRun]:
    insight, changes = InsightService(session).suggested_changes(insight_id)
    runs = OptimizationService(session)
    source = runs.get(insight.run_id)
    scenarios = ScenarioService(session)
    proposed = [parse_change({**c, "source": ChangeSource.RECOMMENDATION}) for c in changes]
    name = f"Try {insight.rule_id.lower()}"[:120]
    if source.scenario_id is not None:
        scenario = scenarios.create(name=name, dataset_id=None, parent_id=source.scenario_id, changes=proposed)
    else:
        version_no = runs.datasets.get_version_by_id(source.dataset_version_id).version_no  # type: ignore[union-attr]
        scenario = scenarios.create(name=name, dataset_id=source.dataset_id, version_no=version_no, changes=proposed)
    created = runs.create_run(dataset_id=None, scenario_id=scenario.id, config=RunConfig.model_validate(source.config))
    return scenario.id, created


@router.post(
    "/insights/{insight_id}/try",
    response_model=TryInsightResult,
    status_code=status.HTTP_202_ACCEPTED,
    responses={404: {"description": "Insight not found"}, 422: {"description": "NO_SUGGESTED_CHANGE or SCENARIO_APPLY_ERROR"}},
    dependencies=[Depends(rate_limit("runs"))],
)
async def try_insight(insight_id: str, request: Request, response: Response) -> TryInsightResult:
    """Create a scenario from the insight's suggested changes (branching from the run's scenario,
    if any) and run it with the same configuration."""
    get_executor(request).ensure_capacity()
    scenario_id, created = await in_transaction(request, lambda s: _create_trial(s, insight_id))
    detail = await submit_and_wait(request, response, created, 0)
    response.status_code = status.HTTP_202_ACCEPTED
    return TryInsightResult(scenario_id=scenario_id, run_id=detail.id, run=RunSummary.model_validate(detail.model_dump()))

"""Scenario endpoints (plan §8 — scénarios): CRUD, duplicate, branch, changes, preview, rebase, run."""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, Query, Request, Response, status
from sqlalchemy.orm import Session

from ...db.session import get_session
from ...domain.enums import ScenarioStatus
from ...domain.scenario import ScenarioChangeModel
from ...services.optimization import OptimizationService
from ...services.scenarios import ScenarioService
from ..deps import get_executor, in_transaction, rate_limit
from .runs import RUN_ERRORS, submit_and_wait
from .schemas.common import Page
from .schemas.runs import RunDetail
from .schemas.scenarios import (
    ApplyPreviewRequest,
    ChangeOrder,
    ChangePatch,
    ScenarioBranch,
    ScenarioCopy,
    ScenarioCreate,
    ScenarioDetail,
    ScenarioPatch,
    ScenarioPreview,
    ScenarioRun,
    ScenarioSummary,
)

router = APIRouter(tags=["scenarios"])

PageNo = Annotated[int, Query(ge=1)]
PageSize = Annotated[int, Query(ge=1, le=100)]
APPLY_ERRORS = {404: {"description": "Scenario, dataset or change not found"}, 422: {"description": "SCENARIO_APPLY_ERROR (details.change_index, reason)"}}


def get_service(session: Session = Depends(get_session, scope="function")) -> ScenarioService:
    return ScenarioService(session)


Service = Annotated[ScenarioService, Depends(get_service)]


def _detail(service: ScenarioService, scenario_id: str) -> ScenarioDetail:
    return ScenarioDetail.of(service.detail(scenario_id), service.session)


@router.post("/scenarios", response_model=ScenarioDetail, status_code=status.HTTP_201_CREATED, responses=APPLY_ERRORS)
def create_scenario(body: ScenarioCreate, service: Service) -> ScenarioDetail:
    scenario = service.create(
        name=body.name,
        description=body.description,
        dataset_id=body.dataset_id,
        version_no=body.version_no,
        parent_id=body.parent_id,
        changes=body.changes,
        tags=body.tags,
    )
    return _detail(service, scenario.id)


@router.get("/scenarios", response_model=Page[ScenarioSummary])
def list_scenarios(
    service: Service,
    dataset_id: str | None = None,
    scenario_status: Annotated[ScenarioStatus | None, Query(alias="status")] = None,
    page: PageNo = 1,
    page_size: PageSize = 20,
) -> Page[ScenarioSummary]:
    rows, total = service.list(dataset_id=dataset_id, status=scenario_status, page=page, page_size=page_size)
    return Page(items=[ScenarioSummary.of(r, service.session) for r in rows], total=total, page=page, page_size=page_size)


@router.post("/scenarios/apply-preview", response_model=ScenarioPreview, responses=APPLY_ERRORS)
def apply_preview(body: ApplyPreviewRequest, service: Service) -> ScenarioPreview:
    """Effective data of unsaved changes applied to a dataset version (nothing is stored)."""
    return ScenarioPreview.of(service.apply_preview(body.dataset_id, body.version_no, body.changes))


@router.get("/scenarios/{scenario_id}", response_model=ScenarioDetail, responses={404: {"description": "Scenario not found"}})
def get_scenario(scenario_id: str, service: Service) -> ScenarioDetail:
    return _detail(service, scenario_id)


@router.patch("/scenarios/{scenario_id}", response_model=ScenarioSummary, responses={404: {"description": "Scenario not found"}})
def patch_scenario(scenario_id: str, body: ScenarioPatch, service: Service) -> ScenarioSummary:
    scenario = service.update(scenario_id, name=body.name, description=body.description, tags=body.tags, archived=body.archived)
    return ScenarioSummary.of(scenario, service.session)


@router.delete(
    "/scenarios/{scenario_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    responses={404: {"description": "Scenario not found"}, 409: {"description": "HAS_CHILDREN (use cascade=true)"}},
)
def delete_scenario(scenario_id: str, service: Service, cascade: bool = False) -> Response:
    service.delete(scenario_id, cascade=cascade)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.post("/scenarios/{scenario_id}/duplicate", response_model=ScenarioDetail, status_code=status.HTTP_201_CREATED, responses={404: {"description": "Scenario not found"}})
def duplicate_scenario(scenario_id: str, service: Service, body: ScenarioCopy | None = None) -> ScenarioDetail:
    copy = service.duplicate(scenario_id, name=body.name if body else None)
    return _detail(service, copy.id)


@router.post("/scenarios/{scenario_id}/branch", response_model=ScenarioDetail, status_code=status.HTTP_201_CREATED, responses={404: {"description": "Scenario not found"}})
def branch_scenario(scenario_id: str, body: ScenarioBranch, service: Service) -> ScenarioDetail:
    """Child scenario: it applies this scenario's changes first, then its own."""
    child = service.branch(scenario_id, name=body.name, description=body.description)
    return _detail(service, child.id)


@router.post("/scenarios/{scenario_id}/changes", response_model=ScenarioDetail, status_code=status.HTTP_201_CREATED, responses=APPLY_ERRORS)
def add_change(scenario_id: str, change: ScenarioChangeModel, service: Service) -> ScenarioDetail:
    service.add_change(scenario_id, change)
    return _detail(service, scenario_id)


@router.put("/scenarios/{scenario_id}/changes/order", response_model=ScenarioDetail, responses={**APPLY_ERRORS, 422: {"description": "INVALID_ORDER or SCENARIO_APPLY_ERROR"}})
def reorder_changes(scenario_id: str, body: ChangeOrder, service: Service) -> ScenarioDetail:
    service.reorder(scenario_id, body.ids)
    return _detail(service, scenario_id)


@router.patch("/scenarios/{scenario_id}/changes/{change_id}", response_model=ScenarioDetail, responses=APPLY_ERRORS)
def patch_change(scenario_id: str, change_id: str, body: ChangePatch, service: Service) -> ScenarioDetail:
    service.update_change(scenario_id, change_id, body.model_dump(exclude_unset=True))
    return _detail(service, scenario_id)


@router.delete("/scenarios/{scenario_id}/changes/{change_id}", response_model=ScenarioDetail, responses=APPLY_ERRORS)
def delete_change(scenario_id: str, change_id: str, service: Service) -> ScenarioDetail:
    service.delete_change(scenario_id, change_id)
    return _detail(service, scenario_id)


@router.post("/scenarios/{scenario_id}/preview", response_model=ScenarioPreview, responses=APPLY_ERRORS)
def preview(scenario_id: str, service: Service) -> ScenarioPreview:
    """Effective data (base version + lineage changes), field diff, applied changes, validation."""
    return ScenarioPreview.of(service.preview(scenario_id))


@router.post("/scenarios/{scenario_id}/rebase", response_model=ScenarioDetail, responses=APPLY_ERRORS)
def rebase(scenario_id: str, service: Service) -> ScenarioDetail:
    """Move the scenario to the dataset's current version, re-applying the same changes."""
    service.rebase(scenario_id)
    return _detail(service, scenario_id)


@router.post(
    "/scenarios/{scenario_id}/run",
    response_model=RunDetail,
    status_code=status.HTTP_202_ACCEPTED,
    responses={200: {"model": RunDetail, "description": "Finished within `wait` or reused from the cache"}, **RUN_ERRORS},
    dependencies=[Depends(rate_limit("runs"))],
)
async def run_scenario(
    scenario_id: str,
    request: Request,
    response: Response,
    body: ScenarioRun | None = None,
    wait: Annotated[float, Query(ge=0, le=15)] = 0,
) -> RunDetail:
    body = body or ScenarioRun()
    get_executor(request).ensure_capacity()
    created = await in_transaction(
        request,
        lambda s: OptimizationService(s).create_run(
            dataset_id=None, scenario_id=scenario_id, config=body.config, label=body.label, use_cache=body.use_cache
        ),
    )
    return await submit_and_wait(request, response, created, wait)

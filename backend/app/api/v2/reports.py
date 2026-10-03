"""Frozen reports (plan §8 — rapports): create a snapshot, list, read, delete, export CSV / JSON."""

from __future__ import annotations

import json
import logging
from typing import Annotated, Any

from fastapi import APIRouter, Depends, Query, Request, Response, status
from sqlalchemy.orm import Session

from ...ai.narratives import run_narrative
from ...core.errors import AppError
from ...db.models import DEFAULT_WORKSPACE_ID
from ...db.session import get_session
from ...domain.report import ReportSpec
from ...services.reports import TABLES, ReportService
from ..deps import get_app_settings, in_transaction
from .schemas.common import Page
from .schemas.reports import ReportDetail, ReportSummary

logger = logging.getLogger(__name__)
router = APIRouter(tags=["reports"])

PageNo = Annotated[int, Query(ge=1)]
PageSize = Annotated[int, Query(ge=1, le=100)]


def get_service(session: Session = Depends(get_session, scope="function")) -> ReportService:
    return ReportService(session)


Service = Annotated[ReportService, Depends(get_service)]


async def report_narrative(request: Request, spec: ReportSpec) -> dict[str, Any] | None:
    """The narrative frozen into a report. The report never depends on the LLM: if it is disabled
    or fails, the report is created with an explicit 'unavailable' narrative."""
    if not spec.include_narrative:
        return None
    if not get_app_settings(request).llm_configured:
        return {"status": "unavailable", "reason": "IA désactivée (aucune clé configurée)."}
    try:
        out = await run_narrative(request.app.state.llm_provider, request.app.state.session_factory, DEFAULT_WORKSPACE_ID, spec.run_id)
    except AppError as exc:
        logger.warning("Report narrative unavailable", extra={"code": exc.code})
        return {"status": "unavailable", "reason": exc.message}
    return {"status": "ok", "text": out.text, "verification": out.verification, "model": out.model, "prompt": out.prompt}


@router.post(
    "/reports",
    response_model=ReportDetail,
    status_code=status.HTTP_201_CREATED,
    responses={404: {"description": "Run not found"}, 409: {"description": "The main run has no plan"}, 422: {"description": "Invalid spec"}},
)
async def create_report(body: ReportSpec, request: Request) -> ReportDetail:
    """Computes every chosen section once and freezes it: later edits of data, scenarios or runs
    never change the report."""
    narrative = await report_narrative(request, body)
    return await in_transaction(request, lambda s: ReportDetail.of(ReportService(s).create(body, narrative)))


@router.get("/reports", response_model=Page[ReportSummary])
def list_reports(service: Service, run_id: str | None = None, page: PageNo = 1, page_size: PageSize = 20) -> Page[ReportSummary]:
    rows, total = service.list(run_id=run_id, page=page, page_size=page_size)
    return Page(items=[ReportSummary.of(r) for r in rows], total=total, page=page, page_size=page_size)


@router.get("/reports/sections", response_model=dict[str, list[str]])
def report_sections() -> dict[str, list[str]]:
    """Section -> exportable tables."""
    return {section: list(tables) for section, tables in TABLES.items()}


@router.get("/reports/{report_id}", response_model=ReportDetail, responses={404: {"description": "Report not found"}})
def get_report(report_id: str, service: Service) -> ReportDetail:
    return ReportDetail.of(service.get(report_id))


@router.delete("/reports/{report_id}", status_code=status.HTTP_204_NO_CONTENT, responses={404: {"description": "Report not found"}})
def delete_report(report_id: str, service: Service) -> Response:
    service.delete(report_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.get("/reports/{report_id}/export.json", responses={200: {"content": {"application/json": {}}}, 404: {"description": "Report not found"}})
def export_json(report_id: str, service: Service) -> Response:
    report = service.get(report_id)
    body = ReportDetail.of(report).model_dump(mode="json")
    filename = f"rapport-{report.id[:8]}.json"
    return Response(
        json.dumps(body, ensure_ascii=False, indent=2),
        media_type="application/json",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@router.get(
    "/reports/{report_id}/export.csv",
    responses={200: {"content": {"text/csv": {}}}, 404: {"description": "Report, section or table not found"}},
)
def export_csv(report_id: str, service: Service, section: str, table: str | None = None) -> Response:
    filename, content = service.csv(report_id, section, table)
    return Response(content, media_type="text/csv; charset=utf-8", headers={"Content-Disposition": f'attachment; filename="{filename}"'})

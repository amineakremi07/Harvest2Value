"""Dataset registry endpoints (plan §8 — datasets)."""

from __future__ import annotations

from typing import Annotated, Literal

from fastapi import APIRouter, Depends, File, Form, Header, Query, Response, UploadFile, status
from sqlalchemy.orm import Session

from ...core.errors import AppError
from ...db.session import get_session
from ...domain.validation import ValidationReport
from ...services.datasets import DatasetBundle, DatasetService, TemplateInfo
from .schemas.common import Page
from .schemas.datasets import (
    DatasetCreate,
    DatasetDetail,
    DatasetDiff,
    DatasetPatch,
    DatasetSummary,
    DatasetVersionOut,
    DatasetVersionSummary,
    DuplicateRequest,
    ImportResult,
    PayloadUpdate,
    ValidateRequest,
)

router = APIRouter(tags=["datasets"])

PageNo = Annotated[int, Query(ge=1)]
PageSize = Annotated[int, Query(ge=1, le=100)]


def get_service(session: Session = Depends(get_session, scope="function")) -> DatasetService:
    # scope="function": the transaction commits before the response is sent.
    return DatasetService(session)


Service = Annotated[DatasetService, Depends(get_service)]


def _detail(bundle: DatasetBundle) -> DatasetDetail:
    return DatasetDetail(
        dataset=DatasetSummary.of(bundle.dataset, bundle.version),
        current_version=DatasetVersionOut.of(bundle.version),
    )


def _etag(response: Response, version_no: int) -> None:
    response.headers["ETag"] = f'"{version_no}"'


def _parse_if_match(value: str | None) -> int:
    if value is None:
        raise AppError(
            "Send If-Match with the version number you edited (see the ETag header).",
            code="PRECONDITION_REQUIRED",
            status=428,
        )
    cleaned = value.strip().removeprefix("W/").strip('"')
    if not cleaned.isdigit():
        raise AppError("If-Match must be a version number, e.g. \"3\".", code="INVALID_IF_MATCH", status=400)
    return int(cleaned)


@router.get("/templates", response_model=list[TemplateInfo])
def list_templates(service: Service) -> list[TemplateInfo]:
    return service.list_templates()


@router.post("/datasets", response_model=DatasetDetail, status_code=status.HTTP_201_CREATED)
def create_dataset(body: DatasetCreate, service: Service, response: Response) -> DatasetDetail:
    if body.template_key is not None:
        bundle = service.create_from_template(body.template_key, name=body.name, description=body.description)
    else:
        assert body.payload is not None and body.name is not None
        bundle = service.create(name=body.name, payload=body.payload, description=body.description)
    _etag(response, bundle.version.version_no)
    return _detail(bundle)


@router.get("/datasets", response_model=Page[DatasetSummary])
def list_datasets(
    service: Service,
    q: Annotated[str | None, Query(max_length=100)] = None,
    archived: bool | None = False,
    page: PageNo = 1,
    page_size: PageSize = 20,
) -> Page[DatasetSummary]:
    rows, total = service.list(q=q, archived=archived, page=page, page_size=page_size)
    return Page(items=[DatasetSummary.of(d, v) for d, v in rows], total=total, page=page, page_size=page_size)


@router.post("/datasets/import", response_model=ImportResult, status_code=status.HTTP_201_CREATED)
async def import_dataset(
    service: Service,
    file: Annotated[UploadFile, File(description="JSON dataset, schema v2 or v1")],
    name: Annotated[str | None, Form(min_length=1, max_length=120)] = None,
) -> ImportResult:
    content = await file.read()
    bundle, assumptions, fmt = service.import_file(file.filename or "dataset.json", content, name=name)
    return ImportResult(source_format=fmt, assumptions=assumptions, dataset=_detail(bundle))


@router.get("/datasets/{dataset_id}", response_model=DatasetDetail)
def get_dataset(dataset_id: str, service: Service, response: Response) -> DatasetDetail:
    bundle = service.get(dataset_id)
    _etag(response, bundle.version.version_no)
    return _detail(bundle)


@router.patch("/datasets/{dataset_id}", response_model=DatasetSummary)
def patch_dataset(dataset_id: str, body: DatasetPatch, service: Service) -> DatasetSummary:
    bundle = service.update_metadata(dataset_id, name=body.name, description=body.description, archived=body.archived)
    return DatasetSummary.of(bundle.dataset, bundle.version)


@router.put("/datasets/{dataset_id}/payload", response_model=DatasetVersionOut)
def replace_payload(
    dataset_id: str,
    body: PayloadUpdate,
    service: Service,
    response: Response,
    if_match: Annotated[str | None, Header()] = None,
) -> DatasetVersionOut:
    bundle = service.update_payload(dataset_id, body.payload, expected_version_no=_parse_if_match(if_match), note=body.note)
    _etag(response, bundle.version.version_no)
    return DatasetVersionOut.of(bundle.version)


@router.delete("/datasets/{dataset_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_dataset(dataset_id: str, service: Service) -> Response:
    service.delete(dataset_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.post("/datasets/{dataset_id}/duplicate", response_model=DatasetDetail, status_code=status.HTTP_201_CREATED)
def duplicate_dataset(dataset_id: str, service: Service, body: DuplicateRequest | None = None) -> DatasetDetail:
    return _detail(service.duplicate(dataset_id, name=body.name if body else None))


@router.get("/datasets/{dataset_id}/export")
def export_dataset(
    dataset_id: str,
    service: Service,
    format: Literal["json", "csv"] = "json",
    version: Annotated[int | None, Query(ge=1)] = None,
) -> Response:
    exported = service.export(dataset_id, format, version)
    return Response(
        content=exported.content,
        media_type=exported.media_type,
        headers={"Content-Disposition": f'attachment; filename="{exported.filename}"'},
    )


@router.post("/datasets/{dataset_id}/validate", response_model=ValidationReport)
def validate_dataset(dataset_id: str, service: Service, body: ValidateRequest | None = None) -> ValidationReport:
    return service.validate(dataset_id, body.payload if body else None)


@router.get("/datasets/{dataset_id}/versions", response_model=Page[DatasetVersionSummary])
def list_versions(dataset_id: str, service: Service, page: PageNo = 1, page_size: PageSize = 20) -> Page[DatasetVersionSummary]:
    versions, total = service.list_versions(dataset_id, page=page, page_size=page_size)
    return Page(items=[DatasetVersionSummary.of(v) for v in versions], total=total, page=page, page_size=page_size)


@router.get("/datasets/{dataset_id}/versions/{version_no}", response_model=DatasetVersionOut)
def get_version(dataset_id: str, version_no: int, service: Service) -> DatasetVersionOut:
    return DatasetVersionOut.of(service.get_version(dataset_id, version_no))


@router.get("/datasets/{dataset_id}/diff", response_model=DatasetDiff)
def diff_versions(
    dataset_id: str,
    service: Service,
    from_: Annotated[int | None, Query(alias="from", ge=1)] = None,
    to: Annotated[int | None, Query(ge=1)] = None,
) -> DatasetDiff:
    from_no, to_no, changes = service.diff(dataset_id, from_, to)
    return DatasetDiff(from_version=from_no, to_version=to_no, changes=changes)

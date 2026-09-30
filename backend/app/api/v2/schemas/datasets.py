"""Dataset registry DTOs."""

from __future__ import annotations

from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, Field, model_validator

from ....db.models import Dataset, DatasetVersion
from ....domain.dataset import DatasetPayload
from ....domain.diff import FieldDiff
from ....domain.validation import ValidationIssue, ValidationReport


class DatasetCreate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=120)
    description: str | None = Field(default=None, max_length=2000)
    template_key: str | None = Field(default=None, max_length=64)
    payload: DatasetPayload | None = None

    @model_validator(mode="after")
    def _one_source(self) -> DatasetCreate:
        if (self.template_key is None) == (self.payload is None):
            raise ValueError("Provide exactly one of template_key or payload")
        if self.payload is not None and self.name is None:
            raise ValueError("name is required when creating from a payload")
        return self


class DatasetPatch(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=120)
    description: str | None = Field(default=None, max_length=2000)
    archived: bool | None = None


class PayloadUpdate(BaseModel):
    payload: DatasetPayload
    note: str | None = Field(default=None, max_length=500)


class DuplicateRequest(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=120)


class ValidateRequest(BaseModel):
    """`payload` is a raw draft, so structural errors come back in the report instead of a 422."""

    payload: dict[str, Any] | None = None


class DatasetVersionSummary(BaseModel):
    version_no: int
    schema_version: str
    content_hash: str
    is_valid: bool
    note: str | None
    created_at: datetime

    @classmethod
    def of(cls, v: DatasetVersion) -> DatasetVersionSummary:
        return cls(
            version_no=v.version_no,
            schema_version=v.schema_version,
            content_hash=v.content_hash,
            is_valid=v.is_valid,
            note=v.note,
            created_at=v.created_at,
        )


class DatasetVersionOut(DatasetVersionSummary):
    validation: ValidationReport
    payload: DatasetPayload

    @classmethod
    def of(cls, v: DatasetVersion) -> DatasetVersionOut:
        return cls(
            **DatasetVersionSummary.of(v).model_dump(),
            validation=ValidationReport.model_validate(v.validation),
            payload=DatasetPayload.model_validate(v.payload),
        )


class DatasetSummary(BaseModel):
    id: str
    name: str
    description: str | None
    source: str
    template_key: str | None
    archived: bool
    current_version_no: int | None
    is_valid: bool | None
    crops: list[str]
    harvest_kg: float | None
    buyer_count: int | None
    created_at: datetime
    updated_at: datetime

    @classmethod
    def of(cls, d: Dataset, v: DatasetVersion | None) -> DatasetSummary:
        payload = v.payload if v is not None else None
        return cls(
            id=d.id,
            name=d.name,
            description=d.description,
            source=d.source,
            template_key=d.template_key,
            archived=d.archived,
            current_version_no=v.version_no if v else None,
            is_valid=v.is_valid if v else None,
            crops=[c["name"] for c in payload["crops"]] if payload else [],
            harvest_kg=sum(lot["quantity_kg"] for lot in payload["harvest_lots"]) if payload else None,
            buyer_count=len(payload["buyers"]) if payload else None,
            created_at=d.created_at,
            updated_at=d.updated_at,
        )


class DatasetDetail(BaseModel):
    dataset: DatasetSummary
    current_version: DatasetVersionOut


class ImportResult(BaseModel):
    source_format: Literal["v1", "v2"]
    assumptions: list[ValidationIssue]
    dataset: DatasetDetail


class DatasetDiff(BaseModel):
    from_version: int
    to_version: int
    changes: list[FieldDiff]

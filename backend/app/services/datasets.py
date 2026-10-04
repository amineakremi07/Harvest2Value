"""Dataset registry: templates, creation, import/export, versioning and validation."""

from __future__ import annotations

import builtins
import csv
import io
import json
import zipfile
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Literal

from pydantic import BaseModel, ValidationError
from sqlalchemy.orm import Session

from ..core.config import REPO_DIR
from ..core.errors import AppError, Conflict, NotFound, ValidationFailed
from ..core.hashing import sha256_of
from ..db.models import DEFAULT_WORKSPACE_ID, Dataset, DatasetVersion
from ..domain.dataset import (
    SCHEMA_VERSION,
    Buyer,
    Crop,
    DatasetPayload,
    HarvestLot,
    Producer,
    Route,
    StorageFacility,
    VehicleType,
)
from ..domain.diff import FieldDiff, payload_diff
from ..domain.migrations_v1 import V1FormatError, detect_format, migrate_v1_to_v2
from ..domain.validation import (
    ValidationIssue,
    ValidationReport,
    report_from_validation_error,
    validate_business,
)
from ..repositories.datasets import DatasetRepository

TEMPLATES_DIR = REPO_DIR / "data" / "templates"
ExportFormat = Literal["json", "csv"]


class TemplateInfo(BaseModel):
    key: str
    name: str
    region: str
    crops: list[str]
    harvest_kg: float
    lot_count: int
    buyer_count: int


@dataclass
class DatasetBundle:
    dataset: Dataset
    version: DatasetVersion


@dataclass
class ExportFile:
    filename: str
    media_type: str
    content: bytes


class DatasetService:
    def __init__(
        self,
        session: Session,
        *,
        workspace_id: str = DEFAULT_WORKSPACE_ID,
        templates_dir: Path = TEMPLATES_DIR,
    ) -> None:
        self.repo = DatasetRepository(session)
        self.workspace_id = workspace_id
        self.templates_dir = templates_dir

    # ---- templates ----

    def list_templates(self) -> list[TemplateInfo]:
        infos = []
        for path in sorted(self.templates_dir.glob("*.json")):
            payload = DatasetPayload.model_validate_json(path.read_text(encoding="utf-8"))
            infos.append(
                TemplateInfo(
                    key=path.stem,
                    name=f"{payload.producer.name} — {', '.join(c.name for c in payload.crops)}",
                    region=payload.producer.region,
                    crops=[c.name for c in payload.crops],
                    harvest_kg=sum(lot.quantity_kg for lot in payload.harvest_lots),
                    lot_count=len(payload.harvest_lots),
                    buyer_count=len(payload.buyers),
                )
            )
        return infos

    def load_template(self, key: str) -> DatasetPayload:
        path = self.templates_dir / f"{key}.json"
        if not key.replace("_", "").replace("-", "").isalnum() or not path.is_file():
            raise NotFound(f"Template '{key}' does not exist.", details={"template_key": key})
        return DatasetPayload.model_validate_json(path.read_text(encoding="utf-8"))

    # ---- create ----

    def create(
        self,
        *,
        name: str,
        payload: DatasetPayload,
        source: str = "manual",
        description: str | None = None,
        template_key: str | None = None,
        note: str | None = None,
        extra_assumptions: list[ValidationIssue] | None = None,
    ) -> DatasetBundle:
        dataset = Dataset(
            workspace_id=self.workspace_id,
            name=name,
            description=description,
            source=source,
            template_key=template_key,
            archived=False,
        )
        self.repo.add(dataset)
        version = self._add_version(dataset, payload, version_no=1, note=note, extra_assumptions=extra_assumptions)
        return DatasetBundle(dataset, version)

    def create_from_template(self, key: str, *, name: str | None = None, description: str | None = None) -> DatasetBundle:
        payload = self.load_template(key)
        return self.create(
            name=name or payload.producer.name,
            payload=payload,
            source="template",
            description=description,
            template_key=key,
            note=f"Created from template '{key}'",
        )

    def import_file(self, filename: str, content: bytes, *, name: str | None = None) -> tuple[DatasetBundle, list[ValidationIssue], str]:
        if not filename.lower().endswith(".json"):
            raise AppError(
                "Only JSON imports are supported for now (CSV import comes in V2.1).",
                code="UNSUPPORTED_IMPORT_FORMAT",
                status=415,
                details={"filename": filename},
            )
        try:
            document = json.loads(content.decode("utf-8-sig"))
        except (UnicodeDecodeError, json.JSONDecodeError) as e:
            raise ValidationFailed(f"The file is not valid JSON: {e}", code="IMPORT_PARSE_ERROR") from e

        fmt = detect_format(document)
        assumptions: list[ValidationIssue] = []
        if fmt == "v1":
            try:
                payload, assumptions = migrate_v1_to_v2(document)
            except V1FormatError as e:
                raise ValidationFailed(str(e), code="IMPORT_PARSE_ERROR") from e
        elif fmt == "v2":
            payload = self._parse_payload(document)
        else:
            raise ValidationFailed(
                "Unrecognized dataset format: expected a v2 document (schema_version) or a v1 document "
                "(producer.harvest_kg, crop, buyers, logistics).",
                code="IMPORT_PARSE_ERROR",
            )

        bundle = self.create(
            name=name or Path(filename).stem[:120] or payload.producer.name,
            payload=payload,
            source="import",
            note=f"Imported from {fmt} file '{Path(filename).name}'",
            extra_assumptions=assumptions,
        )
        return bundle, assumptions, fmt

    # ---- read ----

    def list(self, *, q: str | None, archived: bool | None, page: int, page_size: int) -> tuple[list[tuple[Dataset, DatasetVersion | None]], int]:
        return self.repo.list(self.workspace_id, q=q, archived=archived, offset=(page - 1) * page_size, limit=page_size)

    def get(self, dataset_id: str) -> DatasetBundle:
        dataset = self._dataset(dataset_id)
        return DatasetBundle(dataset, self._current_version(dataset))

    def get_version(self, dataset_id: str, version_no: int) -> DatasetVersion:
        self._dataset(dataset_id)
        version = self.repo.get_version(dataset_id, version_no)
        if version is None:
            raise NotFound(f"Version {version_no} does not exist.", details={"version_no": version_no})
        return version

    def list_versions(self, dataset_id: str, *, page: int, page_size: int) -> tuple[builtins.list[DatasetVersion], int]:
        self._dataset(dataset_id)
        return self.repo.list_versions(dataset_id, offset=(page - 1) * page_size, limit=page_size)

    def diff(self, dataset_id: str, from_no: int | None, to_no: int | None) -> tuple[int, int, builtins.list[FieldDiff]]:
        bundle = self.get(dataset_id)
        to_version = self.get_version(dataset_id, to_no) if to_no is not None else bundle.version
        from_no = from_no if from_no is not None else max(1, to_version.version_no - 1)
        from_version = self.get_version(dataset_id, from_no)
        return from_version.version_no, to_version.version_no, payload_diff(from_version.payload, to_version.payload)

    # ---- update / delete ----

    def update_metadata(
        self, dataset_id: str, *, name: str | None = None, description: str | None = None, archived: bool | None = None
    ) -> DatasetBundle:
        dataset = self._dataset(dataset_id)
        if name is not None:
            dataset.name = name
        if description is not None:
            dataset.description = description
        if archived is not None:
            dataset.archived = archived
        self.repo.session.flush()
        return DatasetBundle(dataset, self._current_version(dataset))

    def update_payload(
        self, dataset_id: str, payload: DatasetPayload, *, expected_version_no: int, note: str | None = None
    ) -> DatasetBundle:
        """Optimistic concurrency: the caller must name the version it edited (If-Match)."""
        dataset = self._dataset(dataset_id)
        current = self._current_version(dataset)
        if current.version_no != expected_version_no:
            raise Conflict(
                f"The dataset changed since version {expected_version_no}; the current version is {current.version_no}.",
                code="VERSION_CONFLICT",
                details={"current_version_no": current.version_no, "expected_version_no": expected_version_no},
            )
        version = self._add_version(dataset, payload, version_no=self.repo.latest_version_no(dataset.id) + 1, note=note)
        return DatasetBundle(dataset, version)

    def delete(self, dataset_id: str) -> None:
        self.repo.delete(self._dataset(dataset_id))

    def duplicate(self, dataset_id: str, *, name: str | None = None) -> DatasetBundle:
        source = self.get(dataset_id)
        return self.create(
            name=name or f"{source.dataset.name} (copy)"[:120],
            payload=DatasetPayload.model_validate(source.version.payload),
            source="duplicate",
            description=source.dataset.description,
            template_key=source.dataset.template_key,
            note=f"Duplicated from '{source.dataset.name}' v{source.version.version_no}",
        )

    # ---- validation / export ----

    def validate(self, dataset_id: str, draft: dict[str, Any] | None = None) -> ValidationReport:
        """Validate a draft payload (structural + business) or the current version."""
        if draft is None:
            return ValidationReport.model_validate(self.get(dataset_id).version.validation)
        self._dataset(dataset_id)
        try:
            payload = DatasetPayload.model_validate(draft)
        except ValidationError as e:
            return report_from_validation_error(e)
        return validate_business(payload)

    def export(self, dataset_id: str, fmt: ExportFormat, version_no: int | None = None) -> ExportFile:
        bundle = self.get(dataset_id)
        version = self.get_version(dataset_id, version_no) if version_no is not None else bundle.version
        stem = _safe_filename(f"{bundle.dataset.name}_v{version.version_no}")
        if fmt == "json":
            content = json.dumps(version.payload, indent=2, ensure_ascii=False).encode("utf-8")
            return ExportFile(f"{stem}.json", "application/json", content)
        return ExportFile(f"{stem}.zip", "application/zip", _csv_zip(version.payload))

    # ---- internals ----

    def _dataset(self, dataset_id: str) -> Dataset:
        dataset = self.repo.get(dataset_id, self.workspace_id)
        if dataset is None:
            raise NotFound(f"Dataset '{dataset_id}' does not exist.", details={"dataset_id": dataset_id})
        return dataset

    def _current_version(self, dataset: Dataset) -> DatasetVersion:
        version = self.repo.get_version_by_id(dataset.current_version_id) if dataset.current_version_id else None
        if version is None:  # cannot happen through the service; guards manual DB edits
            raise NotFound(f"Dataset '{dataset.id}' has no current version.")
        return version

    def _parse_payload(self, document: Any) -> DatasetPayload:
        try:
            return DatasetPayload.model_validate(document)
        except ValidationError as e:
            report = report_from_validation_error(e)
            raise ValidationFailed(
                "The dataset does not match schema v2.",
                code="DATASET_INVALID",
                details={"errors": [i.model_dump() for i in report.errors]},
            ) from e

    def _add_version(
        self,
        dataset: Dataset,
        payload: DatasetPayload,
        *,
        version_no: int,
        note: str | None,
        extra_assumptions: builtins.list[ValidationIssue] | None = None,
    ) -> DatasetVersion:
        document = payload.model_dump(mode="json")
        report = validate_business(payload)
        report.assumptions = [*(extra_assumptions or []), *report.assumptions]
        version = DatasetVersion(
            dataset_id=dataset.id,
            version_no=version_no,
            schema_version=SCHEMA_VERSION,
            payload=document,
            content_hash=sha256_of(document),
            validation=report.model_dump(mode="json"),
            is_valid=report.is_valid,
            note=note,
        )
        self.repo.add_version(version)
        dataset.current_version_id = version.id
        self.repo.session.flush()
        return version


def _safe_filename(text: str) -> str:
    cleaned = "".join(ch if ch.isalnum() or ch in "-_." else "_" for ch in text)
    return cleaned.strip("_")[:100] or "dataset"


_CSV_SECTIONS: dict[str, type[BaseModel]] = {
    "producer": Producer,
    "crops": Crop,
    "harvest_lots": HarvestLot,
    "buyers": Buyer,
    "storage_facilities": StorageFacility,
    "vehicle_types": VehicleType,
    "routes": Route,
}


def _cell(value: Any) -> Any:
    if value is None:
        return ""
    if isinstance(value, (list, dict)):
        return json.dumps(value, ensure_ascii=False)
    return value


def _rows_to_csv(rows: list[dict[str, Any]], fieldnames: list[str]) -> bytes:
    buffer = io.StringIO()
    writer = csv.DictWriter(buffer, fieldnames=fieldnames, lineterminator="\n")
    writer.writeheader()
    for row in rows:
        writer.writerow({k: _cell(row.get(k)) for k in fieldnames})
    return buffer.getvalue().encode("utf-8")


def _csv_zip(payload: dict[str, Any]) -> bytes:
    """One CSV per entity; list/object cells are JSON-encoded. Field order follows schema v2."""
    archive = io.BytesIO()
    with zipfile.ZipFile(archive, "w", zipfile.ZIP_DEFLATED) as zf:
        meta = {"schema_version": payload["schema_version"], "currency": payload.get("currency")}
        zf.writestr("dataset.csv", _rows_to_csv([meta], list(meta)))
        for section, model in _CSV_SECTIONS.items():
            rows = payload[section] if isinstance(payload[section], list) else [payload[section]]
            zf.writestr(f"{section}.csv", _rows_to_csv(rows, list(model.model_fields)))
    return archive.getvalue()

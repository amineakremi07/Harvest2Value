"""Frozen reports (phase 13).

A report is a SNAPSHOT: at creation every chosen section is computed from the stored results and
copied into `reports.snapshot` (JSON). Reading, printing or exporting a report never recomputes
anything, so the report never changes even if datasets, scenarios or runs are later edited or
deleted. `snapshot_hash` lets anyone check the copy is intact.
"""

from __future__ import annotations

import copy
import csv
import io
from datetime import datetime, timezone
from typing import Any

from sqlalchemy.orm import Session

from ..core.errors import NotFound, ValidationFailed
from ..core.hashing import sha256_of
from ..db.models import DEFAULT_WORKSPACE_ID, DatasetVersion, Report, Scenario
from ..domain.report import ReportSection, ReportSpec
from ..repositories.datasets import DatasetRepository
from ..repositories.reports import ReportRepository
from .analytics import AnalyticsService
from .comparisons import ComparisonService
from .insights import InsightService
from .optimization import OptimizationService

SNAPSHOT_SCHEMA = 1

# section -> {table name: path inside the section} (first table is the default CSV export)
TABLES: dict[ReportSection, dict[str, str]] = {
    "summary": {"kpis": "kpis"},
    "financial": {"by_buyer": "by_buyer", "daily": "daily", "waterfall": "waterfall"},
    "operational": {"daily": "daily", "storage": "storage"},
    "buyers": {"buyers": "buyers"},
    "logistics": {"vehicles": "vehicles", "routes": "routes", "daily": "daily"},
    "crops": {"lots": "lots"},
    "insights": {"insights": "items"},
    "comparison": {"kpis": "kpi_rows", "buyers": "buyer_rows", "notable_changes": "notable_changes"},
}


def _section(session: Session, workspace_id: str, section: ReportSection, spec: ReportSpec) -> dict[str, Any]:
    analytics = AnalyticsService(session, workspace_id=workspace_id)
    runs = OptimizationService(session, workspace_id=workspace_id)
    if section == "summary":
        result = runs.result(spec.run_id)
        kpis = result.kpis.model_dump(mode="json")
        return {
            "outcome_label": result.outcome_label,
            "objective": result.objective,
            "horizon_days": result.horizon_days,
            "kpis": [{"kpi": k, "value": v} for k, v in kpis.items() if isinstance(v, (int, float)) and not isinstance(v, bool)],
            "kpi_values": kpis,
            "warnings": result.warnings,
        }
    if section == "financial":
        return analytics.financial(spec.run_id).model_dump(mode="json")
    if section == "operational":
        return analytics.operational(spec.run_id).model_dump(mode="json")
    if section == "buyers":
        data = analytics.buyers(spec.run_id).model_dump(mode="json")
        for b in data["buyers"]:
            b["served_days"] = ", ".join(str(d) for d in b.get("served_days", []))
        return data
    if section == "logistics":
        data = analytics.logistics(spec.run_id).model_dump(mode="json")
        for v in data["vehicles"]:
            v["binding_days"] = ", ".join(str(d) for d in v.get("binding_days", []))
        return data
    if section == "crops":
        return analytics.crops(spec.run_id).model_dump(mode="json")
    if section == "insights":
        views = InsightService(session, workspace_id=workspace_id).list(spec.run_id)
        return {
            "items": [
                {"severity": v.severity, "category": v.category, "rule_id": v.rule_id, "message": v.message}
                for v in views
            ]
        }
    if section == "comparison":
        result = ComparisonService(session, workspace_id=workspace_id).compare(spec.run_id, spec.compare_run_ids)
        ids = [result.baseline_run_id, *result.run_ids]
        labels = {r.run_id: r.label or r.run_id[:8] for r in result.runs}
        kpi_rows = []
        for row in result.kpi_table:
            item: dict[str, Any] = {"kpi": row.kpi, "label": row.label, "unit": row.unit, "better": row.better}
            for run_id in ids:
                item[labels[run_id]] = row.values.get(run_id)
                if run_id in row.deltas:
                    item[f"{labels[run_id]} (Δ)"] = row.deltas[run_id].abs
                    item[f"{labels[run_id]} (Δ %)"] = row.deltas[run_id].pct
            kpi_rows.append(item)
        buyer_rows = []
        for buyer in result.buyer_matrix:
            item = {"buyer_id": buyer.buyer_id, "buyer_name": buyer.buyer_name}
            for run_id in ids:
                cell = buyer.cells.get(run_id)
                item[f"{labels[run_id]} kg"] = cell.sold_kg if cell else None
                if run_id != result.baseline_run_id and cell:
                    item[f"{labels[run_id]} Δ kg"] = cell.delta_kg
                    item[f"{labels[run_id]} statut"] = cell.status
            buyer_rows.append(item)
        return {
            "baseline_run_id": result.baseline_run_id,
            "run_ids": result.run_ids,
            "labels": labels,
            "kpi_rows": kpi_rows,
            "buyer_rows": buyer_rows,
            "notable_changes": [{"run": labels.get(c.run_id, c.run_id), "message": c.message} for c in result.notable_changes],
        }
    raise ValidationFailed(f"Unknown section {section!r}")


class ReportService:
    def __init__(self, session: Session, *, workspace_id: str = DEFAULT_WORKSPACE_ID) -> None:
        self.session = session
        self.workspace_id = workspace_id
        self.repo = ReportRepository(session)

    def build_snapshot(self, spec: ReportSpec, narrative: dict[str, Any] | None = None) -> dict[str, Any]:
        runs = OptimizationService(self.session, workspace_id=self.workspace_id)
        run = runs.get(spec.run_id)
        runs.require_result(run.id)  # 409 if the main run has no plan
        version = self.session.get(DatasetVersion, run.dataset_version_id)
        dataset = DatasetRepository(self.session).get(run.dataset_id, self.workspace_id)
        scenario = self.session.get(Scenario, run.scenario_id) if run.scenario_id else None
        payload = version.payload if version else {}
        compared = []
        for run_id in spec.compare_run_ids:
            other = runs.get(run_id)
            compared.append({"id": other.id, "label": other.label, "scenario_id": other.scenario_id, "created_at": other.created_at.isoformat()})
        snapshot = {
            "schema": SNAPSHOT_SCHEMA,
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "title": spec.title,
            "currency": payload.get("currency") or "TND",
            "run": {
                "id": run.id,
                "label": run.label,
                "objective": run.config.get("objective", "profit"),
                "created_at": run.created_at.isoformat(),
                "solve_seconds": run.solve_seconds,
                "dataset_id": run.dataset_id,
                "dataset_name": dataset.name if dataset else None,
                "version_no": version.version_no if version else None,
                "scenario_id": run.scenario_id,
                "scenario_name": scenario.name if scenario else None,
                "producer": (payload.get("producer") or {}).get("name"),
                "region": (payload.get("producer") or {}).get("region"),
            },
            "compared_runs": compared,
            "sections": {section: _section(self.session, self.workspace_id, section, spec) for section in spec.sections},
            "narrative": narrative,
        }
        return copy.deepcopy(snapshot)

    def create(self, spec: ReportSpec, narrative: dict[str, Any] | None = None) -> Report:
        snapshot = self.build_snapshot(spec, narrative)
        report = Report(
            workspace_id=self.workspace_id,
            title=spec.title,
            spec=spec.model_dump(mode="json"),
            snapshot=snapshot,
            snapshot_hash=sha256_of(snapshot),
            run_id=spec.run_id,
        )
        return self.repo.add(report)

    def get(self, report_id: str) -> Report:
        report = self.repo.get(report_id, self.workspace_id)
        if report is None:
            raise NotFound(f"Report '{report_id}' does not exist.", details={"report_id": report_id})
        return report

    def list(self, *, run_id: str | None, page: int, page_size: int) -> tuple[list[Report], int]:
        return self.repo.list(self.workspace_id, run_id=run_id, page=page, page_size=page_size)

    def delete(self, report_id: str) -> None:
        self.repo.delete(self.get(report_id))

    def csv(self, report_id: str, section: str, table: str | None) -> tuple[str, bytes]:
        report = self.get(report_id)
        sections: dict[str, Any] = report.snapshot.get("sections", {})
        if section not in sections:
            raise NotFound(f"Section '{section}' is not in this report.", details={"available": list(sections)})
        tables = TABLES[section]  # type: ignore[index]
        name = table or next(iter(tables))
        if name not in tables:
            raise NotFound(f"Table '{name}' does not exist in section '{section}'.", details={"available": list(tables)})
        rows = sections[section].get(tables[name]) or []
        return f"{_slug(report.title)}-{section}-{name}.csv", rows_to_csv(rows)


def rows_to_csv(rows: list[dict[str, Any]]) -> bytes:
    """UTF-8 with BOM (opens correctly in Excel), `;`-free values flattened."""
    fieldnames: list[str] = []
    for row in rows:
        for key in row:
            if key not in fieldnames:
                fieldnames.append(key)
    buffer = io.StringIO()
    writer = csv.DictWriter(buffer, fieldnames=fieldnames, extrasaction="ignore")
    writer.writeheader()
    for row in rows:
        writer.writerow({k: _cell(row.get(k)) for k in fieldnames})
    return ("﻿" + buffer.getvalue()).encode("utf-8")


def _cell(value: Any) -> Any:
    if isinstance(value, (dict, list)):
        return str(value)
    if isinstance(value, str) and value[:1] in ("=", "+", "-", "@") and not _is_number(value):
        return "'" + value  # CSV formula injection guard
    return "" if value is None else value


def _is_number(text: str) -> bool:
    try:
        float(text)
    except ValueError:
        return False
    return True


def _slug(text: str) -> str:
    slug = "".join(c if c.isalnum() else "-" for c in text.lower()).strip("-")
    return "-".join(filter(None, slug.split("-")))[:60] or "rapport"

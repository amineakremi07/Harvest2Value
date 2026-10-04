"""Scenario registry: CRUD, ordered changes, lineage, preview, stale detection and rebase.

A scenario = a base dataset version + an ordered list of typed changes; a child applies its
ancestors' changes first. Every write re-applies the full chain, so an invalid change is rejected
with SCENARIO_APPLY_ERROR (422) and nothing is saved.
"""

from __future__ import annotations

import builtins
from dataclasses import dataclass
from typing import Any

from pydantic import ValidationError
from sqlalchemy.orm import Session

from ..core.errors import Conflict, NotFound, ValidationFailed
from ..db.models import DEFAULT_WORKSPACE_ID, Dataset, DatasetVersion, OptimizationRun, Scenario, ScenarioChange
from ..domain.dataset import DatasetPayload
from ..domain.diff import FieldDiff
from ..domain.enums import ScenarioStatus
from ..domain.scenario import AppliedChange, ScenarioChangeModel, parse_change
from ..domain.validation import ValidationReport, validate_business
from ..repositories.datasets import DatasetRepository
from ..repositories.runs import RunRepository
from ..repositories.scenarios import ScenarioRepository
from ..scenarios.apply import ApplyResult, ChangeRef, apply_changes
from ..scenarios.lineage import resolve_chain

MAX_CHANGES = 100


@dataclass
class ScenarioDetailData:
    scenario: Scenario
    dataset: Dataset
    base_version: DatasetVersion
    changes: list[ScenarioChange]
    lineage: list[Scenario]
    runs: list[OptimizationRun]
    stale: bool


@dataclass
class PreviewData:
    base_version: DatasetVersion
    effective: DatasetPayload
    diff: list[FieldDiff]
    applied: list[AppliedChange]
    validation: ValidationReport


def change_to_model(row: ScenarioChange) -> ScenarioChangeModel:
    return parse_change(
        {"op": row.op, "target": row.target, "params": row.params, "enabled": row.enabled, "source": row.source, "note": row.note}
    )


def model_to_fields(change: ScenarioChangeModel) -> dict[str, Any]:
    data = change.model_dump(mode="json")
    return {
        "op": data["op"],
        "target": data["target"],
        "params": data["params"],
        "enabled": data["enabled"],
        "source": data["source"],
        "note": data["note"],
    }


class ScenarioService:
    def __init__(self, session: Session, *, workspace_id: str = DEFAULT_WORKSPACE_ID) -> None:
        self.session = session
        self.repo = ScenarioRepository(session)
        self.datasets = DatasetRepository(session)
        self.runs = RunRepository(session)
        self.workspace_id = workspace_id

    # ---- lookups ----

    def get(self, scenario_id: str) -> Scenario:
        scenario = self.repo.get(scenario_id, self.workspace_id)
        if scenario is None:
            raise NotFound(f"Scenario '{scenario_id}' does not exist.", details={"scenario_id": scenario_id})
        self._refresh_stale(scenario)
        return scenario

    def _dataset(self, dataset_id: str) -> Dataset:
        dataset = self.datasets.get(dataset_id, self.workspace_id)
        if dataset is None:
            raise NotFound(f"Dataset '{dataset_id}' does not exist.", details={"dataset_id": dataset_id})
        return dataset

    def _version(self, dataset: Dataset, version_no: int | None) -> DatasetVersion:
        if version_no is None:
            version = self.datasets.get_version_by_id(dataset.current_version_id) if dataset.current_version_id else None
        else:
            version = self.datasets.get_version(dataset.id, version_no)
        if version is None:
            raise NotFound(f"Version {version_no} of dataset '{dataset.id}' does not exist.", details={"version_no": version_no})
        return version

    def base_version(self, scenario: Scenario) -> DatasetVersion:
        version = self.datasets.get_version_by_id(scenario.base_version_id)
        assert version is not None  # FK
        return version

    def is_stale(self, scenario: Scenario) -> bool:
        dataset = self.datasets.get(scenario.dataset_id, self.workspace_id)
        return dataset is not None and dataset.current_version_id != scenario.base_version_id

    def _refresh_stale(self, scenario: Scenario) -> None:
        if scenario.status != ScenarioStatus.ARCHIVED and self.is_stale(scenario) and scenario.status != ScenarioStatus.STALE:
            scenario.status = ScenarioStatus.STALE
            self.session.flush()

    def lineage(self, scenario: Scenario) -> list[Scenario]:
        return resolve_chain(scenario, lambda pid: self.repo.get(pid, self.workspace_id))

    def chain_changes(self, scenario: Scenario, own: list[ScenarioChangeModel] | None = None) -> list[ChangeRef]:
        """Ancestors' changes, then the scenario's own (or `own`, a candidate list being validated)."""
        refs: list[ChangeRef] = []
        chain = self.lineage(scenario)
        for member in chain[:-1]:
            refs += [ChangeRef(change_to_model(row), member.id, row.id) for row in self.repo.changes(member.id)]
        if own is None:
            refs += [ChangeRef(change_to_model(row), scenario.id, row.id) for row in self.repo.changes(scenario.id)]
        else:
            refs += [ChangeRef(change, scenario.id, None) for change in own]
        return refs

    def effective_input(self, scenario: Scenario, *, base: DatasetVersion | None = None) -> ApplyResult:
        version = base or self.base_version(scenario)
        return apply_changes(DatasetPayload.model_validate(version.payload), self.chain_changes(scenario))

    # ---- create / list / update / delete ----

    def create(
        self,
        *,
        name: str,
        dataset_id: str | None,
        description: str | None = None,
        version_no: int | None = None,
        parent_id: str | None = None,
        changes: list[ScenarioChangeModel] | None = None,
        tags: list[str] | None = None,
    ) -> Scenario:
        parent = self.get(parent_id) if parent_id else None
        if parent is not None and dataset_id is not None and dataset_id != parent.dataset_id:
            raise ValidationFailed("A child scenario must use its parent's dataset.", code="SCENARIO_PARENT_MISMATCH")
        if parent is None and dataset_id is None:
            raise ValidationFailed("dataset_id is required for a root scenario.")
        dataset = self._dataset(parent.dataset_id if parent else dataset_id)  # type: ignore[arg-type]
        if parent is not None and version_no is None:
            version = self.base_version(parent)
        else:
            version = self._version(dataset, version_no)
        scenario = Scenario(
            workspace_id=self.workspace_id,
            dataset_id=dataset.id,
            name=name,
            description=description,
            base_version_id=version.id,
            parent_id=parent.id if parent else None,
            status=ScenarioStatus.DRAFT,
            tags=tags,
        )
        self.repo.add(scenario)
        for change in changes or []:
            self._append(scenario, change)
        self.effective_input(scenario)  # validates the whole chain (raises SCENARIO_APPLY_ERROR)
        self._refresh_stale(scenario)
        return scenario

    def list(self, *, dataset_id: str | None, status: str | None, page: int, page_size: int) -> tuple[list[Scenario], int]:
        rows, total = self.repo.list(self.workspace_id, dataset_id=dataset_id, status=status, offset=(page - 1) * page_size, limit=page_size)
        for row in rows:
            self._refresh_stale(row)
        return rows, total

    def detail(self, scenario_id: str) -> ScenarioDetailData:
        scenario = self.get(scenario_id)
        runs, _ = self.runs.list(self.workspace_id, scenario_id=scenario.id, limit=50)
        return ScenarioDetailData(
            scenario=scenario,
            dataset=self._dataset(scenario.dataset_id),
            base_version=self.base_version(scenario),
            changes=self.repo.changes(scenario.id),
            lineage=self.lineage(scenario),
            runs=runs,
            stale=self.is_stale(scenario),
        )

    def update(
        self,
        scenario_id: str,
        *,
        name: str | None = None,
        description: str | None = None,
        tags: builtins.list[str] | None = None,
        archived: bool | None = None,
    ) -> Scenario:
        scenario = self.get(scenario_id)
        if name is not None:
            scenario.name = name
        if description is not None:
            scenario.description = description
        if tags is not None:
            scenario.tags = tags
        if archived is True:
            scenario.status = ScenarioStatus.ARCHIVED
        elif archived is False and scenario.status == ScenarioStatus.ARCHIVED:
            scenario.status = ScenarioStatus.DRAFT
            self._refresh_stale(scenario)
        self.session.flush()
        return scenario

    def delete(self, scenario_id: str, *, cascade: bool = False) -> None:
        scenario = self.get(scenario_id)
        children = self.repo.children(scenario.id)
        if children and not cascade:
            raise Conflict(
                f"Scenario '{scenario.name}' has {len(children)} child scenario(s); delete them first or pass cascade=true.",
                code="HAS_CHILDREN",
                details={"children": [c.id for c in children]},
            )
        self.repo.delete(scenario)  # children and changes: ON DELETE CASCADE; runs keep their data (scenario_id -> NULL)
        self.session.expire_all()

    def duplicate(self, scenario_id: str, *, name: str | None = None) -> Scenario:
        source = self.get(scenario_id)
        copy = Scenario(
            workspace_id=self.workspace_id,
            dataset_id=source.dataset_id,
            name=name or f"{source.name} (copy)"[:120],
            description=source.description,
            base_version_id=source.base_version_id,
            parent_id=source.parent_id,
            status=ScenarioStatus.DRAFT,
            tags=list(source.tags) if source.tags else None,
        )
        self.repo.add(copy)
        for row in self.repo.changes(source.id):
            self._append(copy, change_to_model(row))
        self._refresh_stale(copy)
        return copy

    def branch(self, scenario_id: str, *, name: str, description: str | None = None) -> Scenario:
        parent = self.get(scenario_id)
        return self.create(name=name, dataset_id=parent.dataset_id, description=description, parent_id=parent.id)

    # ---- changes ----

    def _append(self, scenario: Scenario, change: ScenarioChangeModel) -> ScenarioChange:
        existing = self.repo.changes(scenario.id)
        if len(existing) >= MAX_CHANGES:
            raise ValidationFailed(f"A scenario holds at most {MAX_CHANGES} changes.", code="TOO_MANY_CHANGES")
        row = ScenarioChange(scenario_id=scenario.id, position=len(existing), **model_to_fields(change))
        self.repo.add_change(row)
        return row

    def _changed(self, scenario: Scenario) -> None:
        self.effective_input(scenario)  # raises SCENARIO_APPLY_ERROR -> the transaction rolls back
        if scenario.status in (ScenarioStatus.READY,):
            scenario.status = ScenarioStatus.DRAFT
        self.session.flush()

    def add_change(self, scenario_id: str, change: ScenarioChangeModel) -> Scenario:
        scenario = self.get(scenario_id)
        self._append(scenario, change)
        self._changed(scenario)
        return scenario

    def update_change(self, scenario_id: str, change_id: str, patch: dict[str, Any]) -> Scenario:
        scenario = self.get(scenario_id)
        row = self._change(scenario, change_id)
        merged = {**model_to_fields(change_to_model(row)), **patch}
        try:
            change = parse_change(merged)
        except ValidationError as e:
            raise ValidationFailed(
                "The updated change is invalid.",
                details={"errors": [{"loc": list(err["loc"]), "msg": err["msg"]} for err in e.errors()]},
            ) from e
        for key, value in model_to_fields(change).items():
            setattr(row, key, value)
        self.session.flush()
        self._changed(scenario)
        return scenario

    def delete_change(self, scenario_id: str, change_id: str) -> Scenario:
        scenario = self.get(scenario_id)
        self.repo.delete_change(self._change(scenario, change_id))
        self.repo.set_order(self.repo.changes(scenario.id))
        self._changed(scenario)
        return scenario

    def reorder(self, scenario_id: str, ids: builtins.list[str]) -> Scenario:
        scenario = self.get(scenario_id)
        rows = {row.id: row for row in self.repo.changes(scenario.id)}
        if sorted(ids) != sorted(rows) or len(ids) != len(set(ids)):
            raise ValidationFailed(
                "ids must list every change of the scenario exactly once.",
                code="INVALID_ORDER",
                details={"expected": sorted(rows)},
            )
        self.repo.set_order([rows[i] for i in ids])
        self._changed(scenario)
        return scenario

    def _change(self, scenario: Scenario, change_id: str) -> ScenarioChange:
        row = self.repo.get_change(scenario.id, change_id)
        if row is None:
            raise NotFound(f"Change '{change_id}' does not exist in this scenario.", details={"change_id": change_id})
        return row

    # ---- preview / rebase ----

    def preview(self, scenario_id: str) -> PreviewData:
        scenario = self.get(scenario_id)
        version = self.base_version(scenario)
        applied = self.effective_input(scenario, base=version)
        return PreviewData(version, applied.effective, applied.diff, applied.applied, validate_business(applied.effective))

    def apply_preview(self, dataset_id: str, version_no: int | None, changes: builtins.list[ScenarioChangeModel]) -> PreviewData:
        version = self._version(self._dataset(dataset_id), version_no)
        applied = apply_changes(DatasetPayload.model_validate(version.payload), changes)
        return PreviewData(version, applied.effective, applied.diff, applied.applied, validate_business(applied.effective))

    def rebase(self, scenario_id: str) -> Scenario:
        """Move the scenario to the dataset's current version and re-apply the same changes."""
        scenario = self.get(scenario_id)
        dataset = self._dataset(scenario.dataset_id)
        current = self._version(dataset, None)
        self.effective_input(scenario, base=current)  # 422 if a change no longer applies
        scenario.base_version_id = current.id
        if scenario.status != ScenarioStatus.ARCHIVED:
            scenario.status = ScenarioStatus.DRAFT
        self.session.flush()
        return scenario

"""apply_changes(base, changes) -> (effective payload, applied changes, field diff).

Changes apply in order; disabled changes are skipped. After each change the full document is
re-validated, so a change that breaks the dataset fails at *its* index with SCENARIO_APPLY_ERROR.
"""

from __future__ import annotations

import copy
from collections.abc import Sequence
from dataclasses import dataclass

from pydantic import ValidationError

from ..core.errors import ScenarioApplyError
from ..domain.dataset import DatasetPayload
from ..domain.diff import FieldDiff
from ..domain.scenario import AppliedChange, ScenarioChangeModel
from .diff import scenario_diff
from .operations import OPERATIONS, ChangeError


@dataclass(frozen=True)
class ChangeRef:
    """A change plus where it comes from (for error messages and lineage)."""

    change: ScenarioChangeModel
    scenario_id: str | None = None
    change_id: str | None = None


@dataclass(frozen=True)
class ApplyResult:
    effective: DatasetPayload
    applied: list[AppliedChange]
    diff: list[FieldDiff]


def _ref(item: ScenarioChangeModel | ChangeRef) -> ChangeRef:
    return item if isinstance(item, ChangeRef) else ChangeRef(item)


def _error(index: int, ref: ChangeRef, reason: str) -> ScenarioApplyError:
    return ScenarioApplyError(
        f"Change #{index} ({ref.change.op}) cannot be applied: {reason}",
        details={
            "change_index": index,
            "op": ref.change.op,
            "target": ref.change.target,
            "reason": reason,
            "scenario_id": ref.scenario_id,
            "change_id": ref.change_id,
        },
    )


def apply_changes(base: DatasetPayload, changes: Sequence[ScenarioChangeModel | ChangeRef]) -> ApplyResult:
    base_doc = base.model_dump(mode="json")
    working = copy.deepcopy(base_doc)
    effective = base
    applied: list[AppliedChange] = []
    for index, item in enumerate(changes):
        ref = _ref(item)
        if not ref.change.enabled:
            continue
        operation = OPERATIONS[ref.change.op]
        try:
            operation.validate(working, ref.change)
            summary = operation.apply(working, ref.change)
            effective = DatasetPayload.model_validate(working)
        except ChangeError as e:
            raise _error(index, ref, e.reason) from e
        except ValidationError as e:
            first = e.errors()[0]
            where = ".".join(str(p) for p in first.get("loc", ()))
            raise _error(index, ref, f"the dataset would become invalid: {first.get('msg', '')} {f'({where})' if where else ''}".strip()) from e
        working = effective.model_dump(mode="json")
        applied.append(
            AppliedChange(
                index=index,
                op=ref.change.op,
                target=ref.change.target,
                summary=summary,
                scenario_id=ref.scenario_id,
                change_id=ref.change_id,
            )
        )
    return ApplyResult(effective=effective, applied=applied, diff=scenario_diff(base_doc, working))

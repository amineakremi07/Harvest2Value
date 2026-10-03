"""Read-only scenario tools: preview changes without saving them, compare runs."""

from __future__ import annotations

from typing import Any

from pydantic import Field, ValidationError

from ...core.errors import AppError
from ...domain.dataset import DatasetPayload
from ...domain.scenario import ScenarioChangeModel, parse_change
from ...domain.validation import validate_business
from ...scenarios.apply import ChangeRef, apply_changes
from ...services.comparisons import ComparisonService
from ...services.scenarios import PreviewData, ScenarioService
from .common import resolve_dataset, resolve_run
from .registry import ToolArgs, ToolContext, ToolFailure, ToolResult, facts, tool

MAX_CHANGES = 20


class ChangeSpec(ToolArgs):
    op: str = Field(max_length=32)
    target: str | None = Field(default=None, max_length=64, description="Entity id, '*' for all, or null")
    params: dict[str, Any] = Field(default_factory=dict)


class ScenarioBaseArgs(ToolArgs):
    changes: list[ChangeSpec] = Field(min_length=1, max_length=MAX_CHANGES)
    dataset_id: str | None = Field(default=None, max_length=64, description="Base dataset alias/id (current version)")
    parent_scenario_id: str | None = Field(default=None, max_length=64, description="Build on top of this scenario instead")


def parse_changes(specs: list[ChangeSpec], *, source: str = "ai_proposed") -> list[ScenarioChangeModel]:
    parsed: list[ScenarioChangeModel] = []
    for i, spec in enumerate(specs):
        try:
            parsed.append(parse_change({"op": spec.op, "target": spec.target, "params": spec.params, "source": source}))
        except ValidationError as exc:
            reasons = "; ".join(f"{'.'.join(map(str, e['loc']))}: {e['msg']}" for e in exc.errors(include_url=False))[:400]
            raise ToolFailure(f"Change #{i + 1} ({spec.op}) is invalid: {reasons}. Read list_change_ops.") from exc
    return parsed


def preview_changes(ctx: ToolContext, args: ScenarioBaseArgs, changes: list[ScenarioChangeModel]) -> tuple[PreviewData, str, str | None]:
    """Applies the changes (on a dataset's current version, or on top of a scenario's chain)."""
    service = ScenarioService(ctx.session, workspace_id=ctx.workspace_id)
    try:
        parent_id = ctx.resolve("scenario", args.parent_scenario_id) if args.parent_scenario_id else None
        if parent_id:
            parent = service.get(parent_id)
            version = service.base_version(parent)
            chain = service.chain_changes(parent) + [ChangeRef(c, None, None) for c in changes]
            applied = apply_changes(DatasetPayload.model_validate(version.payload), chain)
            preview = PreviewData(version, applied.effective, applied.diff, applied.applied, validate_business(applied.effective))
            ctx.alias("scenario", parent.id)
            return preview, parent.dataset_id, parent.id
        dataset, _version = resolve_dataset(ctx, args.dataset_id)
        return service.apply_preview(dataset.id, None, changes), dataset.id, None
    except AppError as exc:
        index = exc.details.get("change_index")
        raise ToolFailure(f"The changes cannot be applied{f' (change #{index + 1})' if isinstance(index, int) else ''}: {exc.message}") from exc


def preview_facts(ctx: ToolContext, prefix: str, preview: PreviewData) -> dict[str, Any]:
    out: dict[str, Any] = {}
    for i, a in enumerate(preview.applied[-MAX_CHANGES:]):
        out[f"{prefix}.applied.{i + 1}"] = a.summary
    for d in preview.diff[:25]:
        path = d.path.replace("[", ".").replace("]", "")
        out.update(facts(ctx, f"{prefix}.diff.{path}", {"before": d.before, "after": d.after}))
    for i, e in enumerate(preview.validation.errors):
        out[f"{prefix}.validation_error.{i + 1}"] = e.message
    for i, w in enumerate(preview.validation.warnings[:5]):
        out[f"{prefix}.validation_warning.{i + 1}"] = w.message
    return out


@tool(
    "preview_scenario",
    "Applies scenario changes to the data WITHOUT saving anything: returns what each change does, the "
    "field diff and the validation of the resulting data. Use it to check changes before proposing them.",
    ScenarioBaseArgs,
)
def preview_scenario(ctx: ToolContext, args: ScenarioBaseArgs) -> ToolResult:
    changes = parse_changes(args.changes)
    preview, _dataset_id, _parent = preview_changes(ctx, args, changes)
    return ToolResult(preview_facts(ctx, "preview", preview), note=f"aperçu de {len(changes)} modification(s)")


class CompareArgs(ToolArgs):
    baseline_run_id: str = Field(max_length=64)
    run_ids: list[str] = Field(min_length=1, max_length=3)


@tool(
    "compare_runs",
    "Compares a baseline run with 1 to 3 runs of the same crop: KPI values and deltas, buyer volume "
    "changes and the notable changes computed by the backend.",
    CompareArgs,
)
def compare_runs(ctx: ToolContext, args: CompareArgs) -> ToolResult:
    baseline = resolve_run(ctx, args.baseline_run_id)
    others = [resolve_run(ctx, r) for r in args.run_ids]
    result = ComparisonService(ctx.session, workspace_id=ctx.workspace_id).compare(baseline.id, [r.id for r in others])
    alias = {r.id: ctx.alias("run", r.id) for r in [baseline, *others]}
    comparison = ctx.alias("comparison", "|".join([baseline.id, *[r.id for r in others]]))
    out: dict[str, Any] = {f"{comparison}.baseline": alias[baseline.id]}
    for row in result.kpi_table:
        for run_id, value in row.values.items():
            if value is not None:
                out.update(facts(ctx, f"{comparison}.{alias[run_id]}.{row.kpi}.value", value))
        for run_id, delta in row.deltas.items():
            if delta.abs is not None:
                out.update(facts(ctx, f"{comparison}.{alias[run_id]}.{row.kpi}.delta", delta.abs))
            if delta.pct is not None:
                out.update(facts(ctx, f"{comparison}.{alias[run_id]}.{row.kpi}.delta_pct", delta.pct))
    for buyer in result.buyer_matrix:
        for run_id, cell in buyer.cells.items():
            if run_id != baseline.id and cell.delta_kg:
                out.update(facts(ctx, f"{comparison}.{alias[run_id]}.buyer.{buyer.buyer_id}.sold_kg.delta", cell.delta_kg))
    for i, change in enumerate(sorted(result.notable_changes, key=lambda c: -c.magnitude)[:8]):
        out[f"{comparison}.notable.{i + 1}"] = f"{alias.get(change.run_id, change.run_id)}: {change.message}"
    return ToolResult(out, note=f"comparaison {comparison}")

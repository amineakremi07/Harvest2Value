"""Read-only tools: page context, dataset, market analysis, scenario operation catalogue."""

from __future__ import annotations

from typing import Any

from pydantic import Field

from ...domain.dataset import DatasetPayload
from ...domain.scenario import CHANGE_TYPES
from ...scenarios.operations import OPERATIONS
from ...services.analytics import AnalyticsService
from ...services.optimization import OptimizationService
from ...services.scenarios import ScenarioService
from .common import resolve_dataset
from .registry import ToolArgs, ToolContext, ToolResult, facts, tool


class NoArgs(ToolArgs):
    pass


@tool(
    "get_context",
    "What the user has on screen (run, dataset, scenario) with their aliases (r1, d1, s1), and the "
    "latest successful run. Call it first when the question refers to 'this run', 'my plan', etc.",
    NoArgs,
)
def get_context(ctx: ToolContext, _args: NoArgs) -> ToolResult:
    out: dict[str, Any] = {"page": ctx.page.page or "inconnue"}
    runs = OptimizationService(ctx.session, workspace_id=ctx.workspace_id)
    if ctx.page.run_id:
        run = runs.get(ctx.page.run_id)
        out["run_on_screen"] = ctx.alias("run", run.id)
        out["run_on_screen_status"] = run.status
        out["run_on_screen_label"] = run.label or ""
        out["dataset_of_run"] = ctx.alias("dataset", run.dataset_id)
        if run.scenario_id:
            out["scenario_of_run"] = ctx.alias("scenario", run.scenario_id)
    if ctx.page.dataset_id:
        out["dataset_on_screen"] = ctx.alias("dataset", ctx.page.dataset_id)
    if ctx.page.scenario_id:
        scenario = ScenarioService(ctx.session, workspace_id=ctx.workspace_id).get(ctx.page.scenario_id)
        out["scenario_on_screen"] = ctx.alias("scenario", scenario.id)
        out["scenario_on_screen_name"] = scenario.name
    for i, run_id in enumerate(ctx.page.compare_run_ids):
        out[f"compared_run_{i + 1}"] = ctx.alias("run", run_id)
    latest = runs.runs.latest_succeeded(ctx.workspace_id)
    if latest is not None:
        out["latest_succeeded_run"] = ctx.alias("run", latest.id)
        out["latest_succeeded_run_label"] = latest.label or ""
    return ToolResult(out, note="contexte de la page")


class DatasetArgs(ToolArgs):
    dataset_id: str | None = Field(default=None, max_length=64, description="Alias (d1) or id; omit for the dataset on screen")


@tool(
    "get_dataset",
    "Input data of a dataset version: producer, crops, harvest lots, buyers (price, demand, constraints), "
    "storage facilities, vehicles and routes.",
    DatasetArgs,
)
def get_dataset(ctx: ToolContext, args: DatasetArgs) -> ToolResult:
    dataset, version = resolve_dataset(ctx, args.dataset_id)
    payload = DatasetPayload.model_validate(version.payload)
    if payload.currency:
        ctx.currency = payload.currency
    alias = ctx.alias("dataset", dataset.id)
    data = payload.model_dump(mode="json", exclude={"schema_version"})
    out = {f"{alias}.name": dataset.name, f"{alias}.version_no": version.version_no}
    out.update(facts(ctx, alias, data, limit=260))
    return ToolResult(out, note=f"données {alias} v{version.version_no}")


class MarketArgs(DatasetArgs):
    crop_id: str | None = Field(default=None, max_length=64)


@tool(
    "get_market_analysis",
    "Buyers ranked by estimated net price per kg (price minus transport) before any optimization, "
    "with reachability. Use it to compare outlets.",
    MarketArgs,
)
def get_market_analysis(ctx: ToolContext, args: MarketArgs) -> ToolResult:
    dataset, version = resolve_dataset(ctx, args.dataset_id)
    market = AnalyticsService(ctx.session, workspace_id=ctx.workspace_id).market(dataset.id, version_no=version.version_no, crop_id=args.crop_id)
    alias = ctx.alias("dataset", dataset.id)
    return ToolResult(facts(ctx, f"{alias}.market", market.model_dump(mode="json")), note=f"marché {alias}")


@tool(
    "list_change_ops",
    "Catalogue of scenario operations (op, target kind, params schema). Read it before proposing a scenario.",
    NoArgs,
)
def list_change_ops(ctx: ToolContext, _args: NoArgs) -> ToolResult:
    out: dict[str, Any] = {}
    for op, change_type in CHANGE_TYPES.items():
        schema = change_type.model_fields["params"].annotation.model_json_schema()  # type: ignore[union-attr]
        out[f"op.{op}.description"] = OPERATIONS[op].description
        out[f"op.{op}.target"] = change_type.target_kind
        out[f"op.{op}.params"] = _compact_schema(schema)
    out["note"] = "target: entity id, '*' for all (one_or_all), or null (none). Numeric params use {mode: absolute|relative_pct|delta, value}."
    return ToolResult(out, note="catalogue des opérations")


def _compact_schema(schema: dict[str, Any]) -> str:
    """`field: type/enum` summary, short enough for the context window."""
    defs = schema.get("$defs", {})
    parts = []
    for name, prop in schema.get("properties", {}).items():
        ref = prop.get("$ref") or next((o.get("$ref") for o in prop.get("anyOf", []) if "$ref" in o), None)
        target = defs.get(ref.split("/")[-1], {}) if ref else prop
        kind = "|".join(map(str, target["enum"])) if "enum" in target else target.get("type") or "object"
        if "anyOf" in prop and not ref:
            kind = "|".join(str(o.get("type", "")) for o in prop["anyOf"])
        parts.append(f"{name}{'' if name in schema.get('required', []) else '?'}: {kind}")
    return "{" + ", ".join(parts) + "}"

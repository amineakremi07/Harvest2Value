"""Read-only analytics tools: buyers, logistics, crop."""

from __future__ import annotations

from ...services.analytics import AnalyticsService
from .common import RunArg, resolve_run
from .registry import ToolContext, ToolResult, facts, tool


def _service(ctx: ToolContext) -> AnalyticsService:
    return AnalyticsService(ctx.session, workspace_id=ctx.workspace_id)


@tool(
    "get_buyer_analysis",
    "Per buyer: list price, sold kg, share of sales, fulfillment, revenue, transport cost, net revenue, "
    "net and estimated net price per kg, market rank, distance.",
    RunArg,
)
def get_buyer_analysis(ctx: ToolContext, args: RunArg) -> ToolResult:
    run = resolve_run(ctx, args.run_id)
    alias = ctx.alias("run", run.id)
    section = _service(ctx).buyers(run.id).model_dump(mode="json", exclude={"run_id"})
    for b in section["buyers"]:
        b.pop("served_days", None)
    return ToolResult(facts(ctx, f"{alias}.buyer_analysis", section), note=f"acheteurs {alias}")


@tool(
    "get_logistics_analysis",
    "Trips, transport cost per trip and per kg, load factor, fleet hours and utilization per vehicle type, routes.",
    RunArg,
)
def get_logistics_analysis(ctx: ToolContext, args: RunArg) -> ToolResult:
    run = resolve_run(ctx, args.run_id)
    alias = ctx.alias("run", run.id)
    section = _service(ctx).logistics(run.id).model_dump(mode="json", exclude={"run_id", "daily"})
    for v in section["vehicles"]:
        v.pop("binding_days", None)
    return ToolResult(facts(ctx, f"{alias}.logistics", section), note=f"logistique {alias}")


@tool(
    "get_crop_analysis",
    "Crop perishability: shelf life, quality decay, loss rates, risk level and reasons, outcome of each harvest lot.",
    RunArg,
)
def get_crop_analysis(ctx: ToolContext, args: RunArg) -> ToolResult:
    run = resolve_run(ctx, args.run_id)
    alias = ctx.alias("run", run.id)
    section = _service(ctx).crops(run.id).model_dump(mode="json", exclude={"run_id", "value_curve"})
    return ToolResult(facts(ctx, f"{alias}.crop", section), note=f"culture {alias}")

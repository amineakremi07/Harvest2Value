"""Read-only tools about one optimization run: KPIs, allocations, constraints, explanations, alerts."""

from __future__ import annotations

from collections import defaultdict
from typing import Any

from pydantic import Field

from ...services.explanation import ExplanationService
from ...services.insights import InsightService
from .common import RunArg, resolve_run, runs_service
from .registry import ToolContext, ToolFailure, ToolResult, dump, facts, tool

KPI_KEYS = (
    "harvest_kg", "sold_kg", "realized_revenue", "transport_cost", "storage_cost", "disposal_cost", "total_cost",
    "realized_profit", "margin_pct", "ending_inventory_kg", "ending_inventory_value", "economic_value", "lost_kg",
    "lost_value", "waste_rate_pct", "sold_rate_pct", "storage_rate_pct", "fulfillment_rate_pct",
    "vehicle_utilization_pct", "load_factor_pct", "trips", "avg_transport_cost_per_kg",
)


@tool(
    "get_run",
    "Status, configuration and KPIs of an optimization run (realized profit, revenue, costs, sold, lost, "
    "waste rate, fulfillment, trips). Realized profit and economic value are different: never mix them.",
    RunArg,
)
def get_run(ctx: ToolContext, args: RunArg) -> ToolResult:
    run = resolve_run(ctx, args.run_id, require_result=False)
    alias = ctx.alias("run", run.id)
    out: dict[str, Any] = {
        f"{alias}.status": run.status,
        f"{alias}.label": run.label or "",
        f"{alias}.objective": run.config.get("objective", "profit"),
        f"{alias}.dataset": ctx.alias("dataset", run.dataset_id),
    }
    if run.scenario_id:
        out[f"{alias}.scenario"] = ctx.alias("scenario", run.scenario_id)
    if run.status == "succeeded":
        result = runs_service(ctx).result(run.id)
        kpis = result.kpis.model_dump(mode="json")
        out.update(facts(ctx, f"{alias}.kpis", {k: kpis[k] for k in KPI_KEYS if kpis.get(k) is not None}))
        out[f"{alias}.outcome"] = result.outcome_label
        out.update(facts(ctx, f"{alias}", {"horizon_days": result.horizon_days}))
    elif run.diagnostics:
        out.update(facts(ctx, f"{alias}.diagnostics", run.diagnostics))
    return ToolResult(out, note=f"exécution {alias}")


class AllocationArgs(RunArg):
    buyer_id: str | None = Field(default=None, max_length=64, description="Only this buyer")


@tool(
    "get_allocations",
    "Sold kg per buyer and delivery day (aggregated over lots), with the storage they came from.",
    AllocationArgs,
)
def get_allocations(ctx: ToolContext, args: AllocationArgs) -> ToolResult:
    run = resolve_run(ctx, args.run_id)
    alias = ctx.alias("run", run.id)
    result = runs_service(ctx).result(run.id)
    rows: dict[tuple[str, int], dict[str, Any]] = defaultdict(lambda: {"kg": 0.0, "revenue": 0.0, "from_storage_kg": 0.0})
    for a in result.allocations:
        if args.buyer_id and a.buyer_id != args.buyer_id:
            continue
        row = rows[(a.buyer_id, a.day)]
        row["kg"] += a.kg
        row["revenue"] += a.revenue
        if a.facility_id:
            row["from_storage_kg"] += a.kg
    names = {b.buyer_id: b.buyer_name for b in result.buyers}
    data = {
        buyer: {"buyer_name": names.get(buyer, buyer), **{f"day{day}": {k: round(v, 2) for k, v in row.items()} for (b, day), row in sorted(rows.items()) if b == buyer}}
        for buyer in sorted({b for b, _ in rows})
    }
    if not data:
        raise ToolFailure("No allocation matches (unknown buyer or nothing sold).")
    return ToolResult(facts(ctx, f"{alias}.allocations", data), note=f"allocations {alias}")


class ConstraintArgs(RunArg):
    family: str | None = Field(default=None, max_length=40, description="e.g. demand_day, storage_capacity, fleet_time")


@tool("get_constraints", "Binding constraints of the plan (the limits that are reached), optionally one family.", ConstraintArgs)
def get_constraints(ctx: ToolContext, args: ConstraintArgs) -> ToolResult:
    run = resolve_run(ctx, args.run_id)
    alias = ctx.alias("run", run.id)
    rows = ExplanationService(ctx.session, workspace_id=ctx.workspace_id).constraints(run.id, binding_only=True)
    rows = [c for c in rows if not args.family or c.family == args.family][:30]
    data = [{"key": c.key.replace("|", "_"), "label": c.label, "family": c.family, "value": c.lhs, "limit": c.rhs} for c in rows]
    return ToolResult(facts(ctx, f"{alias}.binding", data), note=f"{len(data)} contraintes saturées")


@tool(
    "get_bottlenecks",
    "Ranked bottlenecks (binding limits grouped over days) with the suggested relaxation, the measured "
    "gain of relaxing it (probe, if computed) and the dual value (local indicator only).",
    RunArg,
)
def get_bottlenecks(ctx: ToolContext, args: RunArg) -> ToolResult:
    run = resolve_run(ctx, args.run_id)
    alias = ctx.alias("run", run.id)
    items = ExplanationService(ctx.session, workspace_id=ctx.workspace_id).bottlenecks(run.id)[:8]
    data = [
        {
            "key": b.key.replace("|", "_").strip("_"),
            "rank": b.rank,
            "label": b.label,
            "suggestion": b.suggested_label or "",
            "measured_gain": b.probe_gain,
            "dual_local_indicator": b.dual,
        }
        for b in items
    ]
    return ToolResult(facts(ctx, f"{alias}.bottlenecks", data), note=f"{len(data)} goulots")


class DecisionArgs(RunArg):
    entity_id: str = Field(max_length=64, description="Buyer id, storage facility id, or 'waste'")


@tool(
    "explain_decision",
    "Why a buyer received what it received and why not more (limiting factor), best alternative, and "
    "marginal values (measured effect first; dual = local indicator). Also works for a storage facility or 'waste'.",
    DecisionArgs,
)
def explain_decision(ctx: ToolContext, args: DecisionArgs) -> ToolResult:
    run = resolve_run(ctx, args.run_id)
    alias = ctx.alias("run", run.id)
    explanation = ExplanationService(ctx.session, workspace_id=ctx.workspace_id).explanation(run.id)
    card = next((c for c in explanation.decisions if c.entity_id == args.entity_id or c.name.lower() == args.entity_id.lower()), None)
    if card is None:
        known = ", ".join(c.entity_id for c in explanation.decisions)
        raise ToolFailure(f"Unknown entity '{args.entity_id}'. Known: {known}.")
    data = dump(card)
    data["marginal_values"] = [{**mv, "id": f"{mv['kind']}{i}"} for i, mv in enumerate(data.get("marginal_values", []))]
    return ToolResult(facts(ctx, f"{alias}.decision.{card.entity_id}", data), note=f"décision {card.name}")


@tool("get_insights", "Deterministic alerts and opportunities of the run, most severe first, with evidence.", RunArg)
def get_insights(ctx: ToolContext, args: RunArg) -> ToolResult:
    run = resolve_run(ctx, args.run_id)
    alias = ctx.alias("run", run.id)
    views = InsightService(ctx.session, workspace_id=ctx.workspace_id).list(run.id)[:8]
    data = [
        {
            "id": v.rule_id.lower(),
            "severity": v.severity,
            "category": v.category,
            "message": v.message,
            "evidence": {m.key: m.value for m in v.evidence.metrics if isinstance(m.value, (int, float))},
            "has_suggested_change": bool(v.suggested_changes),
        }
        for v in views
    ]
    return ToolResult(facts(ctx, f"{alias}.insights", data), note=f"{len(data)} alertes")

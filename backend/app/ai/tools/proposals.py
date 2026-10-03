"""Proposal tools: they never write. Each creates a *pending* copilot action that the user must
confirm in the UI (with an expiry and an idempotency key). Before proposing:

- R6: the user's message must ask for a change; a question — even one containing a number — never
  produces a proposal;
- every number in the proposal must come from the user or from backend data (no invented values);
- the changes are validated by applying them (preview) so the user confirms something that works.
"""

from __future__ import annotations

from typing import Any

from pydantic import Field, ValidationError

from ...domain.enums import ObjectiveKind
from ...domain.report import REPORT_SECTIONS, ReportSection, ReportSpec
from ...domain.run_config import RunConfig
from ...services.scenarios import ScenarioService
from ..guards import numeric_params, ungrounded_numbers
from .common import resolve_dataset, resolve_run, runs_service
from .registry import ProposedAction, ToolArgs, ToolContext, ToolFailure, ToolResult, tool
from .scenarios import ScenarioBaseArgs, parse_changes, preview_changes, preview_facts


def _require_intent(ctx: ToolContext) -> None:
    if not ctx.asks_for_change:
        raise ToolFailure(
            "The user did not ask for a change: answer the question only. Do not propose scenarios, runs or "
            "reports unless the user explicitly asks to create, simulate, run or generate one."
        )


def _require_grounded(ctx: ToolContext, values: list[float], what: str) -> None:
    missing = ungrounded_numbers(values, [*ctx.user_numbers, *ctx.refs.numbers()])
    if missing:
        listed = ", ".join(f"{v:g}" for v in missing)
        raise ToolFailure(f"The value(s) {listed} in {what} were not given by the user nor found in the data. Ask the user for them.")


class CreateScenarioArgs(ScenarioBaseArgs):
    name: str = Field(min_length=1, max_length=120)


@tool(
    "create_scenario",
    "PROPOSES a new scenario (base dataset or parent scenario + typed changes). Nothing is saved until "
    "the user confirms the proposal in the interface. Only when the user asks for it.",
    CreateScenarioArgs,
    kind="proposal",
)
def create_scenario(ctx: ToolContext, args: CreateScenarioArgs) -> ToolResult:
    _require_intent(ctx)
    changes = parse_changes(args.changes)
    _require_grounded(ctx, [v for c in args.changes for v in numeric_params(c.params)], "the changes")
    preview, dataset_id, parent_id = preview_changes(ctx, args, changes)
    if preview.validation.errors:
        raise ToolFailure("The resulting data would be invalid: " + "; ".join(e.message for e in preview.validation.errors[:3]))
    summaries = [a.summary for a in preview.applied[-len(changes) :]]
    payload = {
        "name": args.name,
        "dataset_id": None if parent_id else dataset_id,
        "version_no": None if parent_id else preview.base_version.version_no,
        "parent_id": parent_id,
        "changes": [c.model_dump(mode="json") for c in changes],
    }
    ctx.actions.append(ProposedAction("create_scenario", payload, f"Créer le scénario « {args.name} » : " + " ; ".join(summaries)))
    out: dict[str, Any] = {"proposal.status": "pending_user_confirmation", "proposal.kind": "create_scenario", "proposal.name": args.name}
    out.update(preview_facts(ctx, "proposal", preview))
    return ToolResult(out, note="scénario proposé (à confirmer)")


class RunOptimizationArgs(ToolArgs):
    dataset_id: str | None = Field(default=None, max_length=64)
    scenario_id: str | None = Field(default=None, max_length=64, description="Optimize this scenario's data")
    objective: ObjectiveKind = ObjectiveKind.PROFIT
    horizon_days: int | None = Field(default=None, ge=1, le=60)
    label: str | None = Field(default=None, max_length=120)


@tool(
    "run_optimization",
    "PROPOSES to run the optimizer on a dataset or a scenario. The run starts only after the user confirms. "
    "Only when the user asks for it.",
    RunOptimizationArgs,
    kind="proposal",
)
def run_optimization(ctx: ToolContext, args: RunOptimizationArgs) -> ToolResult:
    _require_intent(ctx)
    if args.horizon_days is not None:
        _require_grounded(ctx, [float(args.horizon_days)], "the horizon")
    try:
        config = RunConfig(objective=args.objective, horizon_days=args.horizon_days)
    except ValidationError as exc:
        raise ToolFailure(f"Invalid configuration: {exc.errors(include_url=False)[0]['msg']}") from exc
    scenario_id = ctx.resolve("scenario", args.scenario_id) if args.scenario_id else None
    if scenario_id:
        scenario = ScenarioService(ctx.session, workspace_id=ctx.workspace_id).get(scenario_id)
        target = f"le scénario « {scenario.name} »"
        payload: dict[str, Any] = {"scenario_id": scenario.id, "dataset_id": None}
        ctx.alias("scenario", scenario.id)
    else:
        dataset, version = resolve_dataset(ctx, args.dataset_id)
        target = f"les données « {dataset.name} » v{version.version_no}"
        payload = {"scenario_id": None, "dataset_id": dataset.id}
    payload.update({"config": config.model_dump(mode="json"), "label": args.label})
    ctx.actions.append(ProposedAction("run_optimization", payload, f"Optimiser {target} (objectif {args.objective.value})"))
    return ToolResult({"proposal.status": "pending_user_confirmation", "proposal.kind": "run_optimization", "proposal.target": target}, note="exécution proposée (à confirmer)")


class GenerateReportArgs(ToolArgs):
    title: str = Field(min_length=1, max_length=160)
    run_id: str | None = Field(default=None, max_length=64, description="Main run (alias or id); omit for the run on screen")
    compare_run_ids: list[str] = Field(default_factory=list, max_length=3)
    sections: list[ReportSection] = Field(default_factory=lambda: ["summary", "financial", "buyers", "insights"], description=f"Among {', '.join(REPORT_SECTIONS)}")
    include_narrative: bool = False


@tool(
    "generate_report",
    "PROPOSES a frozen report (snapshot of the chosen sections) for a run, optionally compared with other "
    "runs. Created only after the user confirms. Only when the user asks for a report.",
    GenerateReportArgs,
    kind="proposal",
)
def generate_report(ctx: ToolContext, args: GenerateReportArgs) -> ToolResult:
    _require_intent(ctx)
    run = resolve_run(ctx, args.run_id)
    others = [resolve_run(ctx, r) for r in args.compare_run_ids]
    sections = list(args.sections)
    if others and "comparison" not in sections:
        sections.append("comparison")
    try:
        spec = ReportSpec(title=args.title, run_id=run.id, compare_run_ids=[r.id for r in others], sections=sections, include_narrative=args.include_narrative)
    except ValidationError as exc:
        raise ToolFailure(f"Invalid report: {exc.errors(include_url=False)[0]['msg']}") from exc
    runs_service(ctx).result(run.id)  # the main run must have a plan
    ctx.actions.append(ProposedAction("generate_report", spec.model_dump(mode="json"), f"Générer le rapport « {args.title} » ({', '.join(sections)})"))
    return ToolResult({"proposal.status": "pending_user_confirmation", "proposal.kind": "generate_report", "proposal.title": args.title}, note="rapport proposé (à confirmer)")

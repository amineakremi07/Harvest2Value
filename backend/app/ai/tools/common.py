"""Entity resolution shared by the tools: aliases or ids, falling back to the page context."""

from __future__ import annotations

from pydantic import Field

from ...db.models import Dataset, DatasetVersion, OptimizationRun
from ...domain.enums import RunStatus
from ...services.datasets import DatasetService
from ...services.optimization import OptimizationService
from .registry import ToolArgs, ToolContext, ToolFailure

IdField = Field(default=None, max_length=64, description="Alias such as r1 (see get_context) or full id; omit for the run on screen")


class RunArg(ToolArgs):
    run_id: str | None = IdField


def runs_service(ctx: ToolContext) -> OptimizationService:
    return OptimizationService(ctx.session, workspace_id=ctx.workspace_id)


def resolve_run(ctx: ToolContext, run_id: str | None, *, require_result: bool = True) -> OptimizationRun:
    service = runs_service(ctx)
    resolved = ctx.resolve("run", run_id) or ctx.page.run_id
    if resolved is None:
        latest = service.runs.latest_succeeded(ctx.workspace_id)
        if latest is None:
            raise ToolFailure("No optimization run exists yet. Suggest the user to launch one from the Optimize page.")
        resolved = latest.id
    run = service.get(resolved)
    if require_result and run.status != RunStatus.SUCCEEDED:
        raise ToolFailure(f"Run {ctx.alias('run', run.id)} has status '{run.status}': it has no plan to analyze.")
    ctx.alias("run", run.id)
    if run.dataset_id:
        ctx.alias("dataset", run.dataset_id)
    return run


def resolve_dataset(ctx: ToolContext, dataset_id: str | None) -> tuple[Dataset, DatasetVersion]:
    resolved = ctx.resolve("dataset", dataset_id) or ctx.page.dataset_id
    if resolved is None and ctx.page.run_id:
        resolved = runs_service(ctx).get(ctx.page.run_id).dataset_id
    if resolved is None:
        latest = runs_service(ctx).runs.latest_succeeded(ctx.workspace_id)
        if latest is None:
            raise ToolFailure("No dataset is selected. Ask the user which dataset to use.")
        resolved = latest.dataset_id
    bundle = DatasetService(ctx.session, workspace_id=ctx.workspace_id).get(resolved)
    ctx.alias("dataset", bundle.dataset.id)
    return bundle.dataset, bundle.version

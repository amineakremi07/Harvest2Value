"""Optimization runs: creation (effective input, hashes, cache), background execution,
results, cancellation, on-demand sensitivity (probes) and startup recovery.

`create_run` works in the caller's transaction; `execute_run` and `compute_sensitivity` run in a
worker thread and open their own short transactions (SQLite: never hold a write lock while CBC runs).
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Any

from pydantic import ValidationError
from sqlalchemy.orm import Session, sessionmaker

from ..analytics.context import RunContext
from ..core.errors import AppError, Conflict, NotFound, ScenarioApplyError, ValidationFailed
from ..core.hashing import sha256_of
from ..db.base import utcnow
from ..db.models import DEFAULT_WORKSPACE_ID, DatasetVersion, OptimizationResult, OptimizationRun, Scenario
from ..db.session import unit_of_work
from ..domain.dataset import DatasetPayload
from ..domain.enums import ObjectiveKind, RunStatus, ScenarioStatus, SolverOutcome
from ..domain.results import (
    AllocationRow,
    BuyerSummary,
    ConstraintInfo,
    Diagnostics,
    InventoryRow,
    Kpis,
    OptimizationResultModel,
    SensitivityReport,
    TripRow,
    WasteRow,
)
from ..domain.run_config import RunConfig
from ..domain.scenario import AppliedChange, parse_change
from ..domain.validation import validate_business
from ..explain.binding import bottlenecks, shelf_life_relaxation
from ..optimization.diagnostics import elastic_infeasibility
from ..optimization.engine import OptimizationEngine
from ..optimization.instance import build_instance
from ..optimization.sensitivity import MAX_PROBES, ProbeCandidate, fixed_lp_duals, probe
from ..repositories.datasets import DatasetRepository
from ..repositories.runs import RunRepository
from ..scenarios.apply import apply_changes
from .insights import InsightService
from .scenarios import ScenarioService

logger = logging.getLogger(__name__)

TERMINAL = frozenset(
    {RunStatus.SUCCEEDED, RunStatus.INFEASIBLE, RunStatus.TIMEOUT, RunStatus.FAILED, RunStatus.CANCELLED, RunStatus.INTERRUPTED}
)
SAFE_ERROR_MESSAGES = {
    "INTERNAL_ERROR": "The run failed unexpectedly. Quote the run id if you report it.",
    "ENGINE_INVARIANT": "The optimization result failed an internal consistency check.",
}


@dataclass
class CreatedRun:
    run: OptimizationRun
    cache_hit: bool


@dataclass
class ResolvedInput:
    dataset_id: str
    version: DatasetVersion
    scenario: Scenario | None
    payload: DatasetPayload
    applied: list[AppliedChange]


def safe_error_message(run: OptimizationRun) -> str | None:
    if run.error_code is None:
        return None
    return SAFE_ERROR_MESSAGES.get(run.error_code, run.error_message)


def result_model(run: OptimizationRun, row: OptimizationResult) -> OptimizationResultModel:
    return OptimizationResultModel(
        outcome=SolverOutcome(run.solver_outcome or SolverOutcome.ERROR),
        **row.meta,
        kpis=Kpis.model_validate(row.kpis),
        buyers=[BuyerSummary.model_validate(b) for b in row.buyers],
        allocations=[AllocationRow.model_validate(a) for a in row.allocations],
        inventory=[InventoryRow.model_validate(i) for i in row.inventory],
        trips=[TripRow.model_validate(t) for t in row.trips],
        waste=[WasteRow.model_validate(w) for w in row.waste],
        constraints=[ConstraintInfo.model_validate(c) for c in row.constraints],
        warnings=list(row.warnings),
        sensitivity=SensitivityReport.model_validate(row.sensitivity) if row.sensitivity else None,
    )


class OptimizationService:
    def __init__(self, session: Session, *, workspace_id: str = DEFAULT_WORKSPACE_ID) -> None:
        self.session = session
        self.runs = RunRepository(session)
        self.datasets = DatasetRepository(session)
        self.workspace_id = workspace_id

    # ---- create ----

    def resolve_input(self, *, dataset_id: str | None, version_no: int | None, scenario_id: str | None) -> ResolvedInput:
        """Effective data = dataset version, or a scenario's base version + its change chain."""
        if scenario_id is not None:
            scenarios = ScenarioService(self.session, workspace_id=self.workspace_id)
            scenario = scenarios.get(scenario_id)
            if dataset_id is not None and dataset_id != scenario.dataset_id:
                raise ValidationFailed("scenario_id belongs to another dataset.", code="SCENARIO_DATASET_MISMATCH")
            if version_no is not None:
                raise ValidationFailed("version_no cannot be combined with scenario_id (the scenario fixes its base version).")
            version = scenarios.base_version(scenario)
            applied = scenarios.effective_input(scenario, base=version)
            return ResolvedInput(scenario.dataset_id, version, scenario, applied.effective, applied.applied)

        if dataset_id is None:
            raise ValidationFailed("Provide dataset_id or scenario_id.")
        dataset = self.datasets.get(dataset_id, self.workspace_id)
        if dataset is None:
            raise NotFound(f"Dataset '{dataset_id}' does not exist.", details={"dataset_id": dataset_id})
        found: DatasetVersion | None
        if version_no is None:
            found = self.datasets.get_version_by_id(dataset.current_version_id) if dataset.current_version_id else None
        else:
            found = self.datasets.get_version(dataset_id, version_no)
        if found is None:
            raise NotFound(f"Version {version_no} of dataset '{dataset_id}' does not exist.", details={"version_no": version_no})
        return ResolvedInput(dataset_id, found, None, DatasetPayload.model_validate(found.payload), [])

    def create_run(
        self,
        *,
        dataset_id: str | None,
        version_no: int | None = None,
        scenario_id: str | None = None,
        config: RunConfig,
        label: str | None = None,
        use_cache: bool = True,
    ) -> CreatedRun:
        resolved = self.resolve_input(dataset_id=dataset_id, version_no=version_no, scenario_id=scenario_id)
        return self._create(resolved, config, label=label, use_cache=use_cache)

    def _create(self, resolved: ResolvedInput, config: RunConfig, *, label: str | None, use_cache: bool) -> CreatedRun:
        report = validate_business(resolved.payload)
        if not report.is_valid:
            raise ValidationFailed(
                "The data to optimize has blocking errors; fix them before optimizing.",
                code="DATASET_INVALID",
                details={"errors": [e.model_dump() for e in report.errors]},
            )
        build_instance(resolved.payload, config)  # CONFIG_INVALID (crop, horizon) before queueing

        document = resolved.payload.model_dump(mode="json")
        effective_hash = sha256_of(document)
        config_doc = config.model_dump(mode="json")
        config_hash = sha256_of(config_doc)

        if use_cache:
            cached = self.runs.find_cached(self.workspace_id, effective_hash, config_hash)
            if cached is not None:
                if resolved.scenario is not None:
                    resolved.scenario.latest_run_id = cached.id
                    if resolved.scenario.status == ScenarioStatus.DRAFT:
                        resolved.scenario.status = ScenarioStatus.READY
                    self.session.flush()
                return CreatedRun(cached, cache_hit=True)

        run = OptimizationRun(
            workspace_id=self.workspace_id,
            dataset_id=resolved.dataset_id,
            dataset_version_id=resolved.version.id,
            scenario_id=resolved.scenario.id if resolved.scenario else None,
            config=config_doc,
            config_hash=config_hash,
            effective_input_hash=effective_hash,
            effective_input=document,
            applied_changes=[a.model_dump(mode="json") for a in resolved.applied] or None,
            status=RunStatus.QUEUED,
            label=label,
        )
        self.runs.add(run)
        if resolved.scenario is not None:
            resolved.scenario.latest_run_id = run.id
            self.session.flush()
        return CreatedRun(run, cache_hit=False)

    def rerun(self, run_id: str, *, config_overrides: dict[str, Any], label: str | None, use_cache: bool) -> CreatedRun:
        """Same frozen effective input, new configuration."""
        source = self.get(run_id)
        try:
            config = RunConfig.model_validate({**source.config, **config_overrides})
        except ValidationError as e:
            raise ValidationFailed(
                "The configuration overrides are invalid.",
                code="CONFIG_INVALID",
                details={"errors": [{"loc": list(err["loc"]), "msg": err["msg"]} for err in e.errors()]},
            ) from e
        version = self.datasets.get_version_by_id(source.dataset_version_id)
        assert version is not None
        scenario = None
        if source.scenario_id:
            scenario = self.session.get(Scenario, source.scenario_id)
        resolved = ResolvedInput(
            source.dataset_id,
            version,
            scenario,
            DatasetPayload.model_validate(source.effective_input),
            [AppliedChange.model_validate(a) for a in source.applied_changes or []],
        )
        return self._create(resolved, config, label=label or source.label, use_cache=use_cache)

    # ---- read ----

    def get(self, run_id: str) -> OptimizationRun:
        run = self.runs.get(run_id, self.workspace_id)
        if run is None:
            raise NotFound(f"Run '{run_id}' does not exist.", details={"run_id": run_id})
        return run

    def list(
        self, *, dataset_id: str | None, scenario_id: str | None, status: str | None, page: int, page_size: int
    ) -> tuple[list[OptimizationRun], int]:
        return self.runs.list(
            self.workspace_id, dataset_id=dataset_id, scenario_id=scenario_id, status=status, offset=(page - 1) * page_size, limit=page_size
        )

    def require_result(self, run_id: str) -> tuple[OptimizationRun, OptimizationResult]:
        run = self.get(run_id)
        if run.status in (RunStatus.QUEUED, RunStatus.RUNNING):
            raise Conflict("The run has not finished yet.", code="RUN_NOT_FINISHED", details={"status": run.status})
        if run.status == RunStatus.INFEASIBLE:
            raise Conflict(
                "The run is infeasible: no plan satisfies all constraints. See /diagnostics.",
                code="RUN_INFEASIBLE",
                details={"status": run.status, "diagnostics_url": f"/api/v2/runs/{run.id}/diagnostics"},
            )
        row = self.runs.get_result(run.id)
        if run.status != RunStatus.SUCCEEDED or row is None:
            raise Conflict(
                f"The run has no result (status {run.status}).",
                code="RUN_NO_RESULT",
                details={"status": run.status, "error_code": run.error_code},
            )
        return run, row

    def result(self, run_id: str) -> OptimizationResultModel:
        run, row = self.require_result(run_id)
        return result_model(run, row)

    def context(self, run_id: str) -> RunContext:
        run, row = self.require_result(run_id)
        model = result_model(run, row)
        return RunContext.build(
            run.id,
            DatasetPayload.model_validate(run.effective_input),
            RunConfig.model_validate(run.config),
            model,
            model.sensitivity,
        )

    def diagnostics(self, run_id: str) -> Diagnostics:
        run = self.get(run_id)
        if run.status != RunStatus.INFEASIBLE:
            raise Conflict("Diagnostics exist only for infeasible runs.", code="RUN_NOT_INFEASIBLE", details={"status": run.status})
        return Diagnostics.model_validate(run.diagnostics or {"method": "none"})

    # ---- cancel / delete ----

    def cancel(self, run_id: str) -> OptimizationRun:
        run = self.get(run_id)
        if run.status != RunStatus.QUEUED:
            raise Conflict(
                f"Only a queued run can be cancelled (status {run.status}).", code="NOT_CANCELLABLE", details={"status": run.status}
            )
        run.status = RunStatus.CANCELLED
        run.finished_at = utcnow()
        self.session.flush()
        return run

    def delete(self, run_id: str) -> None:
        run = self.get(run_id)
        if run.status == RunStatus.RUNNING:
            raise Conflict("A running run cannot be deleted; wait for it to finish.", code="RUN_RUNNING")
        self.runs.delete(run)

    def recover_interrupted(self) -> int:
        return self.runs.mark_unfinished_interrupted()


# ---------------------------------------------------------------- background work


def _finish(factory: sessionmaker[Session], run_id: str, **fields: Any) -> OptimizationRun | None:
    with unit_of_work(factory) as session:
        run = session.get(OptimizationRun, run_id)
        if run is None:
            return None
        for key, value in fields.items():
            setattr(run, key, value)
        run.finished_at = utcnow()
        return run


def _with_duals(
    engine: OptimizationEngine, payload: DatasetPayload, config: RunConfig, result: OptimizationResultModel
) -> tuple[OptimizationResultModel, SensitivityReport]:
    """Method 1 (fixed-integer LP duals) is cheap: computed for every succeeded run."""
    if config.objective == ObjectiveKind.WEIGHTED:
        return result, SensitivityReport(duals_available=False)
    try:
        duals = fixed_lp_duals(engine, payload, config, result, time_limit_s=config.time_limit_s or engine.default_time_limit_s)
    except Exception:  # never lose a solved plan because of the dual computation
        logger.exception("Dual computation failed")
        return result, SensitivityReport(duals_available=False)
    constraints = [
        c.model_copy(update={"dual": duals.by_key[c.key].value, "dual_reliable": duals.by_key[c.key].reliable})
        if c.key in duals.by_key
        else c
        for c in result.constraints
    ]
    report = SensitivityReport(duals=duals.duals, duals_available=duals.available)
    return result.model_copy(update={"constraints": constraints, "sensitivity": report}), report


def execute_run(factory: sessionmaker[Session], engine: OptimizationEngine, run_id: str) -> None:
    """Background job: queued -> running -> succeeded | infeasible | timeout | failed."""
    with unit_of_work(factory) as session:
        run = session.get(OptimizationRun, run_id)
        if run is None or run.status != RunStatus.QUEUED:
            return  # cancelled or deleted while waiting
        run.status = RunStatus.RUNNING
        run.started_at = utcnow()
        payload_doc, config_doc = run.effective_input, run.config

    try:
        payload = DatasetPayload.model_validate(payload_doc)
        config = RunConfig.model_validate(config_doc)
        output = engine.run(payload, config)
    except AppError as e:
        _finish(factory, run_id, status=RunStatus.FAILED, solver_outcome=SolverOutcome.ERROR, error_code=e.code, error_message=e.message)
        return
    except Exception as e:
        logger.exception("Run failed", extra={"run_id": run_id})
        _finish(factory, run_id, status=RunStatus.FAILED, solver_outcome=SolverOutcome.ERROR, error_code="INTERNAL_ERROR", error_message=repr(e))
        return

    common = {"solver_outcome": output.outcome, "solve_seconds": round(output.solve_seconds, 3), "warnings": output.warnings}
    if output.result is not None:
        _store_success(factory, engine, run_id, payload, config, output.result, common)
    elif output.outcome == SolverOutcome.INFEASIBLE:
        try:
            diagnostics = elastic_infeasibility(payload, config, runner=engine.runner, time_limit_s=config.time_limit_s or engine.default_time_limit_s)
        except Exception:
            logger.exception("Diagnostics failed", extra={"run_id": run_id})
            diagnostics = Diagnostics(method="none", suggestions=["Diagnostics could not be computed."])
        _finish(factory, run_id, status=RunStatus.INFEASIBLE, diagnostics=diagnostics.model_dump(mode="json"), **common)
    elif output.outcome == SolverOutcome.NOT_SOLVED:
        _finish(
            factory, run_id, status=RunStatus.TIMEOUT, error_code="SOLVER_TIMEOUT",
            error_message="No plan was found within the time limit; raise time_limit_s or simplify the problem.", **common,
        )
    else:
        _finish(
            factory, run_id, status=RunStatus.FAILED, error_code="SOLVER_ERROR",
            error_message=f"The solver stopped with outcome '{output.outcome}'.", **common,
        )


def _store_success(
    factory: sessionmaker[Session],
    engine: OptimizationEngine,
    run_id: str,
    payload: DatasetPayload,
    config: RunConfig,
    result: OptimizationResultModel,
    common: dict[str, Any],
) -> None:
    result, sensitivity = _with_duals(engine, payload, config, result)
    ctx = RunContext.build(run_id, payload, config, result, sensitivity)
    with unit_of_work(factory) as session:
        run = session.get(OptimizationRun, run_id)
        if run is None:
            return
        run.status = RunStatus.SUCCEEDED
        run.mip_gap = result.gap_requested if result.outcome == SolverOutcome.OPTIMAL else None
        run.finished_at = utcnow()
        for key, value in common.items():
            setattr(run, key, value)
        session.add(
            OptimizationResult(
                run_id=run_id,
                meta={
                    "outcome_label": result.outcome_label,
                    "gap_requested": result.gap_requested,
                    "objective": result.objective,
                    "crop_id": result.crop_id,
                    "horizon_days": result.horizon_days,
                    "solve_seconds": result.solve_seconds,
                },
                kpis=result.kpis.model_dump(mode="json"),
                buyers=[b.model_dump(mode="json") for b in result.buyers],
                allocations=[a.model_dump(mode="json") for a in result.allocations],
                inventory=[i.model_dump(mode="json") for i in result.inventory],
                trips=[t.model_dump(mode="json") for t in result.trips],
                waste=[w.model_dump(mode="json") for w in result.waste],
                constraints=[c.model_dump(mode="json") for c in result.constraints],
                warnings=list(result.warnings),
                sensitivity=sensitivity.model_dump(mode="json"),
            )
        )
        InsightService(session).regenerate(ctx)
        if run.scenario_id:
            scenario = session.get(Scenario, run.scenario_id)
            if scenario is not None and scenario.status == ScenarioStatus.DRAFT:
                scenario.status = ScenarioStatus.READY


def probe_candidates(ctx: RunContext) -> list[ProbeCandidate]:
    """One real scenario change per top bottleneck (+ shelf life when stock expired), at most MAX_PROBES."""
    wanted: list[tuple[str, dict[str, Any], str | None]] = [
        (b.suggested_label or b.label, b.suggested_change, b.key) for b in bottlenecks(ctx) if b.suggested_change is not None
    ]
    shelf = shelf_life_relaxation(ctx)
    if shelf is not None:
        wanted.append((shelf.label, shelf.change, None))

    candidates: list[ProbeCandidate] = []
    seen: set[str] = set()
    for label, change, key in wanted:
        signature = sha256_of(change)
        if signature in seen:
            continue  # fleet_time and fleet_trips of one vehicle type -> the same "+1 vehicle"
        seen.add(signature)
        try:
            applied = apply_changes(ctx.payload, [parse_change(change)])
        except ScenarioApplyError:
            continue
        candidates.append(ProbeCandidate(label=label, change=change, payload=applied.effective, constraint_key=key))
        if len(candidates) >= MAX_PROBES:
            break
    return candidates


def compute_sensitivity(factory: sessionmaker[Session], engine: OptimizationEngine, run_id: str) -> None:
    """Background job: probes for the top bottlenecks, then refresh explanation cache and insights."""
    with unit_of_work(factory) as session:
        ctx = OptimizationService(session).context(run_id)
    report = ctx.sensitivity or SensitivityReport()
    probes = probe(engine, ctx.config, ctx.result, probe_candidates(ctx))
    report = report.model_copy(update={"probes": probes, "probes_computed": True, "probe_gap": ctx.result.gap_requested})
    ctx = RunContext.build(run_id, ctx.payload, ctx.config, ctx.result.model_copy(update={"sensitivity": report}), report)
    with unit_of_work(factory) as session:
        row = RunRepository(session).get_result(run_id)
        if row is None:
            return
        row.sensitivity = report.model_dump(mode="json")
        row.explanation = None  # rebuilt with the probes on next read
        InsightService(session).regenerate(ctx)


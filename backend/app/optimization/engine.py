"""OptimizationEngine: the single entry point `run(payload, config) -> EngineOutput`.

Validation -> ProblemInstance -> ModelBuilder (constraints + objective) -> SolverRunner
-> postprocess. The weighted mode first solves one single-criterion model per weighted
criterion (payoff table) to normalize the criteria.
"""

from __future__ import annotations

from dataclasses import dataclass, field

import anyio.to_thread
from pulp import value

from ..core.errors import ValidationFailed
from ..domain.dataset import DatasetPayload
from ..domain.enums import ObjectiveKind, SolverOutcome
from ..domain.results import OptimizationResultModel
from ..domain.run_config import RunConfig
from ..domain.validation import validate_business
from .builder import BuiltModel, ModelBuilder
from .instance import ProblemInstance, build_instance
from .objectives import CRITERIA, Criterion, CriterionBounds, ideal_points, weighted_criteria
from .postprocess import extract
from .runner import SolverRunner


@dataclass(frozen=True)
class EngineOutput:
    outcome: SolverOutcome
    result: OptimizationResultModel | None  # only when the solver found a solution
    warnings: list[str] = field(default_factory=list)
    solve_seconds: float = 0.0
    horizon_days: int | None = None


class OptimizationEngine:
    def __init__(
        self,
        runner: SolverRunner | None = None,
        builder: ModelBuilder | None = None,
        default_time_limit_s: int = 30,
    ) -> None:
        self.runner = runner or SolverRunner()
        self.builder = builder or ModelBuilder()
        self.default_time_limit_s = default_time_limit_s

    def run(self, payload: DatasetPayload, config: RunConfig) -> EngineOutput:
        report = validate_business(payload)
        if not report.is_valid:
            raise ValidationFailed(
                "The dataset has blocking errors; fix them before optimizing.",
                code="DATASET_INVALID",
                details={"errors": [e.model_dump() for e in report.errors]},
            )
        inst = build_instance(payload, config)
        time_limit = config.time_limit_s or self.default_time_limit_s

        bounds: dict[Criterion, CriterionBounds] | None = None
        spent = 0.0
        if config.objective == ObjectiveKind.WEIGHTED:
            bounds, spent, failed = self._payoff_bounds(inst, config, time_limit)
            if failed is not None:
                return EngineOutput(failed, None, list(inst.warnings), spent, inst.horizon)

        built = self.builder.build(inst, config, bounds=bounds)
        raw = self.runner.solve_sync(built, time_limit_s=time_limit, gap=config.gap)
        spent += raw.solve_seconds
        if not raw.outcome.has_solution:
            return EngineOutput(raw.outcome, None, list(inst.warnings), spent, inst.horizon)
        result = extract(built, raw).model_copy(update={"solve_seconds": round(spent, 3)})
        return EngineOutput(raw.outcome, result, list(inst.warnings), spent, inst.horizon)

    async def run_async(self, payload: DatasetPayload, config: RunConfig) -> EngineOutput:
        return await anyio.to_thread.run_sync(self.run, payload, config)

    def build_model(self, payload: DatasetPayload, config: RunConfig) -> BuiltModel | None:
        """The model `run` solves (with the weighted mode's bounds), unsolved; used by sensitivity
        analysis. None when the weighted mode's payoff table cannot be computed."""
        inst = build_instance(payload, config)
        bounds: dict[Criterion, CriterionBounds] | None = None
        if config.objective == ObjectiveKind.WEIGHTED:
            bounds, _spent, failed = self._payoff_bounds(inst, config, config.time_limit_s or self.default_time_limit_s)
            if failed is not None:
                return None
        return self.builder.build(inst, config, bounds=bounds)

    def _payoff_bounds(
        self, inst: ProblemInstance, config: RunConfig, time_limit: int
    ) -> tuple[dict[Criterion, CriterionBounds], float, SolverOutcome | None]:
        criteria = list(weighted_criteria(config))
        payoff: dict[Criterion, dict[Criterion, float]] = {}
        spent = 0.0
        for criterion in criteria:
            built = self.builder.build(inst, config, objective=CRITERIA[criterion].single_objective)
            raw = self.runner.solve_sync(built, time_limit_s=time_limit, gap=config.gap)
            spent += raw.solve_seconds
            if not raw.outcome.has_solution:
                return {}, spent, raw.outcome
            payoff[criterion] = {c: float(value(CRITERIA[c].expression(built.components)) or 0.0) for c in criteria}
        return ideal_points(payoff), spent, None

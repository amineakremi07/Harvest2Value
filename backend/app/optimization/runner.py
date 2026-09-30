"""Run CBC on a built model off the event loop, with bounded concurrency and explicit statuses."""

from __future__ import annotations

import logging
import threading
import time
from dataclasses import dataclass
from functools import partial

import anyio.to_thread
from pulp import PULP_CBC_CMD, LpStatus, PulpSolverError, value

from ..domain.enums import SolverOutcome
from ..domain.run_config import DEFAULT_GAP
from .builder import BuiltModel

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class RawSolution:
    outcome: SolverOutcome
    pulp_status: str
    sol_status: int | None
    solve_seconds: float
    objective_value: float | None


def map_status(status: int, sol_status: int) -> SolverOutcome:
    """PuLP status (1 optimal, 0 not solved, -1 infeasible, -2 unbounded, -3 undefined) and
    sol_status (1 optimal, 2 feasible at time limit, 0 no solution, -1 infeasible, -2 unbounded)."""
    if sol_status == 1 and status == 1:
        return SolverOutcome.OPTIMAL
    if sol_status == 2:
        return SolverOutcome.FEASIBLE
    if status == -1 or sol_status == -1:
        return SolverOutcome.INFEASIBLE
    if status == -2 or sol_status == -2:
        return SolverOutcome.UNBOUNDED
    if status == 0 or sol_status == 0:
        return SolverOutcome.NOT_SOLVED
    return SolverOutcome.ERROR


class SolverRunner:
    def __init__(self, max_concurrency: int = 2) -> None:
        self._slots = threading.BoundedSemaphore(max_concurrency)

    def solve_sync(self, built: BuiltModel, *, time_limit_s: int, gap: float | None = None) -> RawSolution:
        if built.registry.trivially_infeasible:
            return RawSolution(SolverOutcome.INFEASIBLE, "Infeasible", -1, 0.0, None)

        solver = PULP_CBC_CMD(msg=False, timeLimit=time_limit_s, gapRel=DEFAULT_GAP if gap is None else gap)
        with self._slots:
            started = time.perf_counter()
            try:
                built.problem.solve(solver)
            except PulpSolverError:
                logger.exception("CBC failed", extra={"objective": built.objective})
                return RawSolution(SolverOutcome.ERROR, "Error", None, time.perf_counter() - started, None)
            elapsed = time.perf_counter() - started

        outcome = map_status(built.problem.status, built.problem.sol_status)
        objective = value(built.problem.objective) if outcome.has_solution else None
        return RawSolution(outcome, LpStatus[built.problem.status], built.problem.sol_status, elapsed, objective)

    async def solve(self, built: BuiltModel, *, time_limit_s: int, gap: float | None = None) -> RawSolution:
        """Same as solve_sync, in a worker thread so the event loop keeps serving requests."""
        return await anyio.to_thread.run_sync(partial(self.solve_sync, built, time_limit_s=time_limit_s, gap=gap))

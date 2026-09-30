"""RunExecutor: background execution of solver work.

- a bounded number of jobs run at once (asyncio semaphore = SOLVER_MAX_CONCURRENCY);
- blocking work (CBC, database writes) runs in worker threads via anyio.to_thread, so the event
  loop keeps answering requests (/health stays responsive during a long run, audit R5);
- a bounded number of jobs may wait: beyond it `submit` raises SOLVER_BUSY (503);
- jobs live in memory: at startup, runs left `queued`/`running` by a previous process are marked
  `interrupted` (see OptimizationService.recover_interrupted).
"""

from __future__ import annotations

import asyncio
import logging
from collections.abc import Callable

import anyio.to_thread

from ..core.errors import SolverBusy

logger = logging.getLogger(__name__)

DEFAULT_MAX_PENDING = 50


class RunExecutor:
    def __init__(self, max_concurrency: int, max_pending: int = DEFAULT_MAX_PENDING) -> None:
        self.max_concurrency = max_concurrency
        self.max_pending = max_pending
        self._semaphore = asyncio.Semaphore(max_concurrency)
        self._tasks: dict[str, asyncio.Task[None]] = {}

    @property
    def pending(self) -> int:
        return sum(1 for task in self._tasks.values() if not task.done())

    def is_pending(self, key: str) -> bool:
        task = self._tasks.get(key)
        return task is not None and not task.done()

    def ensure_capacity(self) -> None:
        if self.pending >= self.max_pending:
            raise SolverBusy(details={"pending": self.pending, "max_pending": self.max_pending})

    def submit(self, key: str, work: Callable[[], None]) -> None:
        """Schedule `work` (blocking) under `key`. A key already pending is not scheduled twice.
        Must be called from the event loop (an async endpoint)."""
        if self.is_pending(key):
            return
        self.ensure_capacity()
        task = asyncio.get_running_loop().create_task(self._run(key, work), name=f"job:{key}")
        self._tasks[key] = task
        task.add_done_callback(lambda done: self._forget(key, done))

    def _forget(self, key: str, task: asyncio.Task[None]) -> None:
        if self._tasks.get(key) is task:
            del self._tasks[key]

    async def _run(self, key: str, work: Callable[[], None]) -> None:
        async with self._semaphore:
            try:
                await anyio.to_thread.run_sync(work)
            except Exception:  # the job records its own failure; this only guards the loop
                logger.exception("Background job failed", extra={"job": key})

    async def wait(self, key: str, timeout: float) -> bool:
        """Wait up to `timeout` seconds; True when the job is finished (or unknown)."""
        task = self._tasks.get(key)
        if task is None:
            return True
        if timeout <= 0:
            return task.done()
        done, _ = await asyncio.wait({task}, timeout=timeout)
        return bool(done)

    async def shutdown(self, timeout: float = 30.0) -> None:
        """Let running jobs finish (threads cannot be killed), then cancel what still waits."""
        tasks = [t for t in self._tasks.values() if not t.done()]
        if not tasks:
            return
        _, pending = await asyncio.wait(tasks, timeout=timeout)
        for task in pending:
            task.cancel()

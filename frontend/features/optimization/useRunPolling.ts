"use client";

import { useCallback, useEffect, useState } from "react";
import { ApiError } from "@/lib/api/client";
import { api } from "@/lib/api/endpoints";
import { isTerminal, type RunDetail } from "@/lib/api/types";

export const RUN_POLL_INTERVAL_MS = 1000;

export interface RunPolling {
  run: RunDetail | undefined;
  error: unknown;
  /** True while the run is queued/running and the hook keeps asking for its status. */
  polling: boolean;
  /** Fetch once more and resume polling if the run is not finished (e.g. after a cancel). */
  refresh: () => void;
}

type Fetcher = (runId: string, signal: AbortSignal) => Promise<RunDetail>;

/**
 * Reads a run, then re-reads it every `intervalMs` while it is queued or running. Stops on a
 * terminal status, on a 404 and on unmount. Transient errors are reported and retried.
 * `fetcher` must be stable (module-level function), or polling restarts on every render.
 */
export function useRunPolling(
  runId: string | null | undefined,
  { intervalMs = RUN_POLL_INTERVAL_MS, fetcher = api.run }: { intervalMs?: number; fetcher?: Fetcher } = {},
): RunPolling {
  const [run, setRun] = useState<RunDetail | undefined>(undefined);
  const [error, setError] = useState<unknown>(undefined);
  const [polling, setPolling] = useState(false);
  const [generation, setGeneration] = useState(0);

  useEffect(() => {
    if (!runId) return;
    const controller = new AbortController();
    let timer: ReturnType<typeof setTimeout> | undefined;
    let stopped = false;

    const tick = async () => {
      try {
        const detail = await fetcher(runId, controller.signal);
        if (stopped) return;
        setRun(detail);
        setError(undefined);
        if (isTerminal(detail.status)) {
          setPolling(false);
          return;
        }
        setPolling(true);
      } catch (err) {
        if (stopped || controller.signal.aborted) return;
        setError(err);
        if (err instanceof ApiError && err.status === 404) {
          setPolling(false);
          return;
        }
      }
      timer = setTimeout(tick, intervalMs);
    };

    void tick();
    return () => {
      stopped = true;
      controller.abort();
      if (timer !== undefined) clearTimeout(timer);
    };
  }, [runId, intervalMs, fetcher, generation]);

  const refresh = useCallback(() => setGeneration((g) => g + 1), []);
  return { run, error, polling, refresh };
}

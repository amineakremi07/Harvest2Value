import { act, renderHook } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { ApiError } from "@/lib/api/client";
import type { RunDetail, RunStatus } from "@/lib/api/types";
import { OLIVES_RUN } from "@/test/fixtures";
import { useRunPolling } from "./useRunPolling";

const withStatus = (status: RunStatus): RunDetail => ({ ...OLIVES_RUN, status });

/** Lets the pending fetch promise settle, then advances the poll timer. */
async function tick(ms: number) {
  await act(async () => {
    await vi.advanceTimersByTimeAsync(ms);
  });
}

describe("useRunPolling", () => {
  beforeEach(() => vi.useFakeTimers());
  afterEach(() => vi.useRealTimers());

  it("polls every second while the run is queued or running, then stops on a terminal status", async () => {
    const fetcher = vi
      .fn<(id: string, signal: AbortSignal) => Promise<RunDetail>>()
      .mockResolvedValueOnce(withStatus("queued"))
      .mockResolvedValueOnce(withStatus("running"))
      .mockResolvedValueOnce(withStatus("succeeded"));

    const { result } = renderHook(() => useRunPolling("run-1", { fetcher }));
    await tick(0);
    expect(fetcher).toHaveBeenCalledTimes(1);
    expect(result.current.run?.status).toBe("queued");
    expect(result.current.polling).toBe(true);

    await tick(999);
    expect(fetcher).toHaveBeenCalledTimes(1); // not before the interval
    await tick(1);
    expect(fetcher).toHaveBeenCalledTimes(2);
    expect(result.current.run?.status).toBe("running");

    await tick(1000);
    expect(fetcher).toHaveBeenCalledTimes(3);
    expect(result.current.run?.status).toBe("succeeded");
    expect(result.current.polling).toBe(false);

    await tick(5000);
    expect(fetcher).toHaveBeenCalledTimes(3); // stopped
  });

  it("does not poll a run that is already finished", async () => {
    const fetcher = vi.fn().mockResolvedValue(withStatus("infeasible"));
    const { result } = renderHook(() => useRunPolling("run-1", { fetcher }));
    await tick(3000);
    expect(fetcher).toHaveBeenCalledTimes(1);
    expect(result.current.polling).toBe(false);
  });

  it("keeps polling after a transient error and reports it", async () => {
    const fetcher = vi
      .fn()
      .mockRejectedValueOnce(new ApiError(0, "NETWORK_ERROR", "down"))
      .mockResolvedValueOnce(withStatus("succeeded"));
    const { result } = renderHook(() => useRunPolling("run-1", { fetcher }));
    await tick(0);
    expect(result.current.error).toBeInstanceOf(ApiError);
    await tick(1000);
    expect(fetcher).toHaveBeenCalledTimes(2);
    expect(result.current.error).toBeUndefined();
    expect(result.current.run?.status).toBe("succeeded");
  });

  it("stops on 404", async () => {
    const fetcher = vi.fn().mockRejectedValue(new ApiError(404, "NOT_FOUND", "Run not found"));
    renderHook(() => useRunPolling("missing", { fetcher }));
    await tick(5000);
    expect(fetcher).toHaveBeenCalledTimes(1);
  });

  it("stops polling on unmount", async () => {
    const fetcher = vi.fn().mockResolvedValue(withStatus("running"));
    const { unmount } = renderHook(() => useRunPolling("run-1", { fetcher }));
    await tick(0);
    unmount();
    await tick(5000);
    expect(fetcher).toHaveBeenCalledTimes(1);
  });

  it("refresh() fetches again and resumes polling", async () => {
    const fetcher = vi
      .fn()
      .mockResolvedValueOnce(withStatus("cancelled"))
      .mockResolvedValueOnce(withStatus("queued"))
      .mockResolvedValue(withStatus("succeeded"));
    const { result } = renderHook(() => useRunPolling("run-1", { fetcher }));
    await tick(0);
    expect(result.current.polling).toBe(false);
    act(() => result.current.refresh());
    await tick(0);
    expect(result.current.run?.status).toBe("queued");
    await tick(1000);
    expect(result.current.run?.status).toBe("succeeded");
    expect(fetcher).toHaveBeenCalledTimes(3);
  });

  it("does nothing without a run id", async () => {
    const fetcher = vi.fn();
    renderHook(() => useRunPolling(null, { fetcher }));
    await tick(2000);
    expect(fetcher).not.toHaveBeenCalled();
  });
});

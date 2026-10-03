"use client";

import { useCallback, useEffect, useState } from "react";

export interface ApiState<T> {
  data: T | undefined;
  error: unknown;
  loading: boolean;
  reload: () => void;
  setData: (data: T) => void;
}

interface Settled<T> {
  key: string;
  data: T | undefined;
  error: unknown;
}

/**
 * Loads `fetcher()` on mount and whenever `deps` change. `fetcher = null` skips the call
 * (dependent queries). While a new call is pending the previous data stays available;
 * responses of a superseded call are ignored. `deps` must be JSON-serializable.
 */
export function useApi<T>(fetcher: (() => Promise<T>) | null, deps: readonly unknown[]): ApiState<T> {
  const [tick, setTick] = useState(0);
  const enabled = fetcher !== null;
  const key = JSON.stringify([...deps, enabled, tick]);
  const [settled, setSettled] = useState<Settled<T>>({ key: "", data: undefined, error: undefined });

  useEffect(() => {
    if (!fetcher) return;
    let live = true;
    fetcher().then(
      (data) => live && setSettled({ key, data, error: undefined }),
      (error: unknown) => live && setSettled((s) => ({ key, data: s.data, error })),
    );
    return () => {
      live = false;
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps -- `key` encodes the caller's deps
  }, [key]);

  const reload = useCallback(() => setTick((t) => t + 1), []);
  const setData = useCallback((data: T) => setSettled({ key, data, error: undefined }), [key]);
  const current = settled.key === key;
  return {
    data: settled.data,
    error: current ? settled.error : undefined,
    loading: enabled && !current,
    reload,
    setData,
  };
}

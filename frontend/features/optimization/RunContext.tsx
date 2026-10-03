"use client";

import { createContext, useContext, useEffect, useState, type ReactNode } from "react";
import { api } from "@/lib/api/endpoints";
import type { DatasetPayload, OptimizationResult, RunDetail } from "@/lib/api/types";
import { nameIndex, type NameIndex } from "./names";
import { useRunPolling } from "./useRunPolling";

export interface RunView {
  runId: string;
  run: RunDetail | undefined;
  runError: unknown;
  polling: boolean;
  refresh: () => void;
  result: OptimizationResult | undefined;
  resultError: unknown;
  payload: DatasetPayload | undefined;
  names: NameIndex;
  currency: string | undefined;
}

const RunViewContext = createContext<RunView | null>(null);

/** Polls the run and, once it has a plan, loads the result and the dataset version it used. */
export function RunViewProvider({ runId, children }: { runId: string; children: ReactNode }) {
  const { run, error: runError, polling, refresh } = useRunPolling(runId);
  const [result, setResult] = useState<OptimizationResult | undefined>(undefined);
  const [resultError, setResultError] = useState<unknown>(undefined);
  const [payload, setPayload] = useState<DatasetPayload | undefined>(undefined);

  const hasPlan = run?.status === "succeeded";
  const datasetId = run?.dataset_id;
  const versionNo = run?.version_no;

  useEffect(() => {
    if (!hasPlan) return;
    let live = true;
    api.runResult(runId).then(
      (r) => live && setResult(r),
      (err: unknown) => live && setResultError(err),
    );
    return () => {
      live = false;
    };
  }, [runId, hasPlan]);

  useEffect(() => {
    if (!datasetId || !versionNo) return;
    let live = true;
    api.datasetVersion(datasetId, versionNo).then(
      (v) => live && setPayload(v.payload),
      () => undefined, // names fall back to ids
    );
    return () => {
      live = false;
    };
  }, [datasetId, versionNo]);

  const value: RunView = {
    runId,
    run,
    runError,
    polling,
    refresh,
    result,
    resultError,
    payload,
    names: nameIndex(payload),
    currency: payload?.currency ?? undefined,
  };
  return <RunViewContext.Provider value={value}>{children}</RunViewContext.Provider>;
}

export function useRunView(): RunView {
  const ctx = useContext(RunViewContext);
  if (!ctx) throw new Error("useRunView must be used inside <RunViewProvider>");
  return ctx;
}

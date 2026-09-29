"use client";

import { useState } from "react";
import { AlertTriangle, Loader2 } from "lucide-react";
import HarvestInput, { type HarvestInputValues } from "@/app/components/HarvestInput";
import AllocationTable from "@/app/components/AllocationTable";
import RiskGauge from "@/app/components/RiskGauge";
import FlowChart from "@/app/components/FlowChart";
import SankeyChart from "@/app/components/SankeyChart";
import UnifiedChat from "@/app/components/UnifiedChat";
import { glassCard } from "@/app/components/styles";
import {
  ApiError,
  MOCK_OPTIMIZE_RESPONSE,
  optimizeHarvest,
  type OptimizeRequest,
  type OptimizeResponse,
} from "@/app/lib/api";
import { DEMO_INPUT, buildOptimizeRequest } from "@/app/lib/optimize";

type LoadStatus = "idle" | "loading" | "success" | "error";

/** Existing buyer/storage solver, charts and What-If chat (frozen /optimize API), unchanged. */
export default function BuyerOptimizer() {
  const [status, setStatus] = useState<LoadStatus>("idle");
  const [result, setResult] = useState<OptimizeResponse>(MOCK_OPTIMIZE_RESPONSE);
  const [dataset, setDataset] = useState<OptimizeRequest>(() => buildOptimizeRequest(DEMO_INPUT));
  const [error, setError] = useState<string | null>(null);
  const [usingDemoData, setUsingDemoData] = useState(true);

  async function handleSubmit(values: HarvestInputValues) {
    setStatus("loading");
    setError(null);

    try {
      const request = buildOptimizeRequest(values);
      const response = await optimizeHarvest(request);
      setDataset(request);
      setResult(response);
      setUsingDemoData(false);
      setStatus("success");
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Unexpected error running optimization.");
      setStatus("error");
    }
  }

  /** A What-If answer carries a re-solved plan, so the table and charts follow the chat. */
  function handleScenarioResult(scenarioResult: OptimizeResponse) {
    setResult(scenarioResult);
    setUsingDemoData(false);
    setError(null);
    setStatus("success");
  }

  function resetToDemo() {
    setResult(MOCK_OPTIMIZE_RESPONSE);
    setUsingDemoData(true);
    setError(null);
    setStatus("idle");
  }

  return (
    <>
      {status === "loading" && (
        <div className={`${glassCard} flex items-center gap-2 py-3 text-base font-medium`}>
          <Loader2 className="h-5 w-5 animate-spin text-accent-text" aria-hidden="true" />
          <span>Running optimization…</span>
        </div>
      )}

      {status === "error" && error && (
        <div className="flex flex-wrap items-center justify-between gap-3 rounded-2xl border border-danger/40 bg-danger/10 px-6 py-4">
          <span className="inline-flex items-center gap-2 text-base font-medium text-danger">
            <AlertTriangle className="h-5 w-5" aria-hidden="true" />
            <span>{error}</span>
          </span>
          <button
            type="button"
            onClick={resetToDemo}
            className="inline-flex min-h-[40px] items-center rounded-full bg-accent px-4 py-2 text-sm font-bold text-white outline-none hover:bg-accent-hover focus-visible:ring-2 focus-visible:ring-accent"
          >
            Use demo data
          </button>
        </div>
      )}

      {usingDemoData && status !== "loading" && status !== "error" && (
        <div className="rounded-2xl border border-warning/40 bg-warning/10 px-6 py-4 text-base font-medium text-text-primary">
          Showing demo data — run an optimization to see your own results.
        </div>
      )}

      <div className="grid grid-cols-12 gap-4">
        <div className="col-span-12 lg:col-span-7">
          <HarvestInput onSubmit={handleSubmit} />
        </div>
        <div className="col-span-12 lg:col-span-5">
          <RiskGauge result={result} />
        </div>
      </div>

      <div className="grid grid-cols-12 items-stretch gap-4 lg:min-h-[640px]">
        <div className="col-span-12 flex flex-col gap-4 lg:col-span-7">
          <AllocationTable result={result} />
          <UnifiedChat data={dataset} result={result} onScenarioResult={handleScenarioResult} />
        </div>
        <div className="col-span-12 lg:col-span-5">
          <FlowChart result={result} className="h-full" />
        </div>
      </div>

      <SankeyChart result={result} />
    </>
  );
}

"use client";

import { useState } from "react";
import { AlertTriangle, Loader2, Sprout } from "lucide-react";
import HarvestInput, { type HarvestInputValues } from "@/app/components/HarvestInput";
import AllocationTable from "@/app/components/AllocationTable";
import RiskGauge from "@/app/components/RiskGauge";
import {
  ApiError,
  MOCK_OPTIMIZE_RESPONSE,
  optimizeHarvest,
  type OptimizeRequest,
  type OptimizeResponse,
} from "@/app/lib/api";

type LoadStatus = "idle" | "loading" | "success" | "error";

/**
 * HarvestInput only collects harvest_kg/storage_capacity_kg/buyers (per its
 * scoped requirements). The remaining OptimizeRequest fields don't have a
 * form yet, so we fill them with sensible defaults here until a producer
 * identity / crop / logistics form step is added.
 */
function buildOptimizeRequest(values: HarvestInputValues): OptimizeRequest {
  return {
    producer: {
      id: "producer-1",
      name: "My Farm",
      region: "Unknown",
      country: "Unknown",
      harvest_kg: values.harvest_kg,
      storage_capacity_kg: values.storage_capacity_kg,
      shelf_life_days: 14,
    },
    buyers: values.buyers,
    crop: {
      name: "Mixed Produce",
      type: "semi_perishable",
    },
    logistics: {
      available_vehicles: 1,
      vehicle_capacity_kg: Math.max(values.harvest_kg, 1000),
      refrigerated_required: false,
      road_condition: "fair",
    },
  };
}

export default function Home() {
  const [status, setStatus] = useState<LoadStatus>("idle");
  const [result, setResult] = useState<OptimizeResponse>(MOCK_OPTIMIZE_RESPONSE);
  const [error, setError] = useState<string | null>(null);
  const [usingDemoData, setUsingDemoData] = useState(true);

  async function handleSubmit(values: HarvestInputValues) {
    setStatus("loading");
    setError(null);

    try {
      const response = await optimizeHarvest(buildOptimizeRequest(values));
      setResult(response);
      setUsingDemoData(false);
      setStatus("success");
    } catch (err) {
      const message =
        err instanceof ApiError ? err.message : "Unexpected error running optimization.";
      setError(message);
      setStatus("error");
    }
  }

  function useDemoData() {
    setResult(MOCK_OPTIMIZE_RESPONSE);
    setUsingDemoData(true);
    setError(null);
    setStatus("idle");
  }

  return (
    <div className="min-h-screen bg-slate-950 text-slate-100">
      <div className="mx-auto max-w-7xl px-4 py-6 md:py-8">
        <div className="grid grid-cols-12 gap-4 md:gap-6">
          {/* Header */}
          <header className="col-span-12 rounded-2xl border border-slate-700 bg-slate-900 p-4 shadow-lg md:p-6">
            <div className="inline-flex items-center gap-3">
              <Sprout className="h-8 w-8 text-emerald-500" aria-hidden="true" />
              <div>
                <h1 className="text-lg font-bold text-slate-100 md:text-2xl">
                  Harvest2Value
                </h1>
                <p className="text-base text-slate-400">
                  Allocate your harvest across buyers and storage to maximize net profit.
                </p>
              </div>
            </div>
          </header>

          {/* Status banner: loading / error / demo data */}
          {status === "loading" && (
            <div className="col-span-12 inline-flex items-center gap-2 rounded-2xl border border-slate-700 bg-slate-900 px-4 py-3 text-base font-medium text-slate-100">
              <Loader2 className="h-5 w-5 animate-spin text-emerald-500" aria-hidden="true" />
              <span>Running optimization…</span>
            </div>
          )}

          {status === "error" && error && (
            <div className="col-span-12 flex flex-wrap items-center justify-between gap-3 rounded-2xl border border-rose-700 bg-rose-950 px-4 py-3">
              <span className="inline-flex items-center gap-2 text-base font-medium text-rose-300">
                <AlertTriangle className="h-5 w-5" aria-hidden="true" />
                <span>{error}</span>
              </span>
              <button
                type="button"
                onClick={useDemoData}
                className="inline-flex min-h-[44px] items-center rounded-xl bg-rose-700 px-4 py-2 text-base font-medium text-white hover:bg-rose-600 focus:outline-none focus:ring-2 focus:ring-rose-400"
              >
                Use demo data
              </button>
            </div>
          )}

          {usingDemoData && status !== "loading" && status !== "error" && (
            <div className="col-span-12 rounded-2xl border border-amber-700 bg-amber-950 px-4 py-3 text-base font-medium text-amber-300">
              Showing demo data — run an optimization to see your own results.
            </div>
          )}

          {/* Main dashboard */}
          <div className="col-span-12 lg:col-span-4">
            <HarvestInput onSubmit={handleSubmit} />
          </div>

          <div className="col-span-12 md:col-span-6 lg:col-span-3">
            <RiskGauge result={result} />
          </div>

          <div className="col-span-12 md:col-span-6 lg:col-span-5">
            <AllocationTable result={result} />
          </div>

          {/* Reserved for @Member3 (What-If & XAI) — do not implement here */}
          <div className="col-span-12 flex min-h-[200px] items-center justify-center rounded-2xl border-2 border-dashed border-slate-700 bg-slate-900/40 p-6 text-center text-base text-slate-500 md:col-span-6">
            What-If Chat — reserved for @Member3 (WhatIfChat.tsx)
          </div>
          <div className="col-span-12 flex min-h-[200px] items-center justify-center rounded-2xl border-2 border-dashed border-slate-700 bg-slate-900/40 p-6 text-center text-base text-slate-500 md:col-span-6">
            Explanation View — reserved for @Member3 (ExplainView.tsx)
          </div>

          {/* Reserved for @Member4 (Data, Viz & DevOps) — do not implement here */}
          <div className="col-span-12 flex min-h-[200px] items-center justify-center rounded-2xl border-2 border-dashed border-slate-700 bg-slate-900/40 p-6 text-center text-base text-slate-500 md:col-span-6">
            Sankey Chart — reserved for @Member4 (SankeyChart.tsx)
          </div>
          <div className="col-span-12 flex min-h-[200px] items-center justify-center rounded-2xl border-2 border-dashed border-slate-700 bg-slate-900/40 p-6 text-center text-base text-slate-500 md:col-span-6">
            Flow Chart — reserved for @Member4 (FlowChart.tsx)
          </div>
        </div>
      </div>
    </div>
  );
}

"use client";

import { useState } from "react";
import {
  AlertTriangle,
  Loader2,
  Waypoints,
  MessageSquareText,
  Lightbulb,
  Wheat,
  Warehouse,
  TrendingUp,
} from "lucide-react";
import Sidebar from "@/app/components/Sidebar";
import Header from "@/app/components/Header";
import HarvestInput, { type HarvestInputValues } from "@/app/components/HarvestInput";
import AllocationTable from "@/app/components/AllocationTable";
import RiskGauge, { RISK_CONFIG, getRiskLevel, getWasteRatio } from "@/app/components/RiskGauge";
import FlowChart from "@/app/components/FlowChart";
import SankeyChart from "@/app/components/SankeyChart";
import {
  ApiError,
  MOCK_OPTIMIZE_RESPONSE,
  optimizeHarvest,
  type OptimizeRequest,
  type OptimizeResponse,
} from "@/app/lib/api";

type LoadStatus = "idle" | "loading" | "success" | "error";

/**
 * HarvestInput only collects harvest_kg/storage_capacity_kg — buyers are
 * chosen by the optimizer, not entered by the user. The backend's
 * OptimizeRequest schema still requires a non-empty `buyers` list, though,
 * so until Member 1 exposes a buyer directory (or makes buyers optional
 * server-side), we submit a placeholder candidate pool here. The optimizer
 * decides how much (if any) of the harvest each one actually gets.
 */
const DEFAULT_BUYER_POOL = [
  {
    id: "buyer-1",
    name: "Local Cooperative",
    location: "Nearby Market",
    max_demand_kg: 50000,
    price_per_kg: 0.8,
    distance_km: 15,
    transport_cost_per_kg_per_km: 0.01,
  },
  {
    id: "buyer-2",
    name: "Regional Distributor",
    location: "Regional Hub",
    max_demand_kg: 50000,
    price_per_kg: 0.65,
    distance_km: 60,
    transport_cost_per_kg_per_km: 0.008,
  },
];

/**
 * HarvestInput only collects harvest_kg/storage_capacity_kg. The remaining
 * OptimizeRequest fields don't have a form yet, so we fill them with
 * sensible defaults here until a producer identity / crop / logistics form
 * step is added.
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
    buyers: DEFAULT_BUYER_POOL,
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

const card = "bg-[#131B2E] border border-[#1E293B] rounded-xl p-6";

const numberFormatter = new Intl.NumberFormat("en-US", { maximumFractionDigits: 0 });
const currencyFormatter = new Intl.NumberFormat("en-US", {
  style: "currency",
  currency: "TND",
  maximumFractionDigits: 0,
});

function KpiCard({
  icon: Icon,
  label,
  value,
  accentColor,
}: {
  icon: typeof Wheat;
  label: string;
  value: string;
  accentColor: string;
}) {
  return (
    <div className={`${card} border-l-4`} style={{ borderLeftColor: accentColor }}>
      <div className="mb-3 flex items-center gap-2 text-slate-400">
        <Icon className="h-4 w-4" aria-hidden="true" />
        <span className="text-xs font-semibold uppercase tracking-wider">{label}</span>
      </div>
      <div className="font-mono text-[28px] font-bold tabular-nums text-white">{value}</div>
    </div>
  );
}

function ReservedSlot({
  icon: Icon,
  category,
  label,
}: {
  icon: typeof Waypoints;
  category: string;
  label: string;
}) {
  return (
    <div
      className={`${card} flex min-h-[200px] flex-col items-center justify-center gap-3 border-dashed text-center`}
    >
      <div className="flex items-center gap-2 text-slate-400">
        <Icon className="h-5 w-5 text-[#10B981]" aria-hidden="true" />
        <span className="text-xs font-semibold uppercase tracking-wider">{category}</span>
      </div>
      <p className="text-sm text-slate-400">{label}</p>
    </div>
  );
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
      // TEMP-DIAG
      console.log("[H2V-DIAG] before setResult", { values, total_harvest_kg: response.total_harvest_kg, wasted_kg: response.wasted_kg, stored_kg: response.stored_kg });
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

  const riskLevel = getRiskLevel(getWasteRatio(result));
  const riskConfig = RISK_CONFIG[riskLevel];

  return (
    <div className="min-h-screen bg-[#090D16] text-white">
      <Sidebar />

      <div className="lg:pl-64">
        <div className="mx-auto max-w-7xl px-6 py-6 lg:px-10">
          <Header />

          <div className="mt-6 space-y-6">
            {status === "loading" && (
              <div className={`${card} flex items-center gap-2 py-3 text-base font-medium`}>
                <Loader2 className="h-5 w-5 animate-spin text-[#10B981]" aria-hidden="true" />
                <span>Running optimization…</span>
              </div>
            )}

            {status === "error" && error && (
              <div className="flex flex-wrap items-center justify-between gap-3 rounded-xl border border-rose-500/30 bg-rose-500/10 px-6 py-4">
                <span className="inline-flex items-center gap-2 text-base font-medium text-rose-300">
                  <AlertTriangle className="h-5 w-5" aria-hidden="true" />
                  <span>{error}</span>
                </span>
                <button
                  type="button"
                  onClick={useDemoData}
                  className="inline-flex min-h-[40px] items-center rounded-full bg-[#06B6D4] px-4 py-2 text-sm font-bold text-black hover:bg-cyan-400 focus:outline-none focus:ring-2 focus:ring-cyan-300"
                >
                  Use demo data
                </button>
              </div>
            )}

            {usingDemoData && status !== "loading" && status !== "error" && (
              <div className="rounded-xl border border-amber-500/30 bg-amber-500/10 px-6 py-4 text-base font-medium text-amber-300">
                Showing demo data — run an optimization to see your own results.
              </div>
            )}

            {/* KPI metrics row */}
            <div className="grid grid-cols-1 gap-6 sm:grid-cols-2 lg:grid-cols-4">
              <KpiCard
                icon={Wheat}
                label="Total Harvest"
                value={`${numberFormatter.format(result.total_harvest_kg)} kg`}
                accentColor="#10B981"
              />
              <KpiCard
                icon={Warehouse}
                label="Active Storage"
                value={`${numberFormatter.format(result.stored_kg)} kg`}
                accentColor="#06B6D4"
              />
              <KpiCard
                icon={TrendingUp}
                label="Net Profit"
                value={currencyFormatter.format(result.net_profit)}
                accentColor="#10B981"
              />
              <KpiCard
                icon={riskConfig.icon}
                label="Risk Rating"
                value={riskConfig.label}
                accentColor={riskConfig.ringColor}
              />
            </div>

            {/* Main bento: HarvestInput + AllocationTable (main), RiskGauge + flow chart (side panel) */}
            <div className="grid grid-cols-1 gap-6 lg:grid-cols-3">
              <div className="space-y-6 lg:col-span-2">
                <HarvestInput onSubmit={handleSubmit} />
                <AllocationTable result={result} />
              </div>

              <div className="space-y-6">
                <RiskGauge result={result} />
                <FlowChart result={result} />
              </div>
            </div>

            {/* Reserved for @Member3 (What-If & XAI) and @Member4 (Sankey) — do not implement here */}
            <div className="grid grid-cols-1 gap-6 md:grid-cols-3">
              <ReservedSlot
                icon={MessageSquareText}
                category="What-If Chat"
                label="Reserved for @Member3 (WhatIfChat.tsx)"
              />
              <ReservedSlot
                icon={Lightbulb}
                category="Explanation View"
                label="Reserved for @Member3 (ExplainView.tsx)"
              />
              <SankeyChart result={result} />
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}

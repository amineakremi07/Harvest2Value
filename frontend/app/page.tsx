"use client";

import { useState } from "react";
import {
  AlertTriangle,
  Loader2,
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
import UnifiedChat from "@/app/components/UnifiedChat";
import {
  ApiError,
  MOCK_OPTIMIZE_RESPONSE,
  optimizeHarvest,
  type OptimizeRequest,
  type OptimizeResponse,
} from "@/app/lib/api";

type LoadStatus = "idle" | "loading" | "success" | "error";

/** Matches MOCK_OPTIMIZE_RESPONSE so the demo plan and its dataset agree. */
const DEMO_INPUT: HarvestInputValues = {
  harvest_kg: MOCK_OPTIMIZE_RESPONSE.total_harvest_kg,
  storage_capacity_kg: MOCK_OPTIMIZE_RESPONSE.stored_kg,
};

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

const card = "bg-white dark:bg-[#131B2E] border border-slate-200 dark:border-[#1E293B] rounded-xl p-6";

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
      <div className="mb-3 flex items-center gap-2 text-[#64748B] dark:text-slate-400">
        <Icon className="h-4 w-4" aria-hidden="true" />
        <span className="text-xs font-semibold uppercase tracking-wider">{label}</span>
      </div>
      <div className="font-mono text-[28px] font-bold tabular-nums text-[#0F172A] dark:text-white">{value}</div>
    </div>
  );
}

export default function Home() {
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

  /**
   * A What-If answer carries a re-solved plan and the dataset it was solved
   * on, so the KPIs, table and charts follow the conversation.
   */
  function handleScenarioResult(scenarioResult: OptimizeResponse) {
    setResult(scenarioResult);
    setUsingDemoData(false);
    setError(null);
    setStatus("success");
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
    <div className="min-h-screen bg-[#F8FAFC] dark:bg-[#090D16] text-[#0F172A] dark:text-white">
      <Sidebar />

      <div className="lg:pl-64">
        <div className="mx-auto max-w-7xl px-6 py-6 lg:px-10">
          <Header />

          <div className="mt-6 space-y-6">
            {status === "loading" && (
              <div className={`${card} flex items-center gap-2 py-3 text-base font-medium`}>
                <Loader2 className="h-5 w-5 animate-spin text-[#059669] dark:text-[#10B981]" aria-hidden="true" />
                <span>Running optimization…</span>
              </div>
            )}

            {status === "error" && error && (
              <div className="flex flex-wrap items-center justify-between gap-3 rounded-xl border border-rose-500/30 bg-rose-500/10 px-6 py-4">
                <span className="inline-flex items-center gap-2 text-base font-medium text-rose-700 dark:text-rose-300">
                  <AlertTriangle className="h-5 w-5" aria-hidden="true" />
                  <span>{error}</span>
                </span>
                <button
                  type="button"
                  onClick={useDemoData}
                  className="inline-flex min-h-[40px] items-center rounded-full bg-[#06B6D4] px-4 py-2 text-sm font-bold text-white dark:text-black hover:bg-cyan-400 focus:outline-none focus:ring-2 focus:ring-cyan-300"
                >
                  Use demo data
                </button>
              </div>
            )}

            {usingDemoData && status !== "loading" && status !== "error" && (
              <div className="rounded-xl border border-amber-500/30 bg-amber-500/10 px-6 py-4 text-base font-medium text-amber-700 dark:text-amber-300">
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

            {/* Controls row: harvest form + risk summary */}
            <div className="grid grid-cols-12 gap-6">
              <div className="col-span-12 lg:col-span-7">
                <HarvestInput onSubmit={handleSubmit} />
              </div>
              <div className="col-span-12 lg:col-span-5">
                <RiskGauge result={result} />
              </div>
            </div>

            {/*
              Main grid. The left column stacks the allocation table over the
              assistant card, which flexes to absorb whatever vertical space the
              taller right-hand logistics panel leaves behind.
            */}
            <div className="grid grid-cols-12 items-stretch gap-6 lg:min-h-[640px]">
              <div className="col-span-12 flex flex-col gap-6 lg:col-span-7">
                <AllocationTable result={result} />
                <UnifiedChat
                  data={dataset}
                  result={result}
                  onScenarioResult={handleScenarioResult}
                />
              </div>

              <div className="col-span-12 lg:col-span-5">
                <FlowChart result={result} className="h-full" />
              </div>
            </div>

            {/* Harvest -> buyers/storage/waste flow (Member 4), full width */}
            <div className="grid grid-cols-12 gap-6">
              <div className="col-span-12">
                <SankeyChart result={result} />
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}

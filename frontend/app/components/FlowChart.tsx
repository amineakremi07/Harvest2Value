"use client";

import React, { useState, useEffect, useMemo } from "react";
import {
  ComposedChart,
  Bar,
  Line,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  Legend,
  ResponsiveContainer,
  Cell,
  ScatterChart,
  Scatter,
  ZAxis,
} from "recharts";

// ============================================================================
// Types (aligned with backend OptimizeResponse and data/schema.json)
// ============================================================================

export interface AllocationDetail {
  buyer_name: string;
  allocated_kg: number;
  unit_price: number;
  revenue: number;
  transport_cost: number;
  net_profit: number;
  distance_km: number;
}

export interface OptimizeResult {
  total_harvest_kg?: number;
  allocated_kg?: number;
  stored_kg?: number;
  wasted_kg?: number;
  total_revenue?: number;
  total_transport_cost?: number;
  net_profit?: number;
  allocation?: Record<string, AllocationDetail> | AllocationDetail[];
}

export interface FlowChartProps {
  /** Full or partial OptimizeResponse from /api/v1/optimize */
  result?: OptimizeResult | null;
  /** Direct allocation array/object (optional fallback) */
  allocation?: Record<string, AllocationDetail> | AllocationDetail[];
  className?: string;
}

// ============================================================================
// Palette & Theme Constants
// ============================================================================

const PALETTE = [
  "#2563eb", // blue-600
  "#7c3aed", // violet-600
  "#0891b2", // cyan-600
  "#059669", // emerald-600
  "#d97706", // amber-600
  "#e11d48", // rose-600
];

// ============================================================================
// Helpers
// ============================================================================

function formatKg(value: number): string {
  if (value >= 1000) return `${(value / 1000).toFixed(1)}t`;
  return `${value.toLocaleString()}kg`;
}

function formatCurrency(value: number): string {
  return `${value.toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 })} DT`;
}

// ============================================================================
// Custom Tooltip for Logistics Composed Chart
// ============================================================================

interface TooltipItem {
  name: string;
  value: number;
  color?: string;
  dataKey?: string;
}

function LogisticsTooltipContent({
  active,
  payload,
  label,
}: {
  active?: boolean;
  payload?: TooltipItem[];
  label?: string;
}) {
  if (!active || !payload || payload.length === 0) return null;

  return (
    <div className="z-50 min-w-[220px] rounded-xl border border-card-border bg-white/95 p-3.5 shadow-xl backdrop-blur-sm dark:border-slate-700 dark:bg-slate-900/95">
      <div className="mb-2 border-b border-slate-100 pb-1.5 dark:border-slate-800">
        <p className="font-semibold text-slate-900 dark:text-white">{label}</p>
      </div>
      <div className="space-y-1.5 text-xs">
        {payload.map((entry) => {
          let formattedValue = entry.value?.toLocaleString();
          if (entry.dataKey === "allocated_kg") {
            formattedValue = `${entry.value?.toLocaleString()} kg`;
          } else if (entry.dataKey === "distance_km") {
            formattedValue = `${entry.value} km`;
          } else if (entry.dataKey === "transport_cost") {
            formattedValue = formatCurrency(entry.value);
          }

          return (
            <div key={entry.name} className="flex items-center justify-between gap-3">
              <span className="flex items-center gap-1.5 text-slate-500 dark:text-slate-400">
                <span className="h-2 w-2 rounded-full" style={{ backgroundColor: entry.color }} />
                {entry.name}
              </span>
              <span className="font-semibold text-slate-800 dark:text-slate-200">
                {formattedValue}
              </span>
            </div>
          );
        })}
      </div>
    </div>
  );
}

// ============================================================================
// Custom Tooltip for Bubble Chart
// ============================================================================

function BubbleTooltipContent({
  active,
  payload,
}: {
  active?: boolean;
  payload?: Array<{ payload: any }>;
}) {
  if (!active || !payload || payload.length === 0) return null;

  const data = payload[0].payload as {
    buyer_name: string;
    distance_km: number;
    allocated_kg: number;
    transport_cost: number;
    net_profit: number;
    cost_per_kg: number;
  };

  return (
    <div className="z-50 min-w-[220px] rounded-xl border border-card-border bg-white/95 p-3.5 shadow-xl backdrop-blur-sm dark:border-slate-700 dark:bg-slate-900/95">
      <p className="mb-2 border-b border-slate-100 pb-1 font-semibold text-slate-900 dark:text-white">
        {data.buyer_name}
      </p>
      <div className="space-y-1 text-xs text-slate-600 dark:text-slate-300">
        <div className="flex justify-between">
          <span className="text-slate-500 dark:text-slate-400">Distance:</span>
          <span className="font-semibold">{data.distance_km} km</span>
        </div>
        <div className="flex justify-between">
          <span className="text-slate-500 dark:text-slate-400">Volume:</span>
          <span className="font-semibold">{data.allocated_kg.toLocaleString()} kg</span>
        </div>
        <div className="flex justify-between">
          <span className="text-slate-500 dark:text-slate-400">Transport Cost:</span>
          <span className="font-semibold text-amber-600 dark:text-amber-400">
            {formatCurrency(data.transport_cost)}
          </span>
        </div>
        <div className="flex justify-between">
          <span className="text-slate-500 dark:text-slate-400">Unit Freight:</span>
          <span className="font-semibold">{formatCurrency(data.cost_per_kg)}/kg</span>
        </div>
        <div className="mt-1.5 flex justify-between border-t border-slate-100 pt-1.5 dark:border-slate-800">
          <span className="font-medium text-slate-700 dark:text-slate-300">Net Profit:</span>
          <span className="font-bold text-success">
            {formatCurrency(data.net_profit)}
          </span>
        </div>
      </div>
    </div>
  );
}

// ============================================================================
// Main FlowChart Component
// ============================================================================

export default function FlowChart({
  result,
  allocation: propAllocation,
  className = "",
}: FlowChartProps) {
  const [mounted, setMounted] = useState(false);

  useEffect(() => {
    setMounted(true);
  }, []);

  // Normalize allocation input
  const rawAllocation = propAllocation ?? result?.allocation ?? {};
  const allocationList: AllocationDetail[] = useMemo(() => {
    if (Array.isArray(rawAllocation)) return rawAllocation;
    return Object.values(rawAllocation);
  }, [rawAllocation]);

  // Process data for charts
  const { chartData, totalShipped, totalTransportCost, totalProfit, hasData } = useMemo(() => {
    const activeEntries = allocationList.filter((a) => (a.allocated_kg || 0) > 0);

    if (activeEntries.length === 0) {
      return {
        chartData: [],
        totalShipped: 0,
        totalTransportCost: 0,
        totalProfit: 0,
        hasData: false,
      };
    }

    const shipped = activeEntries.reduce((sum, a) => sum + a.allocated_kg, 0);
    const transport = activeEntries.reduce((sum, a) => sum + (a.transport_cost || 0), 0);
    const profit = activeEntries.reduce((sum, a) => sum + (a.net_profit || 0), 0);

    const data = activeEntries.map((a, idx) => ({
      buyer_name: a.buyer_name,
      allocated_kg: a.allocated_kg,
      distance_km: a.distance_km,
      transport_cost: a.transport_cost || 0,
      net_profit: a.net_profit || 0,
      unit_price: a.unit_price || 0,
      cost_per_kg: a.allocated_kg > 0 ? (a.transport_cost || 0) / a.allocated_kg : 0,
      color: PALETTE[idx % PALETTE.length],
    }));

    return {
      chartData: data,
      totalShipped: result?.allocated_kg ?? shipped,
      totalTransportCost: result?.total_transport_cost ?? transport,
      totalProfit: result?.net_profit ?? profit,
      hasData: true,
    };
  }, [allocationList, result]);

  // ---- Empty / Zero State ----
  if (!mounted || !hasData) {
    return (
      <div
        className={`flex flex-col items-center justify-center rounded-2xl border border-dashed border-card-border bg-slate-50/70 p-8 text-center dark:border-slate-800 dark:bg-slate-900/40 ${className}`}
      >
        <div className="mb-3 flex h-12 w-12 items-center justify-center rounded-full bg-slate-100 text-slate-400 dark:bg-slate-800 dark:text-slate-500">
          <svg className="h-6 w-6" fill="none" viewBox="0 0 24 24" stroke="currentColor">
            <path
              strokeLinecap="round"
              strokeLinejoin="round"
              strokeWidth={1.5}
              d="M9 17a2 2 0 11-4 0 2 2 0 014 0zM19 17a2 2 0 11-4 0 2 2 0 014 0z"
            />
            <path
              strokeLinecap="round"
              strokeLinejoin="round"
              strokeWidth={1.5}
              d="M13 16V6a1 1 0 00-1-1H4a1 1 0 00-1 1v10a1 1 0 001 1h1m8-1a1 1 0 01-1 1H9m4-1V8a1 1 0 011-1h2.586a1 1 0 01.707.293l3.414 3.414a1 1 0 01.293.707V16a1 1 0 01-1 1h-1m-6-1a1 1 0 001 1h1M5 17a2 2 0 104 0m-4 0a2 2 0 114 0m6 0a2 2 0 104 0m-4 0a2 2 0 114 0"
            />
          </svg>
        </div>
        <h4 className="text-sm font-semibold text-slate-700 dark:text-slate-200">
          No Logistics Data Available
        </h4>
        <p className="mt-1 max-w-sm text-xs text-slate-500 dark:text-slate-400">
          Run the optimizer to calculate buyer distances, transport costs, and volume trade-offs.
        </p>
      </div>
    );
  }

  return (
    <div
      className={`flex flex-col gap-6 rounded-2xl border border-card-border bg-white p-6 shadow-sm dark:border-slate-800 dark:bg-slate-900 ${className}`}
    >
      {/* Header */}
      <div className="flex flex-wrap items-center justify-between gap-3 border-b border-slate-100 pb-4 dark:border-slate-800">
        <div>
          <h3 className="text-base font-semibold text-slate-900 dark:text-white">
            Logistics &amp; Transport Analysis
          </h3>
          <p className="text-xs text-slate-500 dark:text-slate-400">
            Comparing shipping volumes, route distances, and transport costs across active buyers
          </p>
        </div>
        <div className="flex items-center gap-2">
          <span className="inline-flex items-center gap-1 rounded-full bg-blue-50 px-2.5 py-1 text-xs font-medium text-blue-700 dark:bg-blue-950/60 dark:text-blue-300">
            {chartData.length} Destinations
          </span>
        </div>
      </div>

      {/* Chart 1: Dual-Axis Composed Chart (Volume in Bars vs. Transport Cost in Line) */}
      <div>
        <div className="mb-2 flex items-center justify-between">
          <h4 className="text-xs font-semibold uppercase tracking-wider text-slate-500 dark:text-slate-400">
            Allocated Volume vs. Transport Cost
          </h4>
        </div>
        <div className="h-[300px] w-full">
          <ResponsiveContainer width="100%" height="100%">
            <ComposedChart
              data={chartData}
              margin={{ top: 12, right: 24, left: 8, bottom: 28 }}
            >
              <CartesianGrid
                strokeDasharray="3 3"
                className="stroke-slate-100 dark:stroke-slate-800"
              />
              <XAxis
                dataKey="buyer_name"
                tick={{ fontSize: 11 }}
                className="fill-slate-600 dark:fill-slate-400"
                interval={0}
                angle={-15}
                textAnchor="end"
                height={45}
              />
              <YAxis
                yAxisId="left"
                orientation="left"
                tickFormatter={formatKg}
                tick={{ fontSize: 11 }}
                className="fill-slate-600 dark:fill-slate-400"
                label={{
                  value: "Volume (kg)",
                  angle: -90,
                  position: "insideLeft",
                  style: { fontSize: 10, fill: "#64748b" },
                }}
              />
              <YAxis
                yAxisId="right"
                orientation="right"
                tickFormatter={(v) => `$${v}`}
                tick={{ fontSize: 11 }}
                className="fill-slate-600 dark:fill-slate-400"
                label={{
                  value: "Cost (DT)",
                  angle: 90,
                  position: "insideRight",
                  style: { fontSize: 10, fill: "#64748b" },
                }}
              />
              <Tooltip content={<LogisticsTooltipContent />} />
              <Legend wrapperStyle={{ fontSize: 11, paddingTop: 10 }} />
              <Bar
                yAxisId="left"
                dataKey="allocated_kg"
                name="Volume Allocated (kg)"
                radius={[6, 6, 0, 0]}
              >
                {chartData.map((entry, index) => (
                  <Cell key={`cell-vol-${index}`} fill={entry.color} fillOpacity={0.85} />
                ))}
              </Bar>
              <Line
                yAxisId="right"
                type="monotone"
                dataKey="transport_cost"
                name="Transport Cost (DT)"
                stroke="#f59e0b"
                strokeWidth={3}
                dot={{ r: 5, fill: "#f59e0b", strokeWidth: 2, stroke: "#fff" }}
              />
            </ComposedChart>
          </ResponsiveContainer>
        </div>
      </div>

      {/* Chart 2: Distance vs Cost Scatter / Bubble Chart */}
      <div className="border-t border-slate-100 pt-4 dark:border-slate-800">
        <div className="mb-2">
          <h4 className="text-xs font-semibold uppercase tracking-wider text-slate-500 dark:text-slate-400">
            Route Distance vs. Transport Cost (Bubble Size = Shipped Volume)
          </h4>
        </div>
        <div className="h-[260px] w-full">
          <ResponsiveContainer width="100%" height="100%">
            <ScatterChart margin={{ top: 12, right: 24, left: 8, bottom: 12 }}>
              <CartesianGrid
                strokeDasharray="3 3"
                className="stroke-slate-100 dark:stroke-slate-800"
              />
              <XAxis
                dataKey="distance_km"
                name="Distance"
                unit=" km"
                type="number"
                tick={{ fontSize: 11 }}
                className="fill-slate-600 dark:fill-slate-400"
                label={{
                  value: "Distance (km)",
                  position: "insideBottom",
                  offset: -4,
                  style: { fontSize: 10, fill: "#64748b" },
                }}
              />
              <YAxis
                dataKey="transport_cost"
                name="Transport cost"
                type="number"
                tickFormatter={(v: number) => `${v} DT`}
                tick={{ fontSize: 11 }}
                className="fill-slate-600 dark:fill-slate-400"
                label={{
                  value: "Transport Cost (DT)",
                  angle: -90,
                  position: "insideLeft",
                  style: { fontSize: 10, fill: "#64748b" },
                }}
              />
              <ZAxis dataKey="allocated_kg" range={[150, 800]} name="Volume" />
              <Tooltip content={<BubbleTooltipContent />} />
              <Scatter data={chartData} name="Buyers">
                {chartData.map((entry, idx) => (
                  <Cell
                    key={`bubble-${idx}`}
                    fill={entry.color}
                    fillOpacity={0.8}
                    stroke={entry.color}
                    strokeWidth={2}
                  />
                ))}
              </Scatter>
            </ScatterChart>
          </ResponsiveContainer>
        </div>

        {/* Legend pills for buyers */}
        <div className="mt-3 flex flex-wrap gap-3 text-xs text-slate-600 dark:text-slate-400">
          {chartData.map((b) => (
            <span key={b.buyer_name} className="flex items-center gap-1.5">
              <span className="h-2.5 w-2.5 rounded-full" style={{ backgroundColor: b.color }} />
              {b.buyer_name} ({b.distance_km} km)
            </span>
          ))}
        </div>
      </div>

      {/* KPI Cards */}
      <div className="grid grid-cols-2 gap-3 border-t border-slate-100 pt-4 sm:grid-cols-4 dark:border-slate-800">
        <div className="min-w-0 rounded-xl bg-slate-50 p-2.5 dark:bg-slate-800/60">
          <p className="text-[10px] font-medium uppercase leading-tight text-slate-400">
            Total Shipped
          </p>
          <p className="mt-1 break-words font-mono text-sm font-bold tabular-nums text-blue-600 sm:text-base dark:text-blue-400">
            {formatKg(totalShipped)}
          </p>
        </div>

        <div className="min-w-0 rounded-xl bg-slate-50 p-2.5 dark:bg-slate-800/60">
          <p className="text-[10px] font-medium uppercase leading-tight text-slate-400">
            Total Freight Cost
          </p>
          <p className="mt-1 break-words font-mono text-sm font-bold tabular-nums text-amber-600 sm:text-base dark:text-amber-400">
            {formatCurrency(totalTransportCost)}
          </p>
        </div>

        <div className="min-w-0 rounded-xl bg-slate-50 p-2.5 dark:bg-slate-800/60">
          <p className="text-[10px] font-medium uppercase leading-tight text-slate-400">
            Avg Transport / kg
          </p>
          <p className="mt-1 break-words font-mono text-sm font-bold tabular-nums text-slate-800 sm:text-base dark:text-slate-200">
            {totalShipped > 0 ? formatCurrency(totalTransportCost / totalShipped) : "0.00 DT"}/kg
          </p>
        </div>

        <div className="min-w-0 rounded-xl bg-slate-50 p-2.5 dark:bg-slate-800/60">
          <p className="text-[10px] font-medium uppercase leading-tight text-slate-400">
            Net Optimized Profit
          </p>
          <p className="mt-1 break-words font-mono text-sm font-bold tabular-nums text-success sm:text-base">
            {formatCurrency(totalProfit)}
          </p>
        </div>
      </div>
    </div>
  );
}

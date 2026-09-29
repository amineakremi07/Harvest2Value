"use client";

import React, { useState, useEffect, useMemo } from "react";
import {
  Sankey,
  Tooltip,
  ResponsiveContainer,
  Layer,
  Rectangle,
} from "recharts";

// ============================================================================
// Types (aligned with backend OptimizeResponse and data/schema.json)
// ============================================================================

export interface AllocationDetail {
  buyer_name: string;
  allocated_kg: number;
  unit_price?: number;
  revenue?: number;
  transport_cost?: number;
  net_profit?: number;
  distance_km?: number;
}

export interface OptimizeResult {
  total_harvest_kg?: number;
  harvest_kg?: number;
  allocated_kg?: number;
  stored_kg?: number;
  wasted_kg?: number;
  allocation?: Record<string, AllocationDetail> | AllocationDetail[];
}

export interface SankeyChartProps {
  /** Full or partial OptimizeResponse */
  result?: OptimizeResult | null;
  /** Direct props (optional overrides / flexible interface) */
  harvest_kg?: number;
  allocation?: Record<string, AllocationDetail> | AllocationDetail[];
  stored_kg?: number;
  wasted_kg?: number;
  className?: string;
}

// ============================================================================
// Palette & Theme Constants
// ============================================================================

const COLORS = {
  harvest: "#16a34a",    // green-600
  harvestLink: "#86efac",// green-300
  buyer: "#2563eb",      // blue-600
  stored: "#f59e0b",     // amber-500
  storedLink: "#fcd34d", // amber-300
  wasted: "#ef4444",     // red-500
  wastedLink: "#fca5a5", // red-300
  linkDefault: "#cbd5e1",// slate-300
};

const BUYER_SHADES = [
  "#2563eb", // blue-600
  "#0284c7", // sky-600
  "#0d9488", // teal-600
  "#4f46e5", // indigo-600
  "#7c3aed", // violet-600
  "#0891b2", // cyan-600
];

// ============================================================================
// Custom Node Renderer
// ============================================================================

interface SankeyNodeProps {
  x: number;
  y: number;
  width: number;
  height: number;
  index: number;
  payload: {
    name: string;
    color: string;
    value: number;
    percent?: number;
  };
}

function SankeyCustomNode({ x, y, width, height, index, payload }: SankeyNodeProps) {
  // Prevent rendering outside bounds or invalid coords
  if (isNaN(x) || isNaN(y) || isNaN(width) || isNaN(height) || height <= 0) {
    return null;
  }

  const isSource = index === 0;

  return (
    <Layer key={`sankey-node-${index}`}>
      <Rectangle
        x={x}
        y={y}
        width={width}
        height={height}
        fill={payload.color || COLORS.buyer}
        fillOpacity={0.9}
        rx={4}
        ry={4}
      />
      <text
        x={isSource ? x - 8 : x + width + 8}
        y={y + height / 2}
        textAnchor={isSource ? "end" : "start"}
        dominantBaseline="central"
        className="fill-slate-800 text-xs font-semibold dark:fill-slate-100"
        fontSize={12}
      >
        {payload.name}
      </text>
    </Layer>
  );
}

// ============================================================================
// Custom Tooltip with kg + Percentage
// ============================================================================

interface TooltipPayloadItem {
  payload: {
    source?: { name: string };
    target?: { name: string };
    name?: string;
    value: number;
    sourceName?: string;
    targetName?: string;
    percent?: number;
  };
}

function SankeyCustomTooltip({
  active,
  payload,
  totalHarvest,
}: {
  active?: boolean;
  payload?: TooltipPayloadItem[];
  totalHarvest: number;
}) {
  if (!active || !payload || payload.length === 0) return null;

  const data = payload[0].payload;
  const sourceName = data.source?.name || data.sourceName || "Harvest";
  const targetName = data.target?.name || data.targetName || data.name || "";
  const value = data.value || 0;
  const percent = totalHarvest > 0 ? ((value / totalHarvest) * 100).toFixed(1) : "0.0";

  return (
    <div className="z-50 min-w-[200px] rounded-lg border border-card-border bg-white/95 p-3 shadow-xl backdrop-blur-sm dark:border-slate-700 dark:bg-slate-900/95">
      <div className="mb-1 flex items-center justify-between gap-2 border-b border-slate-100 pb-1.5 dark:border-slate-800">
        <span className="text-xs font-semibold uppercase tracking-wider text-slate-500 dark:text-slate-400">
          Flow Details
        </span>
        <span className="rounded bg-emerald-50 px-1.5 py-0.5 text-xs font-bold text-emerald-600 dark:bg-emerald-950/60 dark:text-emerald-400">
          {percent}% of harvest
        </span>
      </div>
      <p className="mt-1 text-xs text-slate-600 dark:text-slate-300">
        <span className="font-semibold text-slate-900 dark:text-white">{sourceName}</span>
        {" → "}
        <span className="font-semibold text-slate-900 dark:text-white">{targetName}</span>
      </p>
      <p className="mt-1.5 text-base font-bold text-slate-900 dark:text-white">
        {value.toLocaleString()} <span className="text-xs font-normal text-slate-500">kg</span>
      </p>
    </div>
  );
}

// ============================================================================
// Main SankeyChart Component
// ============================================================================

export default function SankeyChart({
  result,
  harvest_kg: propHarvest,
  allocation: propAllocation,
  stored_kg: propStored,
  wasted_kg: propWasted,
  className = "",
}: SankeyChartProps) {
  // SSR hydration protection
  const [mounted, setMounted] = useState(false);

  useEffect(() => {
    setMounted(true);
  }, []);

  // Normalize inputs across prop styles
  const totalHarvest = propHarvest ?? result?.total_harvest_kg ?? result?.harvest_kg ?? 0;
  const storedKg = propStored ?? result?.stored_kg ?? 0;
  const wastedKg = propWasted ?? result?.wasted_kg ?? 0;

  const rawAllocation = propAllocation ?? result?.allocation ?? {};
  const allocationList: AllocationDetail[] = useMemo(() => {
    if (Array.isArray(rawAllocation)) {
      return rawAllocation;
    }
    return Object.values(rawAllocation);
  }, [rawAllocation]);

  // Build Sankey Nodes & Links
  const sankeyData = useMemo(() => {
    const activeBuyers = allocationList.filter((a) => (a.allocated_kg || 0) > 0);
    const totalAllocated = activeBuyers.reduce((acc, b) => acc + b.allocated_kg, 0);

    const hasFlows = totalAllocated > 0 || storedKg > 0 || wastedKg > 0;
    if (!hasFlows || totalHarvest <= 0) {
      return null;
    }

    // Node 0: Harvest (Source)
    const nodes: Array<{ name: string; color: string; value: number }> = [
      {
        name: `Harvest (${totalHarvest.toLocaleString()} kg)`,
        color: COLORS.harvest,
        value: totalHarvest,
      },
    ];

    const links: Array<{ source: number; target: number; value: number }> = [];

    // Buyer Nodes & Links
    activeBuyers.forEach((buyer, idx) => {
      const nodeIndex = nodes.length;
      const buyerColor = BUYER_SHADES[idx % BUYER_SHADES.length];
      nodes.push({
        name: buyer.buyer_name,
        color: buyerColor,
        value: buyer.allocated_kg,
      });
      links.push({
        source: 0,
        target: nodeIndex,
        value: buyer.allocated_kg,
      });
    });

    // Stored Node & Link
    if (storedKg > 0) {
      const storedIdx = nodes.length;
      nodes.push({
        name: `Storage (${storedKg.toLocaleString()} kg)`,
        color: COLORS.stored,
        value: storedKg,
      });
      links.push({
        source: 0,
        target: storedIdx,
        value: storedKg,
      });
    }

    // Wasted Node & Link
    if (wastedKg > 0) {
      const wastedIdx = nodes.length;
      nodes.push({
        name: `Waste (${wastedKg.toLocaleString()} kg)`,
        color: COLORS.wasted,
        value: wastedKg,
      });
      links.push({
        source: 0,
        target: wastedIdx,
        value: wastedKg,
      });
    }

    if (links.length === 0) return null;

    return { nodes, links };
  }, [totalHarvest, allocationList, storedKg, wastedKg]);

  // ---- Fallback / Empty State ----
  if (!mounted || !sankeyData) {
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
              d="M7 16V4m0 0L3 8m4-4l4 4m6 0v12m0 0l4-4m-4 4l-4-4"
            />
          </svg>
        </div>
        <h4 className="text-sm font-semibold text-slate-700 dark:text-slate-200">
          No Harvest Flow Data
        </h4>
        <p className="mt-1 max-w-sm text-xs text-slate-500 dark:text-slate-400">
          Run the optimizer with a valid crop harvest volume to visualize distribution across buyers, storage, and waste.
        </p>
      </div>
    );
  }

  const activeAllocatedTotal = allocationList.reduce((sum, b) => sum + (b.allocated_kg || 0), 0);

  return (
    <div
      className={`flex flex-col rounded-2xl border border-card-border bg-white p-6 shadow-sm dark:border-slate-800 dark:bg-slate-900 ${className}`}
    >
      {/* Header */}
      <div className="mb-4 flex flex-wrap items-center justify-between gap-2">
        <div>
          <h3 className="text-base font-semibold text-slate-900 dark:text-white">
            Harvest Allocation Flow (Sankey)
          </h3>
          <p className="text-xs text-slate-500 dark:text-slate-400">
            End-to-end distribution from harvest to buyer fulfillment and storage
          </p>
        </div>
        <div className="flex items-center gap-2">
          <span className="inline-flex items-center gap-1.5 rounded-full bg-emerald-50 px-3 py-1 text-xs font-medium text-emerald-700 dark:bg-emerald-950/60 dark:text-emerald-300">
            <span className="h-1.5 w-1.5 rounded-full bg-emerald-500" />
            {totalHarvest.toLocaleString()} kg Total
          </span>
        </div>
      </div>

      {/* Sankey Chart Container */}
      <div className="h-[360px] w-full">
        <ResponsiveContainer width="100%" height="100%">
          <Sankey
            data={sankeyData}
            node={(props: any) => <SankeyCustomNode {...props} />}
            link={{ stroke: COLORS.linkDefault, strokeOpacity: 0.45 }}
            nodePadding={28}
            nodeWidth={14}
            margin={{ top: 20, right: 160, bottom: 20, left: 140 }}
          >
            <Tooltip content={<SankeyCustomTooltip totalHarvest={totalHarvest} />} />
          </Sankey>
        </ResponsiveContainer>
      </div>

      {/* Summary KPI Pills */}
      <div className="mt-4 grid grid-cols-2 gap-2 border-t border-slate-100 pt-4 sm:grid-cols-4 dark:border-slate-800">
        <div className="rounded-lg bg-slate-50 p-2.5 dark:bg-slate-800/60">
          <p className="text-[11px] font-medium text-slate-500 dark:text-slate-400">Sold to Buyers</p>
          <p className="mt-0.5 text-sm font-bold text-blue-600 dark:text-blue-400">
            {activeAllocatedTotal.toLocaleString()} kg
            <span className="ml-1 text-[11px] font-normal text-slate-400">
              ({totalHarvest > 0 ? ((activeAllocatedTotal / totalHarvest) * 100).toFixed(0) : 0}%)
            </span>
          </p>
        </div>

        <div className="rounded-lg bg-slate-50 p-2.5 dark:bg-slate-800/60">
          <p className="text-[11px] font-medium text-slate-500 dark:text-slate-400">Stored in Buffer</p>
          <p className="mt-0.5 text-sm font-bold text-amber-600 dark:text-amber-400">
            {storedKg.toLocaleString()} kg
            <span className="ml-1 text-[11px] font-normal text-slate-400">
              ({totalHarvest > 0 ? ((storedKg / totalHarvest) * 100).toFixed(0) : 0}%)
            </span>
          </p>
        </div>

        <div className="rounded-lg bg-slate-50 p-2.5 dark:bg-slate-800/60">
          <p className="text-[11px] font-medium text-slate-500 dark:text-slate-400">Post-Harvest Waste</p>
          <p className={`mt-0.5 text-sm font-bold ${wastedKg > 0 ? "text-red-600 dark:text-red-400" : "text-success"}`}>
            {wastedKg.toLocaleString()} kg
            <span className="ml-1 text-[11px] font-normal text-slate-400">
              ({totalHarvest > 0 ? ((wastedKg / totalHarvest) * 100).toFixed(0) : 0}%)
            </span>
          </p>
        </div>

        <div className="rounded-lg bg-slate-50 p-2.5 dark:bg-slate-800/60">
          <p className="text-[11px] font-medium text-slate-500 dark:text-slate-400">Active Buyers</p>
          <p className="mt-0.5 text-sm font-bold text-slate-800 dark:text-slate-200">
            {allocationList.filter((b) => (b.allocated_kg || 0) > 0).length}
            <span className="ml-1 text-[11px] font-normal text-slate-400">
              / {allocationList.length || 0}
            </span>
          </p>
        </div>
      </div>

      {/* Legend */}
      <div className="mt-3 flex flex-wrap items-center justify-between gap-3 text-xs text-slate-500 dark:text-slate-400">
        <div className="flex flex-wrap items-center gap-4">
          <span className="flex items-center gap-1.5">
            <span className="h-2.5 w-2.5 rounded-full" style={{ background: COLORS.harvest }} />
            Harvest Source
          </span>
          <span className="flex items-center gap-1.5">
            <span className="h-2.5 w-2.5 rounded-full" style={{ background: COLORS.buyer }} />
            Buyer Destinations
          </span>
          <span className="flex items-center gap-1.5">
            <span className="h-2.5 w-2.5 rounded-full" style={{ background: COLORS.stored }} />
            Cold / Dry Storage
          </span>
          <span className="flex items-center gap-1.5">
            <span className="h-2.5 w-2.5 rounded-full" style={{ background: COLORS.wasted }} />
            Waste / Unallocated
          </span>
        </div>
      </div>
    </div>
  );
}

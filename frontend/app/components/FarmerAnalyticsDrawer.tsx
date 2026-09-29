"use client";

import { useMemo } from "react";
import { Bar, BarChart, CartesianGrid, Legend, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import { AlertTriangle, CheckCircle2, Lightbulb, Pencil } from "lucide-react";
import CropDistributionCard from "@/app/components/CropDistributionCard";
import DeltaBadge from "@/app/components/DeltaBadge";
import Modal from "@/app/components/Modal";
import { decimalFormatter, glassCard, numberFormatter } from "@/app/components/styles";
import { KIND_LABEL, fillTone } from "@/app/components/StorageRiskCard";
import {
  RISK_LABEL,
  planReallocation,
  projectedFillPct,
  recommendFor,
  type RiskLevel,
} from "@/app/lib/reallocation";
import {
  CURRENT_PERIOD,
  farmerDelta,
  pctChange,
  snapshotFromCrops,
  wastePercent,
  type Farmer,
  type StorageFacility,
} from "@/types";

const TICK = { fill: "var(--text-secondary)", fontSize: 12 };
const TOOLTIP_STYLE = {
  background: "var(--card-surface)",
  border: "1px solid var(--card-border)",
  borderRadius: 12,
  color: "var(--text-primary)",
  fontSize: 12,
};

const RISK_CLASS: Record<RiskLevel, string> = {
  high: "border-danger/40 bg-danger/10 text-danger",
  medium: "border-warning/40 bg-warning/10 text-text-primary",
  low: "border-success/40 bg-success/10 text-success",
};

interface FarmerAnalyticsDrawerProps {
  /** Farmer to show; `null` keeps the drawer closed. */
  farmer: Farmer | null;
  /** Everyone in the same delegation, so the plan competes for shared capacity. */
  farmers: Farmer[];
  facilities: StorageFacility[];
  onClose: () => void;
  onEdit: (farmer: Farmer) => void;
}

export default function FarmerAnalyticsDrawer({
  farmer,
  farmers,
  facilities,
  onClose,
  onEdit,
}: FarmerAnalyticsDrawerProps) {
  const plan = useMemo(() => planReallocation(farmers, facilities), [farmers, facilities]);

  return (
    <Modal open={farmer !== null} onClose={onClose} title={farmer ? `${farmer.name} — Analytics` : "Farmer analytics"} variant="drawer">
      {farmer && <DrawerBody farmer={farmer} facilities={facilities} plan={plan} onEdit={onEdit} />}
    </Modal>
  );
}

function DrawerBody({
  farmer,
  facilities,
  plan,
  onEdit,
}: {
  farmer: Farmer;
  facilities: StorageFacility[];
  plan: ReturnType<typeof planReallocation>;
  onEdit: (farmer: Farmer) => void;
}) {
  const rec = recommendFor(farmer, plan);
  const delta = farmerDelta(farmer);
  const now = snapshotFromCrops(farmer.crops, CURRENT_PERIOD);
  const onFarmFill = farmer.storageCapacityKg > 0 ? (now.yieldKg / farmer.storageCapacityKg) * 100 : 0;

  // Quarter-over-quarter gains: income change, and waste *reduction* (waste falling = positive).
  const series = [...farmer.history, now];
  const qoq = series.slice(1).map((s, i) => {
    const prev = series[i];
    const income = pctChange(s.incomeTnd, prev.incomeTnd);
    const waste = pctChange(s.wasteKg, prev.wasteKg);
    return {
      period: s.period,
      income: income === null ? 0 : Number(income.toFixed(1)),
      wasteReduction: waste === null ? 0 : Number((-waste).toFixed(1)),
    };
  });

  const allocation = [...new Set(rec.transfers.map((t) => t.facilityId))].map((id) => {
    const facility = facilities.find((f) => f.id === id);
    const items = rec.transfers.filter((t) => t.facilityId === id);
    return { facility, kg: items.reduce((s, t) => s + t.kg, 0) };
  });

  return (
    <div className="space-y-4">
      <div className="flex flex-wrap items-center gap-2 text-sm">
        <span className="text-text-secondary">This period vs previous:</span>
        <DeltaBadge label="Income change" delta={delta.income} />
        <DeltaBadge label="Waste change" delta={delta.waste} />
        <button
          type="button"
          onClick={() => onEdit(farmer)}
          className="ml-auto inline-flex items-center gap-1.5 rounded-full border border-card-border px-3 py-1.5 text-xs font-semibold text-accent-text outline-none hover:border-accent/50 focus-visible:ring-2 focus-visible:ring-accent"
        >
          <Pencil className="h-3.5 w-3.5" aria-hidden="true" /> Edit farmer
        </button>
      </div>

      {/* Recommendation */}
      <section aria-label="Recommendation" className={`rounded-2xl border p-4 ${RISK_CLASS[rec.risk]}`}>
        <div className="mb-1 flex items-center gap-2 text-xs font-bold uppercase tracking-wider">
          {rec.risk === "low" ? (
            <CheckCircle2 className="h-4 w-4" aria-hidden="true" />
          ) : (
            <AlertTriangle className="h-4 w-4" aria-hidden="true" />
          )}
          {RISK_LABEL[rec.risk]} · AI Recommendation
        </div>
        <p className="flex gap-2 text-sm leading-relaxed text-text-primary">
          <Lightbulb className="mt-0.5 h-4 w-4 shrink-0" aria-hidden="true" />
          <span>{rec.headline}</span>
        </p>
        <p className="mt-2 text-xs text-text-secondary">
          Rule-based estimate from waste rate and free facility capacity, not yet from the solver.
        </p>
      </section>

      {/* Yield breakdown */}
      <CropDistributionCard farmers={[farmer]} title="Individual Yield Breakdown" />

      {/* Performance */}
      <section aria-labelledby="perf-title" className={glassCard}>
        <h3 id="perf-title" className="mb-1 text-sm font-semibold uppercase tracking-wider text-text-secondary">
          Spoilage &amp; Income Performance
        </h3>
        <p className="mb-3 text-xs text-text-secondary">
          Quarter over quarter. Waste reduction is positive when waste falls.
        </p>
        <div className="h-[220px]" role="img" aria-label="Bar chart of quarterly income gain and waste reduction">
          <ResponsiveContainer width="100%" height="100%">
            <BarChart data={qoq} margin={{ top: 8, right: 8, bottom: 0, left: 0 }}>
              <CartesianGrid stroke="var(--card-border)" strokeDasharray="3 3" />
              <XAxis dataKey="period" tick={TICK} stroke="var(--card-border)" />
              <YAxis tick={TICK} stroke="var(--card-border)" unit="%" />
              <Tooltip contentStyle={TOOLTIP_STYLE} formatter={(v) => `${v}%`} />
              <Legend wrapperStyle={{ fontSize: 12 }} />
              <Bar dataKey="income" name="Income gain %" fill="var(--accent-text)" radius={[4, 4, 0, 0]} />
              <Bar dataKey="wasteReduction" name="Waste reduction %" fill="var(--success)" radius={[4, 4, 0, 0]} />
            </BarChart>
          </ResponsiveContainer>
        </div>
        <p className="mt-2 font-mono text-xs tabular-nums text-text-secondary">
          Current waste {decimalFormatter.format(wastePercent(now.yieldKg, now.wasteKg))}% · income{" "}
          {numberFormatter.format(now.incomeTnd)} TND
        </p>
      </section>

      {/* Storage */}
      <section aria-labelledby="alloc-title" className={glassCard}>
        <h3 id="alloc-title" className="mb-3 text-sm font-semibold uppercase tracking-wider text-text-secondary">
          Storage Allocation Status
        </h3>
        <p className="mb-3 text-sm text-text-primary">
          On-farm storage:{" "}
          <span className="font-mono tabular-nums">
            {decimalFormatter.format(now.yieldKg / 1000)} t harvested / {decimalFormatter.format(farmer.storageCapacityKg / 1000)} t capacity
          </span>{" "}
          <span className={onFarmFill > 100 ? "font-semibold text-danger" : "text-text-secondary"}>
            ({Math.round(onFarmFill)}%{onFarmFill > 100 ? ", overflow" : ""})
          </span>
        </p>

        {allocation.length === 0 ? (
          <p className="text-sm text-text-secondary">No facility allocation recommended.</p>
        ) : (
          <ul className="space-y-3">
            {allocation.map(({ facility, kg }) => {
              if (!facility) return null;
              const pct = projectedFillPct(facility, kg);
              const tone = fillTone(pct);
              return (
                <li key={facility.id} className="rounded-xl border border-card-border p-3">
                  <div className="flex flex-wrap items-baseline justify-between gap-2 text-sm">
                    <span className="font-semibold text-text-primary">
                      {facility.name} <span className="text-xs font-normal text-text-secondary">· {KIND_LABEL[facility.kind]}</span>
                    </span>
                    <span className="font-mono text-xs tabular-nums text-text-secondary">
                      +{decimalFormatter.format(kg / 1000)} t → {Math.round(pct)}% full · {tone.label}
                    </span>
                  </div>
                  <div className="mt-2 h-2 overflow-hidden rounded-full bg-card-border" aria-hidden="true">
                    <div className={`h-full rounded-full ${tone.bar}`} style={{ width: `${Math.min(pct, 100)}%` }} />
                  </div>
                </li>
              );
            })}
          </ul>
        )}
        <p className="mt-3 text-xs text-text-secondary">
          Recommended allocation. Which facility currently holds this farmer&apos;s stock isn&apos;t tracked yet.
        </p>
      </section>
    </div>
  );
}

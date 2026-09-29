"use client";

import type { ReactNode } from "react";

import { ArrowDown, ArrowUp, BarChart3, Pencil } from "lucide-react";
import { KIND_LABEL, fillTone } from "@/app/components/StorageRiskCard";
import { decimalFormatter, numberFormatter } from "@/app/components/styles";
import { RISK_LABEL, recommendFor, type Plan, type RiskLevel } from "@/app/lib/reallocation";
import {
  CROPS,
  CROP_COLORS,
  CROP_TYPES,
  CURRENT_PERIOD,
  facilityFillPct,
  snapshotFromCrops,
  type Farmer,
  type StorageFacility,
} from "@/types";

const RISK_CLASS: Record<RiskLevel, string> = {
  high: "bg-danger/15 text-danger",
  medium: "bg-warning/20 text-text-primary",
  low: "bg-success/15 text-success",
};

interface FarmerQuickPanelProps {
  farmer: Farmer;
  plan: Plan;
  facilities: StorageFacility[];
  onEdit: (farmer: Farmer) => void;
  onOpenFull: (farmer: Farmer) => void;
}

function Metric({ label, children }: { label: string; children: ReactNode }) {
  return (
    <div className="rounded-xl border border-card-border bg-card-surface p-3">
      <p className="mb-1 text-xs font-semibold text-text-secondary">{label}</p>
      {children}
    </div>
  );
}

/** Compact inline analytics shown under a farmer's table row. */
export default function FarmerQuickPanel({ farmer, plan, facilities, onEdit, onOpenFull }: FarmerQuickPanelProps) {
  const now = snapshotFromCrops(farmer.crops, CURRENT_PERIOD);
  const prev = farmer.history[farmer.history.length - 1];
  const rec = recommendFor(farmer, plan);

  // Change versus the previous period, in kg of waste and TND of income.
  const wasteDelta = prev ? now.wasteKg - prev.wasteKg : null; // negative = waste fell
  const incomeDelta = prev ? now.incomeTnd - prev.incomeTnd : null;
  const potentialKg = rec.transfers.reduce((s, t) => s + t.avoidedWasteKg, 0);

  const topTransfer = rec.transfers[0];
  const facility = topTransfer ? facilities.find((f) => f.id === topTransfer.facilityId) : undefined;
  const fillPct = facility ? facilityFillPct(facility) : 0;
  const tone = fillTone(fillPct);

  const slices = CROP_TYPES.map((crop) => ({
    crop,
    kg: farmer.crops.filter((c) => c.crop === crop).reduce((s, c) => s + c.yieldKg, 0),
  })).filter((s) => s.kg > 0);
  const total = slices.reduce((s, x) => s + x.kg, 0);

  return (
    <div className="grid gap-3 py-2 md:grid-cols-2 xl:grid-cols-4">
      <Metric label="Waste reduction vs previous period">
        {wasteDelta === null ? (
          <p className="text-sm text-text-secondary">No previous period</p>
        ) : (
          <p className={`flex items-center gap-1.5 font-mono text-lg font-bold tabular-nums ${wasteDelta <= 0 ? "text-success" : "text-danger"}`}>
            {wasteDelta <= 0 ? <ArrowDown className="h-4 w-4" aria-hidden="true" /> : <ArrowUp className="h-4 w-4" aria-hidden="true" />}
            {numberFormatter.format(Math.abs(wasteDelta))} kg
            <span className="font-sans text-xs font-normal text-text-secondary">
              {wasteDelta <= 0 ? "waste saved" : "more waste"}
            </span>
          </p>
        )}
        {potentialKg > 0 && (
          <p className="mt-1 text-xs text-text-secondary">
            Up to ~{numberFormatter.format(potentialKg)} kg more with the recommended transfers.
          </p>
        )}
      </Metric>

      <Metric label="Income performance">
        {incomeDelta === null ? (
          <p className="text-sm text-text-secondary">No previous period</p>
        ) : (
          <p className={`font-mono text-lg font-bold tabular-nums ${incomeDelta >= 0 ? "text-success" : "text-danger"}`}>
            {incomeDelta >= 0 ? "+" : "−"}
            {numberFormatter.format(Math.abs(incomeDelta))} TND
            <span className="ml-1.5 font-sans text-xs font-normal text-text-secondary">income</span>
          </p>
        )}
        <p className="mt-1 font-mono text-xs tabular-nums text-text-secondary">
          Now {numberFormatter.format(now.incomeTnd)} TND
        </p>
      </Metric>

      <Metric label="Crop breakdown">
        <div
          role="img"
          aria-label={`Crop breakdown: ${slices.map((s) => `${CROPS[s.crop].label} ${Math.round((s.kg / total) * 100)}%`).join(", ")}`}
          className="flex h-3 overflow-hidden rounded-full bg-card-border"
        >
          {slices.map((s) => (
            <span key={s.crop} style={{ width: `${(s.kg / total) * 100}%`, backgroundColor: CROP_COLORS[s.crop] }} />
          ))}
        </div>
        <ul className="mt-2 space-y-0.5 text-xs">
          {slices.map((s) => (
            <li key={s.crop} className="flex justify-between gap-2">
              <span className="flex items-center gap-1.5 text-text-primary">
                <span className="h-2 w-2 rounded-full" style={{ backgroundColor: CROP_COLORS[s.crop] }} aria-hidden="true" />
                {CROPS[s.crop].label}
              </span>
              <span className="font-mono tabular-nums text-text-secondary">{Math.round((s.kg / total) * 100)}%</span>
            </li>
          ))}
        </ul>
      </Metric>

      <Metric label="Storage & risk">
        <p className="mb-1.5">
          <span className={`inline-flex rounded-full px-2 py-0.5 text-xs font-semibold ${RISK_CLASS[rec.risk]}`}>
            {RISK_LABEL[rec.risk]}
          </span>
        </p>
        {facility ? (
          <p className="text-sm text-text-primary">
            {facility.name}
            <span className="block text-xs text-text-secondary">
              {KIND_LABEL[facility.kind]} · {decimalFormatter.format(fillPct)}% full · {tone.label}
            </span>
            <span className="block text-xs text-text-secondary">Recommended facility</span>
          </p>
        ) : (
          <p className="text-sm text-text-secondary">No facility transfer recommended.</p>
        )}
      </Metric>

      <div className="flex flex-wrap gap-2 md:col-span-2 xl:col-span-4">
        <button
          type="button"
          onClick={() => onOpenFull(farmer)}
          className="inline-flex items-center gap-1.5 rounded-full border border-card-border px-4 py-1.5 text-xs font-semibold text-accent-text outline-none hover:border-accent/50 focus-visible:ring-2 focus-visible:ring-accent"
        >
          <BarChart3 className="h-3.5 w-3.5" aria-hidden="true" /> Full analytics
        </button>
        <button
          type="button"
          onClick={() => onEdit(farmer)}
          className="inline-flex items-center gap-1.5 rounded-full bg-accent px-4 py-1.5 text-xs font-bold text-white outline-none hover:bg-accent-hover focus-visible:ring-2 focus-visible:ring-accent"
        >
          <Pencil className="h-3.5 w-3.5" aria-hidden="true" /> Quick edit
        </button>
      </div>
    </div>
  );
}

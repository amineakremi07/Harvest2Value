// Frontend planner for regional harvest reallocation. This is a transparent,
// rule-based ESTIMATE, not the multi-crop MILP solver (that lives on the backend
// branch and is not connected yet). See BACKEND_HANDOFF.md §3.
//
// Model, in one paragraph: each crop has a baseline spoilage rate
// (waste ÷ yield). A share of every harvest sits outside a proper cold chain
// (TRANSFER_SHARE, by perishability). The planner moves that share into regional
// facilities, riskiest crops first, choosing the facility type that best
// protects the crop (RECOVERY) among those with free capacity. Storing a crop
// in a matching facility avoids RECOVERY × its spoilage rate on the moved kg.

import {
  CROPS,
  CURRENT_PERIOD,
  facilityFillPct,
  snapshotFromCrops,
  wastePercent,
  type CropType,
  type FacilityKind,
  type Farmer,
  type Perishability,
  type StorageFacility,
} from "@/types";

/** Share of a harvest assumed to be stored outside a proper cold chain. */
const TRANSFER_SHARE: Record<Perishability, number> = {
  perishable: 0.4,
  semi_perishable: 0.3,
  durable: 0.15,
};

/** Fraction of spoilage avoided when a crop is held in each facility type. */
const RECOVERY: Record<FacilityKind, Record<Perishability, number>> = {
  cold_storage: { perishable: 0.75, semi_perishable: 0.6, durable: 0.2 },
  silo: { perishable: 0.05, semi_perishable: 0.05, durable: 0.7 },
  warehouse: { perishable: 0.1, semi_perishable: 0.3, durable: 0.5 },
};

/** How soon the transfer should happen, by perishability. */
const URGENCY_HOURS: Record<Perishability, number> = {
  perishable: 48,
  semi_perishable: 168,
  durable: 720,
};

export interface Transfer {
  farmerId: string;
  farmerName: string;
  crop: CropType;
  kg: number;
  facilityId: string;
  facilityName: string;
  facilityKind: FacilityKind;
  urgencyHours: number;
  avoidedWasteKg: number;
  avoidedIncomeTnd: number;
}

export interface PlanTotals {
  yieldKg: number;
  wasteKg: number;
  wastePct: number;
  incomeTnd: number;
}

export interface Plan {
  transfers: Transfer[];
  baseline: PlanTotals;
  optimized: PlanTotals;
  avoidedWasteKg: number;
  /** Extra income as a percentage of baseline income. */
  incomeGainPct: number;
}

export function formatUrgency(hours: number): string {
  return hours <= 72 ? `${hours}h` : `${Math.round(hours / 24)} days`;
}

export function planReallocation(farmers: Farmer[], facilities: StorageFacility[]): Plan {
  const free = new Map(facilities.map((f) => [f.id, Math.max(0, f.maxCapacityKg - f.currentStockKg)]));

  const candidates = farmers.flatMap((farmer) =>
    farmer.crops
      .filter((c) => c.yieldKg > 0)
      .map((c) => ({
        farmer,
        crop: c,
        perishability: CROPS[c.crop].perishability,
        rate: c.wasteKg / c.yieldKg,
      })),
  );
  // Highest spoilage risk first, so scarce facility space goes where it saves most.
  candidates.sort((a, b) => b.rate - a.rate);

  const transfers: Transfer[] = [];
  for (const { farmer, crop, perishability, rate } of candidates) {
    let remaining = Math.round(crop.yieldKg * TRANSFER_SHARE[perishability]);
    while (remaining > 0) {
      const options = facilities
        .filter((f) => (free.get(f.id) ?? 0) > 0)
        .sort(
          (a, b) =>
            RECOVERY[b.kind][perishability] - RECOVERY[a.kind][perishability] ||
            (free.get(b.id) ?? 0) - (free.get(a.id) ?? 0),
        );
      const facility = options[0];
      if (!facility || RECOVERY[facility.kind][perishability] <= 0.05) break; // nowhere useful left
      const kg = Math.min(remaining, free.get(facility.id) ?? 0);
      const avoidedWasteKg = kg * rate * RECOVERY[facility.kind][perishability];
      transfers.push({
        farmerId: farmer.id,
        farmerName: farmer.name,
        crop: crop.crop,
        kg,
        facilityId: facility.id,
        facilityName: facility.name,
        facilityKind: facility.kind,
        urgencyHours: URGENCY_HOURS[perishability],
        avoidedWasteKg,
        avoidedIncomeTnd: avoidedWasteKg * (crop.incomeTnd / crop.yieldKg),
      });
      free.set(facility.id, (free.get(facility.id) ?? 0) - kg);
      remaining -= kg;
    }
  }

  const base = farmers.reduce(
    (acc, f) => {
      const s = snapshotFromCrops(f.crops, CURRENT_PERIOD);
      return { yieldKg: acc.yieldKg + s.yieldKg, wasteKg: acc.wasteKg + s.wasteKg, incomeTnd: acc.incomeTnd + s.incomeTnd };
    },
    { yieldKg: 0, wasteKg: 0, incomeTnd: 0 },
  );
  const avoidedWasteKg = transfers.reduce((s, t) => s + t.avoidedWasteKg, 0);
  const gain = transfers.reduce((s, t) => s + t.avoidedIncomeTnd, 0);
  const optimizedWaste = base.wasteKg - avoidedWasteKg;

  return {
    transfers,
    baseline: { ...base, wastePct: wastePercent(base.yieldKg, base.wasteKg) },
    optimized: {
      yieldKg: base.yieldKg,
      wasteKg: optimizedWaste,
      wastePct: wastePercent(base.yieldKg, optimizedWaste),
      incomeTnd: base.incomeTnd + gain,
    },
    avoidedWasteKg,
    incomeGainPct: base.incomeTnd > 0 ? (gain / base.incomeTnd) * 100 : 0,
  };
}

// ---- Per-farmer risk & recommendation ----

export type RiskLevel = "high" | "medium" | "low";

export const RISK_LABEL: Record<RiskLevel, string> = { high: "High Risk", medium: "Medium Risk", low: "Low Risk" };

/** Overall farmer risk from their spoilage rate: ≥6% high, ≥3.5% medium. */
export function farmerRisk(farmer: Farmer): RiskLevel {
  const s = snapshotFromCrops(farmer.crops, CURRENT_PERIOD);
  const pct = wastePercent(s.yieldKg, s.wasteKg);
  return pct >= 6 ? "high" : pct >= 3.5 ? "medium" : "low";
}

export interface Recommendation {
  risk: RiskLevel;
  headline: string;
  transfers: Transfer[];
  /** Share of this farmer's current waste the plan would avoid. */
  wasteCutPct: number;
}

const tons = (kg: number) => (kg / 1000).toFixed(1);

export function recommendFor(farmer: Farmer, plan: Plan): Recommendation {
  const risk = farmerRisk(farmer);
  const transfers = plan.transfers
    .filter((t) => t.farmerId === farmer.id)
    .sort((a, b) => b.avoidedWasteKg - a.avoidedWasteKg);
  const waste = snapshotFromCrops(farmer.crops, CURRENT_PERIOD).wasteKg;
  const avoided = transfers.reduce((s, t) => s + t.avoidedWasteKg, 0);
  const wasteCutPct = waste > 0 ? (avoided / waste) * 100 : 0;

  const top = transfers[0];
  const headline = top
    ? `${RISK_LABEL[risk]}: Divert ${tons(top.kg)} t of ${CROPS[top.crop].label} to ${top.facilityName} within ${formatUrgency(top.urgencyHours)} to prevent about ${Math.round(top.avoidedWasteKg)} kg of loss` +
      (transfers.length > 1 ? ` (${transfers.length} transfers recommended, cutting waste ${Math.round(wasteCutPct)}%).` : ` (${Math.round(wasteCutPct)}% of this farmer's waste).`)
    : `${RISK_LABEL[risk]}: no reallocation needed this period; regional storage has no better option for this farmer's crops.`;

  return { risk, headline, transfers, wasteCutPct };
}

/** Projected fill of a facility after applying `extraKg`. */
export function projectedFillPct(facility: StorageFacility, extraKg: number): number {
  return facilityFillPct({ ...facility, currentStockKg: facility.currentStockKg + extraKg });
}

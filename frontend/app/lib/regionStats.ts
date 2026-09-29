import {
  CURRENT_PERIOD,
  computeDeltaMetrics,
  facilityFillPct,
  snapshotFromCrops,
  wastePercent,
  type DeltaMetrics,
  type Delegation,
  type Farmer,
  type PeriodSnapshot,
  type StorageFacility,
} from "@/types";

export interface RegionStats {
  farmerCount: number;
  totalYieldKg: number;
  totalWasteKg: number;
  wastePct: number;
  stockKg: number;
  maxKg: number;
  availablePct: number;
  /** Facilities filled to 90% or more. */
  criticalFacilities: number;
  healthScore: number;
}

/**
 * Heuristic 0–100 health score: starts at 100, loses 4 points per percentage
 * point of harvest wasted and 0.8 per point of storage fill above 75%.
 * Placeholder until the backend analytics engine defines one.
 */
export function regionalHealthScore(wastePct: number, fillPct: number): number {
  const score = 100 - wastePct * 4 - Math.max(0, fillPct - 75) * 0.8;
  return Math.max(0, Math.min(100, Math.round(score)));
}

export function computeRegionStats(farmers: Farmer[], facilities: StorageFacility[]): RegionStats {
  const totals = farmers.reduce(
    (acc, f) => {
      const snap = snapshotFromCrops(f.crops, CURRENT_PERIOD);
      return { yieldKg: acc.yieldKg + snap.yieldKg, wasteKg: acc.wasteKg + snap.wasteKg };
    },
    { yieldKg: 0, wasteKg: 0 },
  );
  const stockKg = facilities.reduce((s, f) => s + f.currentStockKg, 0);
  const maxKg = facilities.reduce((s, f) => s + f.maxCapacityKg, 0);
  const wastePct = wastePercent(totals.yieldKg, totals.wasteKg);
  const fillPct = maxKg > 0 ? (stockKg / maxKg) * 100 : 0;

  return {
    farmerCount: farmers.length,
    totalYieldKg: totals.yieldKg,
    totalWasteKg: totals.wasteKg,
    wastePct,
    stockKg,
    maxKg,
    availablePct: maxKg > 0 ? 100 - fillPct : 0,
    criticalFacilities: facilities.filter((f) => facilityFillPct(f) >= 90).length,
    healthScore: regionalHealthScore(wastePct, fillPct),
  };
}

/** Sum every farmer's history per period, then append the current period. */
export function aggregateTrend(farmers: Farmer[]): PeriodSnapshot[] {
  const byPeriod = new Map<string, PeriodSnapshot>();
  for (const f of farmers) {
    for (const h of f.history) {
      const prev = byPeriod.get(h.period) ?? { period: h.period, yieldKg: 0, wasteKg: 0, incomeTnd: 0 };
      byPeriod.set(h.period, {
        period: h.period,
        yieldKg: prev.yieldKg + h.yieldKg,
        wasteKg: prev.wasteKg + h.wasteKg,
        incomeTnd: prev.incomeTnd + h.incomeTnd,
      });
    }
  }
  const history = [...byPeriod.values()].sort((a, b) => a.period.localeCompare(b.period));
  const current = farmers.reduce<PeriodSnapshot>(
    (acc, f) => {
      const s = snapshotFromCrops(f.crops, CURRENT_PERIOD);
      return {
        period: CURRENT_PERIOD,
        yieldKg: acc.yieldKg + s.yieldKg,
        wasteKg: acc.wasteKg + s.wasteKg,
        incomeTnd: acc.incomeTnd + s.incomeTnd,
      };
    },
    { period: CURRENT_PERIOD, yieldKg: 0, wasteKg: 0, incomeTnd: 0 },
  );
  return [...history, current];
}

export interface DelegationDelta {
  delegation: Delegation;
  farmerCount: number;
  delta: DeltaMetrics;
}

/** Current period vs the latest previous period, per delegation. */
export function delegationDeltas(delegations: Delegation[], farmers: Farmer[]): DelegationDelta[] {
  return delegations.map((delegation) => {
    const own = farmers.filter((f) => f.delegationId === delegation.id);
    const trend = aggregateTrend(own);
    const current = trend[trend.length - 1];
    const previous = trend.length > 1 ? trend[trend.length - 2] : undefined;
    return { delegation, farmerCount: own.length, delta: computeDeltaMetrics(current, previous) };
  });
}

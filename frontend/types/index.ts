// Domain types, delta helpers and local mock fixtures for the CRDA dashboard.
// Mocks are temporary: replace with backend endpoints once feature/crda-backend-ai
// publishes them. Shapes here must be reconciled with the backend Pydantic models.

// ---- Domain types ----

export type CropType = "tomatoes" | "wheat" | "olives" | "citrus";
export type Perishability = "perishable" | "semi_perishable" | "durable";
export type FacilityKind = "silo" | "cold_storage" | "warehouse";

export interface CropInfo {
  type: CropType;
  label: string;
  perishability: Perishability;
}

export interface Delegation {
  id: string;
  name: string;
  governorate: string;
}

/** Per-crop harvest for one farmer in the current period. */
export interface CropHarvest {
  crop: CropType;
  yieldKg: number;
  wasteKg: number;
  incomeTnd: number;
}

/** Aggregated farmer figures for one past period (e.g. "2026-Q2"). */
export interface PeriodSnapshot {
  period: string;
  yieldKg: number;
  wasteKg: number;
  incomeTnd: number;
}

export interface Farmer {
  id: string;
  name: string;
  delegationId: string;
  phone?: string;
  storageCapacityKg: number;
  /** Current-period harvests, one entry per crop. */
  crops: CropHarvest[];
  /** Past periods, oldest first. The current period is derived from `crops`. */
  history: PeriodSnapshot[];
}

export interface StorageFacility {
  id: string;
  name: string;
  delegationId: string;
  kind: FacilityKind;
  currentStockKg: number;
  maxCapacityKg: number;
}

export type TrendDirection = "up" | "down" | "flat";
/** Whether a change is desirable: income up is good, waste up is bad. */
export type TrendQuality = "good" | "bad" | "neutral";

export interface DeltaValue {
  /** Percent change vs the previous period; null when it cannot be computed. */
  pct: number | null;
  direction: TrendDirection;
  quality: TrendQuality;
}

export interface DeltaMetrics {
  income: DeltaValue;
  waste: DeltaValue;
}

// ---- Constants ----

export const CROPS: Record<CropType, CropInfo> = {
  tomatoes: { type: "tomatoes", label: "Tomatoes", perishability: "perishable" },
  wheat: { type: "wheat", label: "Wheat (Kamh)", perishability: "durable" },
  olives: { type: "olives", label: "Olives", perishability: "semi_perishable" },
  citrus: { type: "citrus", label: "Citrus", perishability: "semi_perishable" },
};

export const CROP_TYPES = Object.keys(CROPS) as CropType[];

/** Categorical chart colors (see DESIGN.md §1). */
export const CROP_COLORS: Record<CropType, string> = {
  tomatoes: "#F87171",
  wheat: "#FACC15",
  olives: "#A3E635",
  citrus: "#FB923C",
};

// ---- Pure helpers ----

/** Percent change from `previous` to `current`; null when previous is 0/invalid. */
export function pctChange(current: number, previous: number): number | null {
  if (!Number.isFinite(current) || !Number.isFinite(previous) || previous === 0) return null;
  return ((current - previous) / previous) * 100;
}

function toDelta(pct: number | null, higherIsBetter: boolean): DeltaValue {
  if (pct === null) return { pct: null, direction: "flat", quality: "neutral" };
  // Treat changes under 0.05% as flat so rounding to 0.0% never shows an arrow.
  if (Math.abs(pct) < 0.05) return { pct, direction: "flat", quality: "neutral" };
  const direction: TrendDirection = pct > 0 ? "up" : "down";
  const improved = (pct > 0) === higherIsBetter;
  return { pct, direction, quality: improved ? "good" : "bad" };
}

/** Δ Income (higher is better) and Δ Waste (lower is better) between two periods. */
export function computeDeltaMetrics(
  current: Pick<PeriodSnapshot, "incomeTnd" | "wasteKg">,
  previous: Pick<PeriodSnapshot, "incomeTnd" | "wasteKg"> | undefined,
): DeltaMetrics {
  if (!previous) return { income: toDelta(null, true), waste: toDelta(null, false) };
  return {
    income: toDelta(pctChange(current.incomeTnd, previous.incomeTnd), true),
    waste: toDelta(pctChange(current.wasteKg, previous.wasteKg), false),
  };
}

/** Sum a farmer's per-crop harvests into one snapshot for `period`. */
export function snapshotFromCrops(crops: CropHarvest[], period: string): PeriodSnapshot {
  return crops.reduce<PeriodSnapshot>(
    (acc, c) => ({
      period,
      yieldKg: acc.yieldKg + c.yieldKg,
      wasteKg: acc.wasteKg + c.wasteKg,
      incomeTnd: acc.incomeTnd + c.incomeTnd,
    }),
    { period, yieldKg: 0, wasteKg: 0, incomeTnd: 0 },
  );
}

/** Current period vs the most recent entry in the farmer's history. */
export function farmerDelta(farmer: Farmer, currentPeriod: string = CURRENT_PERIOD): DeltaMetrics {
  const current = snapshotFromCrops(farmer.crops, currentPeriod);
  return computeDeltaMetrics(current, farmer.history[farmer.history.length - 1]);
}

/** Waste as a percentage of yield; 0 when there is no yield. */
export function wastePercent(yieldKg: number, wasteKg: number): number {
  return yieldKg > 0 ? (wasteKg / yieldKg) * 100 : 0;
}

/** Facility fill level as a percentage of max capacity. */
export function facilityFillPct(f: StorageFacility): number {
  return f.maxCapacityKg > 0 ? (f.currentStockKg / f.maxCapacityKg) * 100 : 0;
}

// ---- Local mock fixtures ----

export const CURRENT_PERIOD = "2026-Q3";

export const MOCK_DELEGATIONS: Delegation[] = [
  { id: "mornag", name: "Mornag", governorate: "Ben Arous" },
  { id: "tebourba", name: "Tebourba", governorate: "Manouba" },
  { id: "kelibia", name: "Kelibia", governorate: "Nabeul" },
];

type HistoryRow = readonly [yieldKg: number, wasteKg: number, incomeTnd: number];

/** Builds oldest-first history for 2025-Q3 .. 2026-Q2 from compact rows. */
function makeHistory(rows: readonly HistoryRow[]): PeriodSnapshot[] {
  const periods = ["2025-Q3", "2025-Q4", "2026-Q1", "2026-Q2"];
  return rows.map(([yieldKg, wasteKg, incomeTnd], i) => ({
    period: periods[i] ?? `P${i + 1}`,
    yieldKg,
    wasteKg,
    incomeTnd,
  }));
}

export const MOCK_FARMERS: Farmer[] = [
  {
    id: "f-mornag-1",
    name: "Slim Ben Salah",
    delegationId: "mornag",
    phone: "+216 20 111 001",
    storageCapacityKg: 18000,
    crops: [
      { crop: "tomatoes", yieldKg: 9200, wasteKg: 620, incomeTnd: 11040 },
      { crop: "citrus", yieldKg: 4100, wasteKg: 180, incomeTnd: 7380 },
    ],
    history: makeHistory([
      [12800, 1240, 17200],
      [13100, 1150, 17900],
      [12600, 1010, 18100],
      [13000, 930, 18000],
    ]),
  },
  {
    id: "f-mornag-2",
    name: "Habiba Trabelsi",
    delegationId: "mornag",
    phone: "+216 22 111 002",
    storageCapacityKg: 12000,
    crops: [
      { crop: "olives", yieldKg: 6400, wasteKg: 240, incomeTnd: 12800 },
      { crop: "citrus", yieldKg: 2800, wasteKg: 150, incomeTnd: 5040 },
    ],
    history: makeHistory([
      [8600, 300, 17100],
      [8900, 330, 17600],
      [9400, 360, 18400],
      [9000, 350, 18900],
    ]),
  },
  {
    id: "f-tebourba-1",
    name: "Mohamed Gharbi",
    delegationId: "tebourba",
    phone: "+216 23 222 001",
    storageCapacityKg: 40000,
    crops: [
      { crop: "wheat", yieldKg: 28500, wasteKg: 570, incomeTnd: 24225 },
      { crop: "olives", yieldKg: 5200, wasteKg: 260, incomeTnd: 10400 },
    ],
    history: makeHistory([
      [31000, 820, 31800],
      [30500, 760, 32500],
      [32200, 700, 33900],
      [33000, 690, 34200],
    ]),
  },
  {
    id: "f-tebourba-2",
    name: "Nour Jebali",
    delegationId: "tebourba",
    phone: "+216 24 222 002",
    storageCapacityKg: 22000,
    crops: [
      { crop: "wheat", yieldKg: 15800, wasteKg: 470, incomeTnd: 13430 },
      { crop: "tomatoes", yieldKg: 3600, wasteKg: 430, incomeTnd: 3960 },
    ],
    history: makeHistory([
      [18200, 610, 16900],
      [19100, 560, 17200],
      [19800, 540, 17600],
      [19300, 500, 17400],
    ]),
  },
  {
    id: "f-kelibia-1",
    name: "Anis Mejri",
    delegationId: "kelibia",
    phone: "+216 25 333 001",
    storageCapacityKg: 26000,
    crops: [
      { crop: "citrus", yieldKg: 14800, wasteKg: 740, incomeTnd: 26640 },
      { crop: "tomatoes", yieldKg: 6100, wasteKg: 550, incomeTnd: 7320 },
    ],
    history: makeHistory([
      [19800, 1500, 30200],
      [20400, 1420, 31800],
      [21100, 1380, 33400],
      [21600, 1310, 34100],
    ]),
  },
  {
    id: "f-kelibia-2",
    name: "Rim Hamdi",
    delegationId: "kelibia",
    phone: "+216 26 333 002",
    storageCapacityKg: 15000,
    crops: [
      { crop: "citrus", yieldKg: 8300, wasteKg: 500, incomeTnd: 14940 },
      { crop: "olives", yieldKg: 2900, wasteKg: 130, incomeTnd: 5800 },
    ],
    history: makeHistory([
      [11800, 520, 22100],
      [11400, 540, 21600],
      [11000, 560, 21100],
      [10900, 580, 21300],
    ]),
  },
];

export const MOCK_FACILITIES: StorageFacility[] = [
  { id: "s-mornag-1", name: "Mornag Cold Storage", delegationId: "mornag", kind: "cold_storage", currentStockKg: 21000, maxCapacityKg: 35000 },
  { id: "s-mornag-2", name: "Mornag Central Warehouse", delegationId: "mornag", kind: "warehouse", currentStockKg: 9500, maxCapacityKg: 25000 },
  { id: "s-tebourba-1", name: "Tebourba Grain Silo", delegationId: "tebourba", kind: "silo", currentStockKg: 78000, maxCapacityKg: 100000 },
  { id: "s-tebourba-2", name: "Tebourba Cold Storage", delegationId: "tebourba", kind: "cold_storage", currentStockKg: 6200, maxCapacityKg: 20000 },
  { id: "s-kelibia-1", name: "Kelibia Citrus Cold Store", delegationId: "kelibia", kind: "cold_storage", currentStockKg: 29000, maxCapacityKg: 40000 },
  { id: "s-kelibia-2", name: "Kelibia Port Warehouse", delegationId: "kelibia", kind: "warehouse", currentStockKg: 11000, maxCapacityKg: 30000 },
];

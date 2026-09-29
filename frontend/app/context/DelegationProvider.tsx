"use client";

import {
  createContext,
  useCallback,
  useContext,
  useMemo,
  useState,
  type ReactNode,
} from "react";
import type { Plan } from "@/app/lib/reallocation";
import {
  MOCK_DELEGATIONS,
  MOCK_FACILITIES,
  MOCK_FARMERS,
  type Delegation,
  type Farmer,
  type StorageFacility,
} from "@/types";

export type DateRangeKey = "this_quarter" | "last_quarter" | "last_12_months";

export const DATE_RANGES: ReadonlyArray<{ key: DateRangeKey; label: string }> = [
  { key: "this_quarter", label: "This quarter" },
  { key: "last_quarter", label: "Last quarter" },
  { key: "last_12_months", label: "Last 12 months" },
];

interface DelegationContextValue {
  delegations: Delegation[];
  /** The delegation currently in scope for the whole dashboard. */
  selected: Delegation;
  selectDelegation: (id: string) => void;
  /** Farmers and facilities belonging to the selected delegation only. */
  farmers: Farmer[];
  /** Every farmer across all delegations (for regional comparisons). */
  allFarmers: Farmer[];
  facilities: StorageFacility[];
  /** Insert a new farmer, or replace the one with the same id. */
  upsertFarmer: (farmer: Farmer) => void;
  dateRange: DateRangeKey;
  setDateRange: (range: DateRangeKey) => void;
  /** Most recent optimization plan run for the selected delegation (this session). */
  latestPlan: Plan | null;
  saveLatestPlan: (plan: Plan) => void;
}

const DelegationContext = createContext<DelegationContextValue | null>(null);

export function DelegationProvider({ children }: { children: ReactNode }) {
  // Local mock state until the backend endpoints exist.
  const [allFarmers, setAllFarmers] = useState<Farmer[]>(MOCK_FARMERS);
  const [allFacilities] = useState<StorageFacility[]>(MOCK_FACILITIES);
  const [selectedId, setSelectedId] = useState<string>(MOCK_DELEGATIONS[0].id);
  const [dateRange, setDateRange] = useState<DateRangeKey>("this_quarter");
  const [plans, setPlans] = useState<Record<string, Plan>>({});

  const selectDelegation = useCallback((id: string) => {
    if (MOCK_DELEGATIONS.some((d) => d.id === id)) setSelectedId(id);
  }, []);

  const upsertFarmer = useCallback((farmer: Farmer) => {
    setAllFarmers((prev) =>
      prev.some((f) => f.id === farmer.id)
        ? prev.map((f) => (f.id === farmer.id ? farmer : f))
        : [...prev, farmer],
    );
  }, []);

  const saveLatestPlan = useCallback(
    (plan: Plan) => setPlans((prev) => ({ ...prev, [selectedId]: plan })),
    [selectedId],
  );

  const value = useMemo<DelegationContextValue>(() => {
    const selected =
      MOCK_DELEGATIONS.find((d) => d.id === selectedId) ?? MOCK_DELEGATIONS[0];
    return {
      delegations: MOCK_DELEGATIONS,
      selected,
      selectDelegation,
      farmers: allFarmers.filter((f) => f.delegationId === selected.id),
      allFarmers,
      facilities: allFacilities.filter((f) => f.delegationId === selected.id),
      upsertFarmer,
      dateRange,
      setDateRange,
      latestPlan: plans[selected.id] ?? null,
      saveLatestPlan,
    };
  }, [selectedId, allFarmers, allFacilities, dateRange, plans, selectDelegation, upsertFarmer, saveLatestPlan]);

  return <DelegationContext.Provider value={value}>{children}</DelegationContext.Provider>;
}

export function useDelegation(): DelegationContextValue {
  const ctx = useContext(DelegationContext);
  if (!ctx) throw new Error("useDelegation must be used inside <DelegationProvider>");
  return ctx;
}

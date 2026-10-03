"use client";

import { useState } from "react";
import { WaterfallChart, type WaterfallStep } from "@/components/charts/WaterfallChart";
import { inputClass } from "@/components/ui/primitives";
import { fmtMoney } from "@/lib/format";
import type { KpiRow } from "@/lib/api/types";

/**
 * Baseline profit -> scenario profit, through the revenue and cost deltas of the KPI table.
 * Costs are subtracted, so a cost increase is a negative step. Any rounding residual is shown.
 */
export function profitBridge(rows: KpiRow[], baselineId: string, runId: string): WaterfallStep[] {
  const value = (kpi: string, id: string) => rows.find((r) => r.kpi === kpi)?.values[id] ?? 0;
  const delta = (kpi: string) => value(kpi, runId) - value(kpi, baselineId);
  const start = value("realized_profit", baselineId);
  const end = value("realized_profit", runId);
  const steps: WaterfallStep[] = [
    { label: "Profit référence", kind: "total", value: start },
    { label: "Δ Chiffre d'affaires", kind: "delta", value: delta("realized_revenue") },
    { label: "Δ Transport", kind: "delta", value: -delta("transport_cost") },
    { label: "Δ Stockage", kind: "delta", value: -delta("storage_cost") },
    { label: "Δ Élimination", kind: "delta", value: -delta("disposal_cost") },
  ];
  const explained = steps.slice(1).reduce((s, st) => s + st.value, start);
  const residual = end - explained;
  if (Math.abs(residual) > 0.5) steps.push({ label: "Autres", kind: "delta", value: residual });
  steps.push({ label: "Profit scénario", kind: "total", value: end });
  return steps;
}

export function ProfitWaterfall({
  rows,
  baselineId,
  runIds,
  labels,
  currency,
}: {
  rows: KpiRow[];
  baselineId: string;
  runIds: string[];
  labels: Record<string, string>;
  currency?: string;
}) {
  const [runId, setRunId] = useState(runIds[0]);
  const selected = runIds.includes(runId) ? runId : runIds[0];
  return (
    <div className="space-y-3">
      {runIds.length > 1 && (
        <select aria-label="Exécution à expliquer" className={`${inputClass} w-auto`} value={selected} onChange={(e) => setRunId(e.target.value)}>
          {runIds.map((id) => (
            <option key={id} value={id}>
              {labels[id]}
            </option>
          ))}
        </select>
      )}
      <WaterfallChart
        steps={profitBridge(rows, baselineId, selected)}
        formatValue={(v) => fmtMoney(v, currency)}
        ariaLabel={`Passage du profit de ${labels[baselineId]} à ${labels[selected]}`}
      />
    </div>
  );
}

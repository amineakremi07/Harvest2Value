"use client";

import { Bar, BarChart, CartesianGrid, Cell, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import { CHART, tooltipStyle } from "@/components/charts/theme";
import type { SensitivityReport } from "@/lib/api/types";

export interface ProbeBar {
  label: string;
  value: number;
  significant: boolean;
}

/** Measured effect of each probe (re-optimized change), largest effect first. */
export function probeBars(report: SensitivityReport): ProbeBar[] {
  return (report.probes ?? [])
    .filter((p) => p.delta_objective != null && p.outcome !== "infeasible")
    .map((p) => ({ label: p.label, value: p.delta_objective as number, significant: p.significant ?? false }))
    .sort((a, b) => Math.abs(b.value) - Math.abs(a.value));
}

export function MarginalValueChart({ report, currency = "TND" }: { report: SensitivityReport; currency?: string }) {
  const bars = probeBars(report);
  if (bars.length === 0) return <p className="text-sm text-slate-400">Aucune perturbation mesurée.</p>;
  return (
    <div role="img" aria-label="Effet mesuré de chaque modification testée sur l'objectif" style={{ height: 48 + bars.length * 36 }}>
      <ResponsiveContainer width="100%" height="100%">
        <BarChart data={bars} layout="vertical" margin={{ top: 4, right: 24, bottom: 4, left: 8 }}>
          <CartesianGrid stroke={CHART.grid} horizontal={false} />
          <XAxis type="number" stroke={CHART.axis} tick={{ fill: CHART.text, fontSize: 11 }} tickFormatter={(v: number) => v.toLocaleString("fr-FR")} />
          <YAxis type="category" dataKey="label" width={260} stroke={CHART.axis} tick={{ fill: CHART.text, fontSize: 11 }} />
          <Tooltip
            {...tooltipStyle}
            cursor={{ fill: "rgba(255,255,255,0.04)" }}
            formatter={(v, _n, item) => {
              const bar = (item as { payload?: ProbeBar }).payload;
              const text = `${typeof v === "number" ? Math.round(v).toLocaleString("fr-FR") : String(v)} ${currency}`;
              return [bar && !bar.significant ? `${text} (non significatif)` : text, "Effet sur l'objectif"];
            }}
          />
          <Bar dataKey="value" isAnimationActive={false}>
            {bars.map((b) => (
              <Cell
                key={b.label}
                fill={b.value >= 0 ? CHART.positive : CHART.negative}
                fillOpacity={b.significant ? 0.95 : 0.35}
              />
            ))}
          </Bar>
        </BarChart>
      </ResponsiveContainer>
    </div>
  );
}

"use client";

import { useMemo } from "react";
import {
  Bar,
  BarChart,
  CartesianGrid,
  Legend,
  Line,
  LineChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import DeltaBadge from "@/app/components/DeltaBadge";
import PageTitle from "@/app/components/PageTitle";
import { glassCard, numberFormatter } from "@/app/components/styles";
import { useDelegation } from "@/app/context/DelegationProvider";
import { aggregateTrend, delegationDeltas } from "@/app/lib/regionStats";

const TICK = { fill: "var(--text-secondary)", fontSize: 12 };
const TOOLTIP_STYLE = {
  background: "var(--card-surface)",
  border: "1px solid var(--card-border)",
  borderRadius: 12,
  color: "var(--text-primary)",
  fontSize: 12,
};

export default function AnalyticsPage() {
  const { selected, farmers, allFarmers, delegations } = useDelegation();
  const trend = useMemo(() => aggregateTrend(farmers), [farmers]);
  const comparison = useMemo(() => delegationDeltas(delegations, allFarmers), [delegations, allFarmers]);
  const barData = comparison.map((c) => ({
    name: c.delegation.name,
    income: Number((c.delta.income.pct ?? 0).toFixed(1)),
    waste: Number((c.delta.waste.pct ?? 0).toFixed(1)),
  }));

  return (
    <>
      <PageTitle
        title="Analytics"
        subtitle="Income versus spoilage trends, and how each delegation compares to the previous period."
      />

      <section aria-labelledby="trend-title" className={glassCard}>
        <h2 id="trend-title" className="mb-1 text-sm font-semibold uppercase tracking-wider text-text-secondary">
          Income vs Waste · {selected.name}
        </h2>
        <p className="mb-4 text-xs text-text-secondary">Sum across all farmers, by quarter. Income in TND (left), waste in kg (right).</p>
        <div className="h-[300px]" role="img" aria-label={`Line chart of income and waste by quarter for ${selected.name}`}>
          <ResponsiveContainer width="100%" height="100%">
            <LineChart data={trend} margin={{ top: 8, right: 8, bottom: 0, left: 0 }}>
              <CartesianGrid stroke="var(--card-border)" strokeDasharray="3 3" />
              <XAxis dataKey="period" tick={TICK} stroke="var(--card-border)" />
              <YAxis yAxisId="income" tick={TICK} stroke="var(--card-border)" tickFormatter={(v) => `${numberFormatter.format(Number(v) / 1000)}k`} />
              <YAxis yAxisId="waste" orientation="right" tick={TICK} stroke="var(--card-border)" tickFormatter={(v) => numberFormatter.format(Number(v))} />
              <Tooltip contentStyle={TOOLTIP_STYLE} formatter={(v) => numberFormatter.format(Number(v))} />
              <Legend wrapperStyle={{ fontSize: 12 }} />
              <Line yAxisId="income" type="monotone" dataKey="incomeTnd" name="Income (TND)" stroke="var(--accent-text)" strokeWidth={2.5} dot={{ r: 3 }} />
              <Line yAxisId="waste" type="monotone" dataKey="wasteKg" name="Waste (kg)" stroke="var(--danger)" strokeWidth={2.5} strokeDasharray="6 3" dot={{ r: 3 }} />
            </LineChart>
          </ResponsiveContainer>
        </div>
      </section>

      <section aria-labelledby="compare-title" className={glassCard}>
        <h2 id="compare-title" className="mb-1 text-sm font-semibold uppercase tracking-wider text-text-secondary">
          Regional Comparison · Δ vs previous period
        </h2>
        <p className="mb-4 text-xs text-text-secondary">A falling waste bar is an improvement.</p>
        <div className="h-[280px]" role="img" aria-label="Bar chart of income and waste change per delegation">
          <ResponsiveContainer width="100%" height="100%">
            <BarChart data={barData} margin={{ top: 8, right: 8, bottom: 0, left: 0 }}>
              <CartesianGrid stroke="var(--card-border)" strokeDasharray="3 3" />
              <XAxis dataKey="name" tick={TICK} stroke="var(--card-border)" />
              <YAxis tick={TICK} stroke="var(--card-border)" unit="%" />
              <Tooltip contentStyle={TOOLTIP_STYLE} formatter={(v) => `${v}%`} />
              <Legend wrapperStyle={{ fontSize: 12 }} />
              <Bar dataKey="income" name="Δ Income %" fill="var(--accent-text)" radius={[4, 4, 0, 0]} />
              <Bar dataKey="waste" name="Δ Waste %" fill="var(--warning)" radius={[4, 4, 0, 0]} />
            </BarChart>
          </ResponsiveContainer>
        </div>

        <div className="mt-4 overflow-x-auto">
          <table className="w-full min-w-[420px] text-left text-sm">
            <thead>
              <tr className="border-b border-card-border text-xs uppercase tracking-wider text-text-secondary">
                <th scope="col" className="pb-2 pr-3 font-semibold">Delegation</th>
                <th scope="col" className="pb-2 pr-3 text-right font-semibold">Farmers</th>
                <th scope="col" className="pb-2 pr-3 font-semibold">Δ Income</th>
                <th scope="col" className="pb-2 font-semibold">Δ Waste</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-card-border">
              {comparison.map((c) => (
                <tr key={c.delegation.id}>
                  <th scope="row" className="py-3 pr-3 font-medium text-text-primary">{c.delegation.name}</th>
                  <td className="py-3 pr-3 text-right font-mono tabular-nums">{c.farmerCount}</td>
                  <td className="py-3 pr-3"><DeltaBadge label="Income change" delta={c.delta.income} /></td>
                  <td className="py-3"><DeltaBadge label="Waste change" delta={c.delta.waste} /></td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </section>
    </>
  );
}

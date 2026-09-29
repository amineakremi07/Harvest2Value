"use client";

import { useEffect, useMemo, useState } from "react";
import { ArrowRight, Check, Loader2, Play, RotateCcw, TrendingDown, TrendingUp } from "lucide-react";
import { decimalFormatter, glassCard, numberFormatter } from "@/app/components/styles";
import { useDelegation } from "@/app/context/DelegationProvider";
import { formatUrgency, planReallocation } from "@/app/lib/reallocation";
import { computeRegionStats } from "@/app/lib/regionStats";
import { CROPS } from "@/types";

/** Messages shown one after another while the plan "runs". */
const RUN_STAGES = [
  "Analyzing crop perishability…",
  "Checking facility capacity…",
  "Calculating optimal storage routes…",
] as const;
const STAGE_MS = 900;

const STEPS = ["Input summary", "Execution", "Before vs after", "Reallocation plan"] as const;

function Stepper({ current }: { current: number }) {
  return (
    <ol aria-label="Optimization progress" className="grid grid-cols-2 gap-3 sm:grid-cols-4">
      {STEPS.map((label, i) => {
        const done = i < current;
        const active = i === current;
        return (
          <li
            key={label}
            aria-current={active ? "step" : undefined}
            className={`flex items-center gap-3 rounded-xl border p-3 ${
              active ? "border-accent bg-accent/10" : "border-card-border bg-card-surface"
            }`}
          >
            <span
              className={`inline-flex h-7 w-7 shrink-0 items-center justify-center rounded-full text-xs font-bold ${
                done ? "bg-success text-white" : active ? "bg-accent text-white" : "bg-card-border text-text-secondary"
              }`}
            >
              {done ? <Check className="h-4 w-4" aria-hidden="true" /> : i + 1}
            </span>
            <span className={`text-sm font-semibold ${active || done ? "text-text-primary" : "text-text-secondary"}`}>
              {label}
              <span className="sr-only">{done ? " (complete)" : active ? " (current)" : ""}</span>
            </span>
          </li>
        );
      })}
    </ol>
  );
}

function CompareCard({
  title,
  beforeLabel,
  before,
  afterLabel,
  after,
  badge,
  good,
}: {
  title: string;
  beforeLabel: string;
  before: string;
  afterLabel: string;
  after: string;
  badge: string;
  good: boolean;
}) {
  const Icon = good ? TrendingUp : TrendingDown;
  return (
    <div className={glassCard}>
      <h3 className="mb-3 text-xs font-semibold uppercase tracking-wider text-text-secondary">{title}</h3>
      <div className="flex items-center gap-3">
        <div className="flex-1">
          <p className="text-xs text-text-secondary">{beforeLabel}</p>
          <p className="font-mono text-2xl font-bold tabular-nums text-text-secondary">{before}</p>
        </div>
        <ArrowRight className="h-5 w-5 shrink-0 text-text-secondary" aria-hidden="true" />
        <div className="flex-1">
          <p className="text-xs text-text-secondary">{afterLabel}</p>
          <p className="font-mono text-2xl font-bold tabular-nums text-text-primary">{after}</p>
        </div>
      </div>
      <span
        className={`mt-3 inline-flex items-center gap-1.5 rounded-full px-2.5 py-1 font-mono text-xs font-semibold tabular-nums ${
          good ? "bg-success/15 text-success" : "bg-danger/15 text-danger"
        }`}
      >
        <Icon className="h-3.5 w-3.5" aria-hidden="true" />
        {badge}
      </span>
    </div>
  );
}

export default function RegionalOptimizer() {
  const { selected, farmers, facilities, latestPlan, saveLatestPlan } = useDelegation();
  const stats = useMemo(() => computeRegionStats(farmers, facilities), [farmers, facilities]);
  const [running, setRunning] = useState(false);
  const [stage, setStage] = useState(0);

  // Advance the loader one stage at a time; the last stage produces the plan.
  useEffect(() => {
    if (!running) return;
    const timer = setTimeout(() => {
      if (stage < RUN_STAGES.length - 1) {
        setStage(stage + 1);
      } else {
        saveLatestPlan(planReallocation(farmers, facilities));
        setRunning(false);
      }
    }, STAGE_MS);
    return () => clearTimeout(timer);
  }, [running, stage, farmers, facilities, saveLatestPlan]);

  function start() {
    setStage(0);
    setRunning(true);
  }

  // The plan is kept per delegation in context, so it survives navigation.
  const plan = latestPlan;
  const result = plan;
  const current = running ? 1 : plan ? 3 : 0;

  return (
    <div className="space-y-6">
      <Stepper current={current} />

      {/* Step 1 */}
      <section aria-labelledby="input-title" className={glassCard}>
        <div className="mb-4 flex flex-wrap items-center justify-between gap-3">
          <h2 id="input-title" className="text-sm font-semibold uppercase tracking-wider text-text-secondary">
            1 · Input summary — {selected.name}
          </h2>
          <button
            type="button"
            onClick={start}
            disabled={running || farmers.length === 0}
            className="inline-flex min-h-[44px] items-center gap-2 rounded-full bg-accent px-6 py-2.5 text-sm font-bold text-white outline-none transition-colors hover:bg-accent-hover focus-visible:ring-2 focus-visible:ring-accent focus-visible:ring-offset-2 focus-visible:ring-offset-app-bg disabled:cursor-not-allowed disabled:opacity-50"
          >
            {result ? <RotateCcw className="h-4 w-4" aria-hidden="true" /> : <Play className="h-4 w-4" aria-hidden="true" />}
            {result ? "Run again" : "Run Optimization"}
          </button>
        </div>
        <dl className="grid grid-cols-2 gap-4 sm:grid-cols-4">
          {[
            ["Farmers", numberFormatter.format(stats.farmerCount)],
            ["Harvest volume", `${numberFormatter.format(stats.totalYieldKg / 1000)} t`],
            ["Facility capacity", `${numberFormatter.format(stats.maxKg / 1000)} t`],
            ["Free capacity", `${numberFormatter.format((stats.maxKg - stats.stockKg) / 1000)} t`],
          ].map(([label, value]) => (
            <div key={label}>
              <dt className="text-xs text-text-secondary">{label}</dt>
              <dd className="font-mono text-xl font-bold tabular-nums text-text-primary">{value}</dd>
            </div>
          ))}
        </dl>
        <ul className="mt-4 flex flex-wrap gap-2">
          {facilities.map((f) => (
            <li key={f.id} className="rounded-full border border-card-border px-3 py-1 text-xs text-text-secondary">
              {f.name}:{" "}
              <span className="font-mono tabular-nums text-text-primary">
                {decimalFormatter.format((f.maxCapacityKg - f.currentStockKg) / 1000)} t free
              </span>
            </li>
          ))}
        </ul>
      </section>

      {/* Step 2 */}
      {running && (
        <section aria-labelledby="run-title" className={`${glassCard} flex items-center gap-4`}>
          <Loader2 className="h-8 w-8 shrink-0 animate-spin text-accent-text" aria-hidden="true" />
          <div role="status" aria-live="polite">
            <h2 id="run-title" className="text-sm font-semibold uppercase tracking-wider text-text-secondary">
              2 · Running optimization
            </h2>
            <p className="text-base font-medium text-text-primary">{RUN_STAGES[stage]}</p>
            <p className="text-xs text-text-secondary">
              Step {stage + 1} of {RUN_STAGES.length}
            </p>
          </div>
        </section>
      )}

      <div id="latest-plan" className="scroll-mt-6 space-y-6">
      {!plan && !running && (
        <p className="rounded-2xl border border-dashed border-card-border p-6 text-center text-sm text-text-secondary">
          No plan yet for {selected.name}. Run the optimization to see the before/after comparison and actions.
        </p>
      )}
      {plan && (
        <>
          {/* Step 3 */}
          <section aria-labelledby="compare-title" className="space-y-3">
            <h2 id="compare-title" className="text-sm font-semibold uppercase tracking-wider text-text-secondary">
              3 · Before vs after
            </h2>
            <div className="grid gap-4 md:grid-cols-3">
              <CompareCard
                title="Spoilage"
                beforeLabel="Baseline waste"
                before={`${decimalFormatter.format(plan.baseline.wastePct)}%`}
                afterLabel="Optimized waste"
                after={`${decimalFormatter.format(plan.optimized.wastePct)}%`}
                badge={`${decimalFormatter.format(plan.baseline.wastePct - plan.optimized.wastePct)} pts lower`}
                good={plan.optimized.wastePct <= plan.baseline.wastePct}
              />
              <CompareCard
                title="Revenue"
                beforeLabel="Baseline income"
                before={`${numberFormatter.format(plan.baseline.incomeTnd)} TND`}
                afterLabel="Optimized income"
                after={`${numberFormatter.format(plan.optimized.incomeTnd)} TND`}
                badge={`+${decimalFormatter.format(plan.incomeGainPct)}% income gain`}
                good={plan.incomeGainPct >= 0}
              />
              <CompareCard
                title="Waste avoided"
                beforeLabel="Baseline waste"
                before={`${numberFormatter.format(plan.baseline.wasteKg)} kg`}
                afterLabel="Optimized waste"
                after={`${numberFormatter.format(plan.optimized.wasteKg)} kg`}
                badge={`${numberFormatter.format(plan.avoidedWasteKg)} kg saved`}
                good={plan.avoidedWasteKg >= 0}
              />
            </div>
            <p className="text-xs text-text-secondary">
              Estimated by a rule-based planner (perishability, spoilage rate and free capacity). The
              multi-crop solver isn&apos;t connected yet, so treat these as indicative.
            </p>
          </section>

          {/* Step 4 */}
          <section aria-labelledby="actions-title" className={`${glassCard} overflow-hidden`}>
            <h2 id="actions-title" className="mb-4 text-sm font-semibold uppercase tracking-wider text-text-secondary">
              4 · Reallocation plan ({plan.transfers.length} actions)
            </h2>
            {plan.transfers.length === 0 ? (
              <p className="py-6 text-center text-sm text-text-secondary">
                No reallocation recommended: no facility with free capacity would reduce spoilage.
              </p>
            ) : (
              <div className="overflow-x-auto">
                <table className="w-full min-w-[720px] text-left text-sm">
                  <thead>
                    <tr className="border-b border-card-border text-xs uppercase tracking-wider text-text-secondary">
                      <th scope="col" className="pb-2 pr-3 font-semibold">Recommended action</th>
                      <th scope="col" className="pb-2 pr-3 text-right font-semibold">Quantity</th>
                      <th scope="col" className="pb-2 pr-3 font-semibold">Deadline</th>
                      <th scope="col" className="pb-2 text-right font-semibold">Waste avoided</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-card-border">
                    {plan.transfers.map((t) => (
                      <tr key={`${t.farmerId}-${t.crop}-${t.facilityId}`}>
                        <td className="py-3 pr-3 text-text-primary">
                          Transfer {CROPS[t.crop].label} from <span className="font-semibold">{t.farmerName}</span> to{" "}
                          <span className="font-semibold">{t.facilityName}</span>
                        </td>
                        <td className="py-3 pr-3 text-right font-mono tabular-nums">{decimalFormatter.format(t.kg / 1000)} t</td>
                        <td className="py-3 pr-3 font-mono tabular-nums text-text-secondary">within {formatUrgency(t.urgencyHours)}</td>
                        <td className="py-3 text-right font-mono tabular-nums text-success">
                          {numberFormatter.format(t.avoidedWasteKg)} kg
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
          </section>
        </>
      )}
      </div>
    </div>
  );
}

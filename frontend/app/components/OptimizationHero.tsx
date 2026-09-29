"use client";

import { useMemo } from "react";
import Link from "next/link";
import { ArrowDown, ArrowRight, BarChart3, Zap } from "lucide-react";
import { decimalFormatter, numberFormatter } from "@/app/components/styles";
import { useDelegation } from "@/app/context/DelegationProvider";
import { planReallocation } from "@/app/lib/reallocation";

/** Human list: "Mornag, Tebourba, and Kelibia". */
function joinNames(names: string[]): string {
  if (names.length <= 2) return names.join(" and ");
  return `${names.slice(0, -1).join(", ")}, and ${names[names.length - 1]}`;
}

/**
 * Flagship call-to-action for the regional optimizer. It stays dark slate with
 * an electric-blue border in both themes, so it reads as the primary feature.
 * The status strip shows the last run if there is one, else a live preview.
 */
export default function OptimizationHero() {
  const { delegations, selected, farmers, facilities, latestPlan } = useDelegation();
  const preview = useMemo(() => planReallocation(farmers, facilities), [farmers, facilities]);
  const plan = latestPlan ?? preview;
  const reductionPts = plan.baseline.wastePct - plan.optimized.wastePct;

  return (
    <section
      aria-labelledby="opt-hero-title"
      className="relative overflow-hidden rounded-2xl border border-accent bg-[#0B0F17] p-6 text-white shadow-[0_0_48px_-12px_rgba(0,82,255,0.55)] sm:p-8"
    >
      <div
        aria-hidden="true"
        className="pointer-events-none absolute -right-24 -top-24 h-72 w-72 rounded-full bg-accent/25 blur-3xl"
      />
      <div className="relative">
        <span className="inline-flex items-center gap-1.5 rounded-full border border-accent/60 bg-accent/15 px-3 py-1 text-xs font-bold uppercase tracking-wider text-[#8FB1FF]">
          <Zap className="h-3.5 w-3.5" aria-hidden="true" />
          Core engine • Groq / AI solver ready
        </span>

        <h2 id="opt-hero-title" className="mt-4 text-2xl font-bold leading-tight sm:text-3xl">
          Run Regional Storage &amp; Spoilage Optimization
        </h2>
        <p className="mt-2 max-w-2xl text-sm leading-relaxed text-slate-300 sm:text-base">
          Reallocate current harvest volumes across {joinNames(delegations.map((d) => d.name))} storage
          facilities to minimize perishability waste and maximize net regional revenue.
        </p>

        <div className="mt-5 flex flex-wrap gap-3">
          <Link
            href="/optimization"
            className="inline-flex min-h-[46px] items-center gap-2 rounded-full bg-accent px-6 py-2.5 text-sm font-bold text-white outline-none transition-colors hover:bg-accent-hover focus-visible:ring-2 focus-visible:ring-white focus-visible:ring-offset-2 focus-visible:ring-offset-[#0B0F17]"
          >
            <Zap className="h-4 w-4" aria-hidden="true" />
            Launch Optimization Engine
            <ArrowRight className="h-4 w-4" aria-hidden="true" />
          </Link>
          <Link
            href="/optimization#latest-plan"
            className="inline-flex min-h-[46px] items-center gap-2 rounded-full border border-slate-600 px-6 py-2.5 text-sm font-semibold text-white outline-none transition-colors hover:border-accent hover:bg-white/5 focus-visible:ring-2 focus-visible:ring-white focus-visible:ring-offset-2 focus-visible:ring-offset-[#0B0F17]"
          >
            <BarChart3 className="h-4 w-4" aria-hidden="true" />
            View Active Plan
          </Link>
        </div>

        <div
          aria-label={`${selected.name} projected impact`}
          className="mt-6 flex flex-wrap items-center gap-x-4 gap-y-2 rounded-xl border border-white/10 bg-white/5 px-4 py-3 text-sm"
        >
          <span className="font-mono font-bold tabular-nums">
            {decimalFormatter.format(plan.baseline.wastePct)}%
            <span className="ml-1.5 font-sans font-normal text-slate-300">
              {latestPlan ? "Baseline Spoilage" : "Projected Spoilage"}
            </span>
          </span>
          <ArrowRight className="h-4 w-4 text-slate-400" aria-hidden="true" />
          <span className="inline-flex items-center gap-1.5 font-semibold text-[#3DDC97]">
            <ArrowDown className="h-4 w-4" aria-hidden="true" />
            Potential {decimalFormatter.format(reductionPts)}% Waste Reduction
            <span className="font-mono font-normal tabular-nums text-slate-300">
              (~{numberFormatter.format(plan.avoidedWasteKg)} kg saved)
            </span>
          </span>
          <span className="text-xs text-slate-400">
            {latestPlan ? "From your last run" : "Preview estimate"} · {selected.name}
          </span>
        </div>
      </div>
    </section>
  );
}

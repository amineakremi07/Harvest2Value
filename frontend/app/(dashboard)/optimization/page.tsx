"use client";

import { useState } from "react";
import BuyerOptimizer from "@/app/components/BuyerOptimizer";
import PageTitle from "@/app/components/PageTitle";
import RegionalOptimizer from "@/app/components/RegionalOptimizer";

type Tab = "regional" | "buyers";

const TABS: ReadonlyArray<{ id: Tab; label: string }> = [
  { id: "regional", label: "Regional plan" },
  { id: "buyers", label: "Buyer allocation (solver)" },
];

export default function OptimizationPage() {
  const [tab, setTab] = useState<Tab>("regional");

  return (
    <>
      <PageTitle
        title="Optimization Runs"
        subtitle="Run the optimizer, compare before and after, and follow the recommended reallocation actions."
      />

      <div role="tablist" aria-label="Optimization mode" className="flex gap-1 border-b border-card-border">
        {TABS.map((t) => (
          <button
            key={t.id}
            type="button"
            role="tab"
            id={`tab-${t.id}`}
            aria-selected={tab === t.id}
            aria-controls={`panel-${t.id}`}
            onClick={() => setTab(t.id)}
            className={`-mb-px rounded-t-lg border-b-2 px-4 py-2.5 text-sm font-semibold outline-none focus-visible:ring-2 focus-visible:ring-accent ${
              tab === t.id
                ? "border-accent text-accent-text"
                : "border-transparent text-text-secondary hover:text-text-primary"
            }`}
          >
            {t.label}
          </button>
        ))}
      </div>

      <div role="tabpanel" id={`panel-${tab}`} aria-labelledby={`tab-${tab}`} className="space-y-6">
        {tab === "regional" ? <RegionalOptimizer /> : <BuyerOptimizer />}
      </div>
    </>
  );
}

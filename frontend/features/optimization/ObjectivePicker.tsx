"use client";

import { cx } from "@/components/ui/primitives";
import type { ObjectiveKind } from "@/lib/api/types";
import { OBJECTIVE_LABEL } from "./runStatus";

const DESCRIPTIONS: Record<ObjectiveKind, string> = {
  profit: "Maximiser le profit réalisé (revenus − coûts).",
  revenue: "Maximiser le chiffre d'affaires, sans tenir compte des coûts.",
  waste: "Minimiser les pertes, avec un plancher de profit optionnel.",
  cost: "Minimiser les coûts pour un taux de vente minimal.",
  weighted: "Arbitrer profit, pertes et coûts selon des poids.",
};

export const OBJECTIVES: readonly ObjectiveKind[] = ["profit", "revenue", "waste", "cost", "weighted"];

export function ObjectivePicker({
  value,
  onChange,
  options = OBJECTIVES,
}: {
  value: ObjectiveKind;
  onChange: (objective: ObjectiveKind) => void;
  options?: readonly ObjectiveKind[];
}) {
  return (
    <div role="radiogroup" aria-label="Objectif" className="grid gap-2 sm:grid-cols-2 lg:grid-cols-5">
      {options.map((objective) => {
        const checked = objective === value;
        return (
          <button
            key={objective}
            type="button"
            role="radio"
            aria-checked={checked}
            aria-labelledby={`objective-${objective}-label`}
            aria-describedby={`objective-${objective}-desc`}
            onClick={() => onChange(objective)}
            className={cx(
              "rounded-lg border p-3 text-left transition-colors focus:outline-none focus-visible:ring-2 focus-visible:ring-cyan-accent",
              checked ? "border-emerald-accent bg-emerald-500/10" : "border-card-border bg-navy-deep hover:border-slate-500",
            )}
          >
            <span id={`objective-${objective}-label`} className="block text-sm font-semibold text-white">{OBJECTIVE_LABEL[objective]}</span>
            <span id={`objective-${objective}-desc`} className="mt-1 block text-xs text-slate-400">{DESCRIPTIONS[objective]}</span>
          </button>
        );
      })}
    </div>
  );
}

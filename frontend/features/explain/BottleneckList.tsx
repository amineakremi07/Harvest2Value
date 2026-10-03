"use client";

import { FlaskConical } from "lucide-react";
import { Badge, Button, EmptyState } from "@/components/ui/primitives";
import { InfoTip } from "@/components/ui/InfoTip";
import { fmtSigned } from "@/lib/format";
import type { Bottleneck } from "@/lib/api/types";
import { DUAL_TOOLTIP, familyLabel, PROBE_TOOLTIP } from "./labels";

function days(b: Bottleneck): string {
  const list = b.binding_days.filter((d): d is number => d != null);
  if (list.length === 0) return "sur tout l'horizon";
  if (list.length > 4) return `${list.length} jours (J${list[0]} … J${list[list.length - 1]})`;
  return list.map((d) => `J${d}`).join(", ");
}

/** Ranked bottlenecks: measured gain of relaxing them first, dual as a local indicator. */
export function BottleneckList({
  bottlenecks,
  currency = "TND",
  onTest,
  testing,
  measured = false,
}: {
  bottlenecks: Bottleneck[];
  currency?: string;
  /** True once the probes are computed: a missing gain then means "no significant effect". */
  measured?: boolean;
  onTest?: (b: Bottleneck) => void;
  testing?: string | null;
}) {
  if (bottlenecks.length === 0) return <EmptyState title="Aucun goulot : aucune contrainte ne limite le plan." />;
  return (
    <ol className="space-y-3" aria-label="Goulots d'étranglement">
      {[...bottlenecks]
        .sort((a, b) => a.rank - b.rank)
        .map((b) => (
          <li key={b.key} className="rounded-lg border border-card-border bg-navy-deep p-3">
            <div className="flex flex-wrap items-start justify-between gap-2">
              <div className="min-w-0">
                <p className="text-sm font-semibold text-white">
                  <span className="mr-2 font-mono text-xs text-slate-500">#{b.rank}</span>
                  {b.label}
                </p>
                <p className="mt-0.5 text-xs text-slate-400">
                  {familyLabel(b.family)} · saturée {days(b)}
                </p>
              </div>
              {b.suggested_change && onTest && (
                <Button onClick={() => onTest(b)} busy={testing === b.key}>
                  <FlaskConical className="h-4 w-4" aria-hidden="true" />
                  Tester
                </Button>
              )}
            </div>
            <div className="mt-2 flex flex-wrap items-center gap-x-4 gap-y-1 text-sm">
              {b.suggested_label && <span className="text-slate-300">Piste : {b.suggested_label}</span>}
              {b.probe_gain != null ? (
                <span className="inline-flex items-center gap-1 text-emerald-300">
                  Effet mesuré <InfoTip label="À propos de l'effet mesuré">{PROBE_TOOLTIP}</InfoTip>:
                  <span className="font-mono font-bold">
                    {fmtSigned(b.probe_gain)} {currency}
                  </span>
                </span>
              ) : (
                <Badge>{measured ? "pas d'effet significatif mesuré" : "effet non mesuré"}</Badge>
              )}
              {b.dual != null && (
                <span className="inline-flex items-center gap-1 text-xs text-slate-500">
                  Indicateur local <InfoTip label="Limites de l'indicateur local">{DUAL_TOOLTIP}</InfoTip>: {fmtSigned(b.dual)} {currency}/unité
                </span>
              )}
            </div>
          </li>
        ))}
    </ol>
  );
}

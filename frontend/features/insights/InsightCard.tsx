"use client";

import { FlaskConical } from "lucide-react";
import { Badge, Button, type Tone } from "@/components/ui/primitives";
import type { InsightView } from "@/lib/api/types";

export const SEVERITY_TONE: Record<InsightView["severity"], Tone> = { critical: "danger", warning: "warning", info: "info" };
export const SEVERITY_LABEL: Record<InsightView["severity"], string> = { critical: "Critique", warning: "Attention", info: "Info" };
export const CATEGORY_LABEL: Record<InsightView["category"], string> = { risk: "Risque", opportunity: "Opportunité", info: "Information" };

export function InsightCard({
  insight,
  onDismiss,
  onRestore,
  onTry,
  busy = false,
  compact = false,
}: {
  insight: InsightView;
  onDismiss?: () => void;
  onRestore?: () => void;
  onTry?: () => void;
  busy?: boolean;
  compact?: boolean;
}) {
  const canTry = insight.suggested_changes.length > 0 && onTry;
  return (
    <article className="rounded-lg border border-card-border bg-navy-deep p-3" aria-label={insight.message}>
      <div className="flex flex-wrap items-center gap-2">
        <Badge tone={SEVERITY_TONE[insight.severity]}>{SEVERITY_LABEL[insight.severity]}</Badge>
        <Badge>{CATEGORY_LABEL[insight.category]}</Badge>
        {insight.dismissed && <Badge>Ignorée</Badge>}
      </div>
      <p className="mt-2 text-sm text-slate-200">{insight.message}</p>
      {!compact && insight.evidence.metrics.length > 0 && (
        <dl className="mt-2 grid grid-cols-2 gap-x-4 gap-y-1 text-xs sm:grid-cols-3">
          {insight.evidence.metrics.map((m) => (
            <div key={m.key} title={m.source}>
              <dt className="text-slate-500">{m.key}</dt>
              <dd className="font-mono text-slate-300">
                {typeof m.value === "number" ? m.value.toLocaleString("fr-FR", { maximumFractionDigits: 2 }) : String(m.value ?? "—")} {m.unit}
              </dd>
            </div>
          ))}
        </dl>
      )}
      {(canTry || onDismiss || onRestore) && (
        <div className="mt-3 flex flex-wrap gap-2">
          {canTry && (
            <Button variant="primary" onClick={onTry} busy={busy}>
              <FlaskConical className="h-4 w-4" aria-hidden="true" />
              Tester cette recommandation
            </Button>
          )}
          {onDismiss && !insight.dismissed && (
            <Button variant="ghost" onClick={onDismiss}>
              Ignorer
            </Button>
          )}
          {onRestore && insight.dismissed && (
            <Button variant="ghost" onClick={onRestore}>
              Restaurer
            </Button>
          )}
        </div>
      )}
    </article>
  );
}

"use client";

import Link from "next/link";
import { useState } from "react";
import { Check, FileText, GitBranch, Play, X } from "lucide-react";
import { Badge, Button, ErrorBanner, type Tone } from "@/components/ui/primitives";
import { errorMessage } from "@/lib/api/client";
import { api } from "@/lib/api/endpoints";
import type { ActionView } from "@/lib/api/types";
import { fmtDate } from "@/lib/format";

const KIND = {
  create_scenario: { label: "Nouveau scénario", icon: GitBranch },
  run_optimization: { label: "Optimisation", icon: Play },
  generate_report: { label: "Rapport", icon: FileText },
} as const;

const STATUS: Record<ActionView["status"], { label: string; tone: Tone }> = {
  pending: { label: "À confirmer", tone: "info" },
  executed: { label: "Exécutée", tone: "success" },
  rejected: { label: "Refusée", tone: "neutral" },
  expired: { label: "Expirée", tone: "warning" },
  failed: { label: "Échec", tone: "danger" },
};

/** Where the result of an executed action lives. */
export function resultHref(action: ActionView): { href: string; label: string } | null {
  const result = action.result ?? {};
  const id = (key: string) => (typeof result[key] === "string" ? (result[key] as string) : null);
  if (action.kind === "create_scenario" && id("scenario_id")) return { href: `/scenarios/${id("scenario_id")}`, label: "Ouvrir le scénario" };
  if (action.kind === "run_optimization" && id("run_id")) return { href: `/runs/${id("run_id")}/summary`, label: "Voir l'exécution" };
  if (action.kind === "generate_report" && id("report_id")) return { href: `/reports/${id("report_id")}`, label: "Ouvrir le rapport" };
  return null;
}

/** A copilot proposal: nothing happens until the user confirms it here. */
export function ActionCard({ action, onChange }: { action: ActionView; onChange: (action: ActionView) => void }) {
  const [busy, setBusy] = useState<"confirm" | "reject" | null>(null);
  const [error, setError] = useState<string | null>(null);
  const kind = KIND[action.kind];
  const status = STATUS[action.status];
  const link = resultHref(action);

  async function decide(which: "confirm" | "reject") {
    setBusy(which);
    setError(null);
    try {
      onChange(await (which === "confirm" ? api.confirmAction(action.id) : api.rejectAction(action.id)));
    } catch (err) {
      setError(errorMessage(err));
    } finally {
      setBusy(null);
    }
  }

  return (
    <article aria-label={`Proposition : ${kind.label}`} className="rounded-lg border border-cyan-500/30 bg-cyan-500/5 p-3 text-sm">
      <header className="mb-1 flex flex-wrap items-center justify-between gap-2">
        <span className="inline-flex items-center gap-2 font-semibold text-cyan-200">
          <kind.icon className="h-4 w-4" aria-hidden="true" />
          {kind.label}
        </span>
        <Badge tone={status.tone}>{status.label}</Badge>
      </header>
      <p className="text-slate-200">{action.summary}</p>
      {action.status === "pending" && (
        <>
          <p className="mt-1 text-xs text-slate-500">Rien n&apos;est modifié sans votre confirmation · expire le {fmtDate(action.expires_at)}</p>
          <div className="mt-2 flex gap-2">
            <Button variant="primary" onClick={() => decide("confirm")} busy={busy === "confirm"} disabled={busy !== null}>
              <Check className="h-4 w-4" aria-hidden="true" />
              Confirmer
            </Button>
            <Button variant="ghost" onClick={() => decide("reject")} busy={busy === "reject"} disabled={busy !== null}>
              <X className="h-4 w-4" aria-hidden="true" />
              Refuser
            </Button>
          </div>
        </>
      )}
      {action.status === "failed" && action.error && <p className="mt-1 text-xs text-rose-300">{action.error}</p>}
      {link && (
        <Link href={link.href} className="mt-2 inline-block font-semibold text-emerald-300 hover:underline">
          {link.label} →
        </Link>
      )}
      {error && (
        <div className="mt-2">
          <ErrorBanner message={error} />
        </div>
      )}
    </article>
  );
}

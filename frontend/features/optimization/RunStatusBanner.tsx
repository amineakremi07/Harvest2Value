"use client";

import { AlertTriangle, CheckCircle2, Loader2, XCircle } from "lucide-react";
import { Badge, Button, cx } from "@/components/ui/primitives";
import { fmtNum } from "@/lib/format";
import type { RunDetail } from "@/lib/api/types";
import { RUN_STATUS_LABEL, RUN_STATUS_TONE } from "./runStatus";

const FRAME: Record<string, string> = {
  info: "border-cyan-500/30 bg-cyan-500/10",
  success: "border-emerald-500/30 bg-emerald-500/10",
  warning: "border-amber-500/30 bg-amber-500/10",
  danger: "border-rose-500/30 bg-rose-500/10",
  neutral: "border-card-border bg-card-surface",
};

export function RunStatusBanner({
  run,
  polling,
  onCancel,
  cancelling = false,
}: {
  run: RunDetail;
  polling: boolean;
  onCancel?: () => void;
  cancelling?: boolean;
}) {
  const tone = RUN_STATUS_TONE[run.status];
  const active = run.status === "queued" || run.status === "running";
  const Icon = active ? Loader2 : run.status === "succeeded" ? CheckCircle2 : run.status === "failed" ? XCircle : AlertTriangle;

  return (
    <div role="status" aria-live="polite" className={cx("mb-6 rounded-xl border px-4 py-3", FRAME[tone])}>
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div className="flex flex-wrap items-center gap-3 text-sm">
          <Icon className={cx("h-5 w-5", active && "animate-spin")} aria-hidden="true" />
          <Badge tone={tone}>{RUN_STATUS_LABEL[run.status]}</Badge>
          {active && <span className="text-slate-300">{run.status === "queued" ? "En attente du solveur…" : "Optimisation en cours…"}</span>}
          {polling && <span className="text-xs text-slate-500">actualisation chaque seconde</span>}
          {run.status === "succeeded" && (
            <span className="text-slate-300">
              Résolu en {fmtNum(run.solve_seconds)} s
              {run.mip_gap != null && ` · écart prouvé ${fmtNum(run.mip_gap * 100)} %`}
              {run.solver_outcome === "feasible" && " · solution non prouvée optimale (limite de temps)"}
            </span>
          )}
          {run.cache_hit && <Badge tone="info">Résultat réutilisé (cache)</Badge>}
        </div>
        {run.status === "queued" && onCancel && (
          <Button variant="danger" onClick={onCancel} busy={cancelling}>
            Annuler
          </Button>
        )}
      </div>
      {run.error && (
        <p className="mt-2 text-sm text-rose-200">
          {run.error.code} — {run.error.message ?? "erreur inconnue"}
        </p>
      )}
      {run.status === "infeasible" && run.diagnostics && (
        <div className="mt-3 text-sm text-amber-100">
          <p className="font-semibold">Le modèle est infaisable. Contraintes à relâcher :</p>
          <ul className="mt-1 list-disc pl-5">
            {(run.diagnostics.conflicts ?? []).map((c) => (
              <li key={c.key}>
                {c.label} — relâcher de {fmtNum(c.relaxation_needed)} {c.unit}
              </li>
            ))}
          </ul>
          {(run.diagnostics.suggestions ?? []).length > 0 && (
            <ul className="mt-2 list-disc pl-5 text-amber-200/80">
              {(run.diagnostics.suggestions ?? []).map((s) => (
                <li key={s}>{s}</li>
              ))}
            </ul>
          )}
        </div>
      )}
      {run.warnings.length > 0 && (
        <ul className="mt-2 list-disc pl-5 text-xs text-amber-200/80">
          {run.warnings.map((w) => (
            <li key={w}>{w}</li>
          ))}
        </ul>
      )}
    </div>
  );
}

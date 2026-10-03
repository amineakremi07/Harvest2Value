"use client";

import Link from "next/link";
import { useState, type ReactNode } from "react";
import { FileText, GitCompare, LineChart } from "lucide-react";
import { ErrorBanner, Loading, PageHeader } from "@/components/ui/primitives";
import { LinkTabs } from "@/components/ui/Tabs";
import { errorMessage } from "@/lib/api/client";
import { api } from "@/lib/api/endpoints";
import { fmtDate, shortId } from "@/lib/format";
import type { OptimizationResult } from "@/lib/api/types";
import { RunStatusBanner } from "./RunStatusBanner";
import { OBJECTIVE_LABEL } from "./runStatus";
import { RunViewProvider, useRunView } from "./RunContext";

export const RUN_TABS = [
  { slug: "summary", label: "Synthèse" },
  { slug: "allocation", label: "Allocation" },
  { slug: "inventory", label: "Stock" },
  { slug: "logistics", label: "Logistique" },
  { slug: "explain", label: "Explication" },
  { slug: "insights", label: "Alertes" },
  { slug: "network", label: "Réseau" },
  { slug: "raw", label: "Données brutes" },
] as const;

function RunHeader() {
  const { run, runError, polling, refresh, runId } = useRunView();
  const [cancelling, setCancelling] = useState(false);
  const [cancelError, setCancelError] = useState<string | null>(null);

  if (!run) {
    return runError ? <ErrorBanner message={errorMessage(runError)} onRetry={refresh} /> : <Loading label="Chargement de l'exécution…" />;
  }

  async function cancel() {
    setCancelling(true);
    setCancelError(null);
    try {
      await api.cancelRun(runId);
      refresh();
    } catch (err) {
      setCancelError(errorMessage(err));
    } finally {
      setCancelling(false);
    }
  }

  return (
    <>
      <PageHeader
        title={run.label ?? `Exécution ${shortId(run.id)}`}
        subtitle={
          <span className="flex flex-wrap gap-x-3">
            <span>Objectif : {OBJECTIVE_LABEL[run.objective]}</span>
            <span>
              Données v{run.version_no}
              {run.scenario_id && (
                <>
                  {" "}· scénario{" "}
                  <Link className="text-cyan-300 hover:underline" href={`/scenarios/${run.scenario_id}`}>
                    {shortId(run.scenario_id)}
                  </Link>
                </>
              )}
            </span>
            <span>Créée {fmtDate(run.created_at)}</span>
          </span>
        }
        actions={
          run.status === "succeeded" && (
            <>
              <Link href={`/compare?runs=${run.id}`} className={ACTION_LINK}>
                <GitCompare className="h-4 w-4" aria-hidden="true" />
                Comparer
              </Link>
              <Link href={`/analytics?run=${run.id}`} className={ACTION_LINK}>
                <LineChart className="h-4 w-4" aria-hidden="true" />
                Analyses
              </Link>
              <Link href={`/reports/new?run=${run.id}`} className={ACTION_LINK}>
                <FileText className="h-4 w-4" aria-hidden="true" />
                Rapport
              </Link>
            </>
          )
        }
      />
      <RunStatusBanner run={run} polling={polling} onCancel={cancel} cancelling={cancelling} />
      {cancelError && <ErrorBanner message={cancelError} />}
    </>
  );
}

const ACTION_LINK =
  "inline-flex items-center gap-2 rounded-lg border border-card-border px-3 py-1.5 text-sm font-semibold text-slate-200 hover:border-slate-500";

export function RunShell({ runId, children }: { runId: string; children: ReactNode }) {
  return (
    <RunViewProvider runId={runId}>
      <RunHeader />
      <LinkTabs label="Sections de l'exécution" tabs={RUN_TABS.map((t) => ({ href: `/runs/${runId}/${t.slug}`, label: t.label, muted: "muted" in t }))} />
      {children}
    </RunViewProvider>
  );
}

/** Renders `children(result)` once the plan is available, otherwise the reason it is not. */
export function WithResult({ children }: { children: (result: OptimizationResult) => ReactNode }) {
  const { run, result, resultError } = useRunView();
  if (!run) return null;
  if (run.status === "queued" || run.status === "running") return <Loading label="Le résultat s'affichera à la fin de l'optimisation…" />;
  if (run.status !== "succeeded") {
    return <p className="text-sm text-slate-400">Pas de plan pour cette exécution (statut : {run.status}).</p>;
  }
  if (resultError) return <ErrorBanner message={errorMessage(resultError)} />;
  if (!result) return <Loading label="Chargement du résultat…" />;
  return <>{children(result)}</>;
}

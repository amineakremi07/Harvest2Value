"use client";

import Link from "next/link";
import { useState } from "react";
import { EmptyState, ErrorBanner, inputClass, Loading, PageHeader, Button } from "@/components/ui/primitives";
import { errorMessage } from "@/lib/api/client";
import { api } from "@/lib/api/endpoints";
import { useApi } from "@/lib/hooks/useApi";
import type { RunStatus } from "@/lib/api/types";
import { RunList } from "@/features/optimization/RunList";
import { RUN_STATUS_LABEL } from "@/features/optimization/runStatus";

const PAGE_SIZE = 20;

export default function RunsPage() {
  const [status, setStatus] = useState<RunStatus | "">("");
  const [page, setPage] = useState(1);
  const runs = useApi(() => api.runs({ status: status || undefined, page, page_size: PAGE_SIZE }), [status, page]);
  const datasets = useApi(() => api.datasets(), []);
  const datasetNames = Object.fromEntries((datasets.data?.items ?? []).map((d) => [d.id, d.name]));
  const total = runs.data?.total ?? 0;

  return (
    <>
      <PageHeader
        title="Exécutions"
        subtitle="Historique des optimisations, les plus récentes d'abord."
        actions={
          <>
            <select
              aria-label="Filtrer par statut"
              className={inputClass}
              value={status}
              onChange={(e) => {
                setStatus(e.target.value as RunStatus | "");
                setPage(1);
              }}
            >
              <option value="">Tous les statuts</option>
              {(Object.keys(RUN_STATUS_LABEL) as RunStatus[]).map((s) => (
                <option key={s} value={s}>
                  {RUN_STATUS_LABEL[s]}
                </option>
              ))}
            </select>
            <Link href="/optimize" className="whitespace-nowrap rounded-lg bg-emerald-accent px-3 py-2 text-sm font-semibold text-black hover:bg-emerald-400">
              Nouvelle optimisation
            </Link>
          </>
        }
      />
      {runs.loading && !runs.data ? (
        <Loading />
      ) : runs.error ? (
        <ErrorBanner message={errorMessage(runs.error)} onRetry={runs.reload} />
      ) : !runs.data || runs.data.items.length === 0 ? (
        <EmptyState title="Aucune exécution.">
          <Link href="/optimize" className="text-cyan-300 hover:underline">
            Lancer une première optimisation
          </Link>
        </EmptyState>
      ) : (
        <div className="space-y-4 rounded-xl border border-card-border bg-card-surface p-4">
          <RunList runs={runs.data.items} datasetNames={datasetNames} />
          {total > PAGE_SIZE && (
            <div className="flex items-center justify-end gap-2 text-sm text-slate-400">
              <Button disabled={page <= 1} onClick={() => setPage((p) => p - 1)}>
                Précédent
              </Button>
              <span>
                Page {page} / {Math.ceil(total / PAGE_SIZE)}
              </span>
              <Button disabled={page * PAGE_SIZE >= total} onClick={() => setPage((p) => p + 1)}>
                Suivant
              </Button>
            </div>
          )}
        </div>
      )}
    </>
  );
}

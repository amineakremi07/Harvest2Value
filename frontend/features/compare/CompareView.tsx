"use client";

import { useRouter } from "next/navigation";
import { useEffect, useState } from "react";
import { Card, EmptyState, ErrorBanner, Loading, PageHeader } from "@/components/ui/primitives";
import { ApiError, errorMessage } from "@/lib/api/client";
import { api } from "@/lib/api/endpoints";
import { useApi } from "@/lib/hooks/useApi";
import { NarrativeCard } from "@/features/copilot/NarrativeCard";
import { BuyerDeltaHeatmap } from "./BuyerDeltaHeatmap";
import { CompareKpiTable } from "./CompareKpiTable";
import { NotableChanges } from "./NotableChanges";
import { ProfitWaterfall } from "./ProfitWaterfall";
import { defaultBaseline, MAX_COMPARED, RunPicker } from "./RunPicker";
import { runLabels } from "./runLabels";

export function CompareView({ initialBaseline, initialRuns }: { initialBaseline?: string; initialRuns: string[] }) {
  const router = useRouter();
  // undefined = not chosen yet (guessed below), null = explicitly cleared.
  const [chosenBaseline, setBaselineId] = useState<string | null | undefined>(initialBaseline);
  const [runIds, setRunIds] = useState<string[]>(initialRuns.filter((r) => r !== initialBaseline).slice(0, MAX_COMPARED));
  const runs = useApi(() => api.runs({ status: "succeeded", page_size: 100 }), []);

  // Coming from a run or scenario page (?runs=X only): use its dataset's latest baseline run.
  const baselineId =
    chosenBaseline === undefined ? (runs.data && runIds.length > 0 ? defaultBaseline(runs.data.items, runIds) : undefined) : (chosenBaseline ?? undefined);

  useEffect(() => {
    const params = new URLSearchParams();
    if (baselineId) params.set("baseline", baselineId);
    if (runIds.length > 0) params.set("runs", runIds.join(","));
    router.replace(`/compare${params.size ? `?${params}` : ""}`, { scroll: false });
  }, [baselineId, runIds, router]);

  const ready = Boolean(baselineId) && runIds.length > 0;
  const comparison = useApi(ready ? () => api.compare(baselineId as string, runIds) : null, [baselineId, runIds.join(",")]);

  // A trial run started from "Tester cette recommandation" may still be solving: retry each second.
  const waiting = comparison.error instanceof ApiError && comparison.error.code === "RUN_NOT_FINISHED";
  const { reload: reloadComparison } = comparison;
  useEffect(() => {
    if (!waiting) return;
    const timer = setTimeout(reloadComparison, 1000);
    return () => clearTimeout(timer);
  }, [waiting, reloadComparison]);

  const result = comparison.data;
  const labels = result ? runLabels(result) : {};
  const shownRuns = result?.run_ids ?? [];

  return (
    <>
      <PageHeader title="Comparer" subtitle="Une exécution de référence face à une à trois autres : indicateurs, acheteurs, profit." />
      <div className="space-y-6">
        <Card title="Sélection">
          {runs.loading ? (
            <Loading />
          ) : runs.error || !runs.data ? (
            <ErrorBanner message={errorMessage(runs.error)} onRetry={runs.reload} />
          ) : runs.data.items.length < 2 ? (
            <EmptyState title="Il faut au moins deux exécutions terminées pour comparer." />
          ) : (
            <RunPicker
              runs={runs.data.items}
              baselineId={baselineId}
              runIds={runIds}
              onChange={(b, r) => {
                setBaselineId(b ?? null);
                setRunIds(r);
              }}
            />
          )}
        </Card>

        {!ready ? null : waiting ? (
          <Loading label="En attente de la fin de l'exécution à comparer…" />
        ) : comparison.loading && !result ? (
          <Loading label="Calcul de la comparaison…" />
        ) : comparison.error ? (
          <ErrorBanner message={errorMessage(comparison.error)} onRetry={comparison.reload} />
        ) : result ? (
          <>
            <NarrativeCard
              key={[result.baseline_run_id, ...shownRuns].join(",")}
              title="Lecture de la comparaison"
              load={() => api.comparisonNarrative(result.baseline_run_id, shownRuns)}
              hint="L'IA résume les écarts calculés par le backend (indicateurs, acheteurs, changements notables)."
            />
            <Card title="Changements notables">
              <NotableChanges changes={result.notable_changes} labels={labels} />
            </Card>
            <div className="grid grid-cols-1 gap-6 xl:grid-cols-2">
              <Card title="Du profit de référence au profit comparé">
                <ProfitWaterfall rows={result.kpi_table} baselineId={result.baseline_run_id} runIds={shownRuns} labels={labels} />
              </Card>
              <Card title="Acheteurs (écarts en kg)">
                <BuyerDeltaHeatmap rows={result.buyer_matrix} baselineId={result.baseline_run_id} runIds={shownRuns} labels={labels} />
              </Card>
            </div>
            <Card title="Indicateurs">
              <CompareKpiTable rows={result.kpi_table} baselineId={result.baseline_run_id} runIds={shownRuns} labels={labels} />
            </Card>
          </>
        ) : null}
      </div>
    </>
  );
}

"use client";

import { useRouter } from "next/navigation";
import { useState } from "react";
import { Card, EmptyState, ErrorBanner, Loading } from "@/components/ui/primitives";
import { errorMessage } from "@/lib/api/client";
import { api } from "@/lib/api/endpoints";
import { useApi } from "@/lib/hooks/useApi";
import type { InsightView } from "@/lib/api/types";
import { compareHref } from "@/features/explain/testChange";
import { InsightCard } from "./InsightCard";

export function RunInsightsPanel({ runId }: { runId: string }) {
  const router = useRouter();
  const [showDismissed, setShowDismissed] = useState(false);
  const { data, error, loading, reload, setData } = useApi(() => api.runInsights(runId, showDismissed), [runId, showDismissed]);
  const [busyId, setBusyId] = useState<string | null>(null);
  const [actionError, setActionError] = useState<string | null>(null);

  const replace = (updated: InsightView) =>
    setData((data ?? []).map((i) => (i.id === updated.id ? updated : i)).filter((i) => showDismissed || !i.dismissed));

  async function act(id: string, action: () => Promise<void>) {
    setBusyId(id);
    setActionError(null);
    try {
      await action();
    } catch (err) {
      setActionError(errorMessage(err));
    } finally {
      setBusyId(null);
    }
  }

  return (
    <Card
      title="Alertes et opportunités"
      actions={
        <label className="flex items-center gap-2 text-xs text-slate-400">
          <input type="checkbox" checked={showDismissed} onChange={(e) => setShowDismissed(e.target.checked)} />
          Afficher les alertes ignorées
        </label>
      }
    >
      {actionError && <ErrorBanner message={actionError} />}
      {loading && !data ? (
        <Loading />
      ) : error ? (
        <ErrorBanner message={errorMessage(error)} onRetry={reload} />
      ) : !data || data.length === 0 ? (
        <EmptyState title="Aucune alerte pour ce plan." />
      ) : (
        <div className="space-y-3">
          {data.map((insight) => (
            <InsightCard
              key={insight.id}
              insight={insight}
              busy={busyId === insight.id}
              onDismiss={() => act(insight.id, async () => replace(await api.dismissInsight(insight.id)))}
              onRestore={() => act(insight.id, async () => replace(await api.restoreInsight(insight.id)))}
              onTry={() =>
                act(insight.id, async () => {
                  const trial = await api.tryInsight(insight.id);
                  router.push(compareHref(runId, trial.run_id));
                })
              }
            />
          ))}
        </div>
      )}
    </Card>
  );
}

"use client";

import { useRouter } from "next/navigation";
import { useCallback, useEffect, useState } from "react";
import { Gauge } from "lucide-react";
import { Button, Card, EmptyState, ErrorBanner, Loading } from "@/components/ui/primitives";
import { ApiError, errorMessage } from "@/lib/api/client";
import { api } from "@/lib/api/endpoints";
import { useApi } from "@/lib/hooks/useApi";
import type { Bottleneck, RunDetail } from "@/lib/api/types";
import { InsightCard } from "@/features/insights/InsightCard";
import { useRunView } from "@/features/optimization/RunContext";
import { BindingConstraintsTable } from "./BindingConstraintsTable";
import { BottleneckList } from "./BottleneckList";
import { DecisionCard } from "./DecisionCard";
import { MarginalValueChart } from "./MarginalValueChart";
import { Narrative } from "./Narrative";
import { asChangeInput, compareHref, trySuggestedChange } from "./testChange";

const KIND_ORDER = { buyer: 0, storage: 1, waste: 2 } as const;

function useMarginalValues(runId: string, computed: boolean, onComputed: () => void) {
  const [state, setState] = useState<"idle" | "computing" | "error">("idle");
  const [error, setError] = useState<string | null>(null);
  const report = useApi(computed ? () => api.marginalValues(runId) : null, [runId, computed]);

  useEffect(() => {
    if (state !== "computing") return;
    let live = true;
    let timer: ReturnType<typeof setTimeout> | undefined;
    const poll = async () => {
      try {
        await api.marginalValues(runId);
        if (!live) return;
        setState("idle");
        onComputed();
      } catch (err) {
        if (!live) return;
        if (err instanceof ApiError && err.code === "NOT_COMPUTED") {
          timer = setTimeout(poll, 1000);
          return;
        }
        setError(errorMessage(err));
        setState("error");
      }
    };
    timer = setTimeout(poll, 1000);
    return () => {
      live = false;
      if (timer) clearTimeout(timer);
    };
  }, [state, runId, onComputed]);

  async function start() {
    setError(null);
    try {
      const status = await api.startMarginalValues(runId, 10);
      if (status.status === "computed") onComputed();
      else setState("computing");
    } catch (err) {
      setError(errorMessage(err));
      setState("error");
    }
  }

  return { report, computing: state === "computing", error, start };
}

function ExplainBody({ run }: { run: RunDetail }) {
  const router = useRouter();
  const { currency } = useRunView();
  const explanation = useApi(() => api.explanation(run.id), [run.id]);
  const insights = useApi(() => api.runInsights(run.id), [run.id]);
  // Computing the probes rebuilds the explanation and regenerates the insights (new ids).
  const { reload: reloadExplanation } = explanation;
  const { reload: reloadInsights } = insights;
  const onComputed = useCallback(() => {
    reloadExplanation();
    reloadInsights();
  }, [reloadExplanation, reloadInsights]);
  const marginal = useMarginalValues(run.id, explanation.data?.sensitivity_computed ?? false, onComputed);
  const [testing, setTesting] = useState<string | null>(null);
  const [testError, setTestError] = useState<string | null>(null);

  async function test(key: string, action: () => Promise<string>) {
    setTesting(key);
    setTestError(null);
    try {
      router.push(compareHref(run.id, await action()));
    } catch (err) {
      setTestError(errorMessage(err));
      setTesting(null);
    }
  }

  const testBottleneck = (b: Bottleneck) => {
    const change = asChangeInput(b.suggested_change);
    if (change) void test(b.key, () => trySuggestedChange(run, change, b.suggested_label ?? `Tester ${b.label}`));
  };

  if (explanation.loading && !explanation.data) return <Loading label="Construction de l'explication…" />;
  if (explanation.error || !explanation.data) return <ErrorBanner message={errorMessage(explanation.error)} onRetry={explanation.reload} />;

  const e = explanation.data;
  const cards = [...e.decisions].sort((a, b) => KIND_ORDER[a.kind] - KIND_ORDER[b.kind]);
  const recommendations = (insights.data ?? []).filter((i) => i.suggested_changes.length > 0);

  return (
    <div className="space-y-6">
      <Narrative runId={run.id} />
      {testError && <ErrorBanner message={testError} />}

      <section aria-label="Décisions">
        <h2 className="mb-3 text-sm font-semibold uppercase tracking-wider text-slate-300">Décisions : pourquoi, et pourquoi pas plus</h2>
        <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-3">
          {cards.map((c) => (
            <DecisionCard key={`${c.kind}-${c.entity_id}`} card={c} currency={currency} />
          ))}
        </div>
      </section>

      <div className="grid gap-6 xl:grid-cols-2">
        <Card title="Goulots d'étranglement">
          <BottleneckList bottlenecks={e.bottlenecks} currency={currency} onTest={testBottleneck} testing={testing} measured={e.sensitivity_computed} />
        </Card>
        <Card
          title="Valeurs marginales"
          actions={
            !e.sensitivity_computed && (
              <Button onClick={marginal.start} busy={marginal.computing}>
                <Gauge className="h-4 w-4" aria-hidden="true" />
                {marginal.computing ? "Calcul en cours…" : "Mesurer par ré-optimisation"}
              </Button>
            )
          }
        >
          {marginal.error && <ErrorBanner message={marginal.error} />}
          {!e.sensitivity_computed ? (
            <p className="text-sm text-slate-400">
              Jusqu&apos;à 8 ré-optimisations testent l&apos;effet réel de relâcher les principaux goulots. Ces effets mesurés
              remplacent alors les indicateurs locaux comme valeur principale.
            </p>
          ) : marginal.report.data ? (
            <MarginalValueChart report={marginal.report.data} currency={currency} />
          ) : (
            <Loading />
          )}
        </Card>
      </div>

      <Card title="Recommandations à tester">
        {insights.loading && !insights.data ? (
          <Loading />
        ) : recommendations.length === 0 ? (
          <EmptyState title="Aucune recommandation chiffrée pour ce plan." />
        ) : (
          <div className="space-y-3">
            {recommendations.map((i) => (
              <InsightCard
                key={i.id}
                insight={i}
                busy={testing === i.id}
                onTry={() => test(i.id, async () => (await api.tryInsight(i.id)).run_id)}
              />
            ))}
          </div>
        )}
      </Card>

      {e.tradeoffs.length > 0 && (
        <Card title="Arbitrages">
          <ul className="space-y-2 text-sm text-slate-300">
            {e.tradeoffs.map((t) => (
              <li key={t.constraint_key}>{t.message}</li>
            ))}
          </ul>
        </Card>
      )}

      <Card title="Contraintes saturées">
        <BindingConstraintsTable constraints={e.binding} />
      </Card>
    </div>
  );
}

export function ExplainCenter() {
  const { run } = useRunView();
  if (!run) return null;
  if (run.status === "queued" || run.status === "running") return <Loading label="L'explication sera disponible à la fin de l'optimisation…" />;
  if (run.status !== "succeeded") return <p className="text-sm text-slate-400">Pas de plan à expliquer (statut : {run.status}).</p>;
  return <ExplainBody run={run} />;
}

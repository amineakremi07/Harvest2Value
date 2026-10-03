"use client";

import { useCallback, useState } from "react";
import { Card, ErrorBanner, Loading } from "@/components/ui/primitives";
import { errorMessage } from "@/lib/api/client";
import { api } from "@/lib/api/endpoints";
import { useApi } from "@/lib/hooks/useApi";
import { useRunView } from "@/features/optimization/RunContext";
import { EDGE_COLOR } from "./layout";
import { PeriodScrubber } from "./PeriodScrubber";
import { SupplyChainGraph } from "./SupplyChainGraph";

const LEGEND = [
  { kind: "harvest", label: "Récolte" },
  { kind: "placement", label: "Mise en stock / vente directe" },
  { kind: "sale", label: "Vente" },
  { kind: "transport", label: "Transport" },
] as const;

export function NetworkView() {
  const { run, result, runId } = useRunView();
  const [day, setDay] = useState<number | null>(null);
  const network = useApi(run?.status === "succeeded" ? () => api.network(runId, day) : null, [runId, day, run?.status]);
  const onDay = useCallback((d: number | null) => setDay(d), []);

  if (!run) return null;
  if (run.status !== "succeeded") return <Loading label="Le réseau s'affichera quand le plan sera disponible…" />;

  return (
    <Card title="Réseau logistique" actions={result && <PeriodScrubber horizon={result.horizon_days} day={day} onChange={onDay} />}>
      <ul className="mb-3 flex flex-wrap gap-4 text-xs text-slate-400" aria-label="Légende">
        {LEGEND.map((l) => (
          <li key={l.kind} className="flex items-center gap-2">
            <span className="inline-block h-0.5 w-5" style={{ backgroundColor: EDGE_COLOR[l.kind] }} aria-hidden="true" />
            {l.label}
          </li>
        ))}
      </ul>
      {network.error ? (
        <ErrorBanner message={errorMessage(network.error)} onRetry={network.reload} />
      ) : !network.data ? (
        <Loading />
      ) : (
        <div className={network.loading ? "opacity-60 transition-opacity" : undefined}>
          {network.data.edges.length === 0 && <p className="mb-2 text-sm text-slate-400">Aucun flux ce jour-là.</p>}
          <SupplyChainGraph graph={network.data} />
        </div>
      )}
    </Card>
  );
}

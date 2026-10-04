"use client";

import Link from "next/link";
import { StackedTimeline } from "@/components/charts/StackedTimeline";
import { CHART } from "@/components/charts/theme";
import { Card, EmptyState, ErrorBanner, Loading, PageHeader } from "@/components/ui/primitives";
import { ApiError, errorMessage } from "@/lib/api/client";
import { api } from "@/lib/api/endpoints";
import { fmtDate, shortId } from "@/lib/format";
import { useApi } from "@/lib/hooks/useApi";
import { AiSummary } from "./AiSummary";
import { AlertsPanel } from "./AlertsPanel";
import { ExecutiveKpis } from "./ExecutiveKpis";
import { RecentRuns } from "./RecentRuns";
import { TopRecommendations } from "./TopRecommendations";

export function DashboardView() {
  const dashboard = useApi(() => api.dashboard(), []);
  const recent = useApi(() => api.runs({ page_size: 6 }), []);

  if (dashboard.loading) return <Loading label="Chargement du tableau de bord…" />;

  if (dashboard.error instanceof ApiError && dashboard.error.code === "NO_RUN") {
    return (
      <>
        <PageHeader title="Tableau de bord" />
        <EmptyState title="Aucun plan optimisé pour l'instant.">
          <Link href="/optimize" className="text-cyan-300 underline underline-offset-2">
            Partez d&apos;un modèle et lancez une première optimisation
          </Link>
        </EmptyState>
      </>
    );
  }
  if (dashboard.error || !dashboard.data) {
    return <ErrorBanner message={errorMessage(dashboard.error)} onRetry={dashboard.reload} />;
  }

  const data = dashboard.data;
  return (
    <>
      <PageHeader
        title="Tableau de bord"
        subtitle={
          <>
            Dernier plan :{" "}
            <Link href={`/runs/${data.run.run_id}/summary`} className="text-cyan-300 underline underline-offset-2">
              {data.run.label ?? shortId(data.run.run_id)}
            </Link>{" "}
            · {fmtDate(data.run.created_at)}
            {data.baseline_run_id && (
              <>
                {" "}
                · comparé à la référence{" "}
                <Link href={`/compare?baseline=${data.baseline_run_id}&runs=${data.run.run_id}`} className="text-cyan-300 underline underline-offset-2">
                  {shortId(data.baseline_run_id)}
                </Link>
              </>
            )}
          </>
        }
      />
      <div className="space-y-6">
        <ExecutiveKpis kpis={data.kpis} deltas={data.kpi_deltas} hasBaseline={data.baseline_run_id != null} />
        <div className="grid grid-cols-1 gap-6 lg:grid-cols-3">
          <div className="space-y-6 lg:col-span-2">
            <Card title="Ventes et stock par jour">
              <StackedTimeline
                ariaLabel="Ventes, stock et pertes par jour du dernier plan"
                data={data.series.map((p) => ({ day: p.day, stock: p.stock_end_kg, sold: p.sold_kg, lost: p.lost_kg }))}
                series={[
                  { key: "stock", label: "Stock fin de jour", kind: "area", color: "#F59E0B" },
                  { key: "sold", label: "Vendu", kind: "bar", color: "#38BDF8" },
                  { key: "lost", label: "Pertes", kind: "line", color: CHART.negative },
                ]}
                height={260}
              />
            </Card>
            <AlertsPanel insights={data.top_insights} runId={data.run.run_id} />
          </div>
          <div className="space-y-6">
            <AiSummary runId={data.run.run_id} />
            <TopRecommendations data={data} />
            {recent.data && <RecentRuns runs={recent.data.items} />}
          </div>
        </div>
      </div>
    </>
  );
}

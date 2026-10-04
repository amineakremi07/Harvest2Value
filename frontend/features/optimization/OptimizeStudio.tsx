"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useState } from "react";
import { Database, LayoutTemplate } from "lucide-react";
import { Badge, Button, Card, cx, EmptyState, ErrorBanner, Loading, PageHeader } from "@/components/ui/primitives";
import { errorMessage } from "@/lib/api/client";
import { api } from "@/lib/api/endpoints";
import { fmtKg } from "@/lib/format";
import { useApi } from "@/lib/hooks/useApi";
import type { DatasetDetail, RunConfig } from "@/lib/api/types";
import { RunConfigForm } from "./RunConfigForm";

function DatasetOverview({ detail }: { detail: DatasetDetail }) {
  const { payload, validation } = detail.current_version;
  return (
    <div className="mb-5 space-y-3">
      <div className="flex flex-wrap items-center gap-2 text-sm text-slate-300">
        <span className="font-semibold text-white">{detail.dataset.name}</span>
        <Badge>v{detail.current_version.version_no}</Badge>
        <Badge tone={detail.current_version.is_valid ? "success" : "danger"}>
          {detail.current_version.is_valid ? "Valide" : "Invalide"}
        </Badge>
        <Link href={`/datasets/${detail.dataset.id}`} className="ml-auto text-xs font-semibold text-cyan-300 hover:underline">
          Modifier les données
        </Link>
      </div>
      <p className="text-sm text-slate-400">
        {payload.producer.name} · {payload.producer.region} · {payload.crops.map((c) => c.name).join(", ")} ·{" "}
        {fmtKg(payload.harvest_lots.reduce((s, l) => s + l.quantity_kg, 0))} en {payload.harvest_lots.length} lot(s) ·{" "}
        {payload.buyers.length} acheteurs · {(payload.storage_facilities ?? []).length} entrepôt(s)
      </p>
      {(validation.errors ?? []).length > 0 && (
        <ul className="list-disc pl-5 text-sm text-rose-300">
          {(validation.errors ?? []).map((e) => (
            <li key={`${e.code}-${e.path}`}>{e.message}</li>
          ))}
        </ul>
      )}
      {(validation.warnings ?? []).length > 0 && (
        <ul className="list-disc pl-5 text-xs text-amber-200/80">
          {(validation.warnings ?? []).map((w) => (
            <li key={`${w.code}-${w.path}`}>{w.message}</li>
          ))}
        </ul>
      )}
    </div>
  );
}

export function OptimizeStudio({ initialDatasetId }: { initialDatasetId?: string }) {
  const router = useRouter();
  const [datasetId, setDatasetId] = useState<string | undefined>(initialDatasetId);
  const [creatingTemplate, setCreatingTemplate] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const templates = useApi(() => api.templates(), []);
  const datasets = useApi(() => api.datasets(), []);
  const detail = useApi(datasetId ? () => api.dataset(datasetId) : null, [datasetId]);

  function select(id: string) {
    setDatasetId(id);
    setError(null);
    router.replace(`/optimize?dataset=${id}`, { scroll: false });
  }

  async function applyTemplate(key: string) {
    setCreatingTemplate(key);
    setError(null);
    try {
      const created = await api.createDatasetFromTemplate(key);
      datasets.reload();
      select(created.dataset.id);
    } catch (err) {
      setError(errorMessage(err));
    } finally {
      setCreatingTemplate(null);
    }
  }

  async function launch(config: RunConfig, label: string | null) {
    if (!datasetId) return;
    setSubmitting(true);
    setError(null);
    try {
      const run = await api.createRun({ dataset_id: datasetId, config, label, use_cache: true });
      router.push(`/runs/${run.id}/summary`);
    } catch (err) {
      setError(errorMessage(err));
      setSubmitting(false);
    }
  }

  return (
    <>
      <PageHeader title="Optimization Studio" subtitle="Choisissez des données, un objectif et un horizon, puis lancez le solveur." />
      {error && (
        <div className="mb-4">
          <ErrorBanner message={error} />
        </div>
      )}
      <div className="grid grid-cols-1 gap-6 lg:grid-cols-[minmax(0,320px)_minmax(0,1fr)]">
        <div className="space-y-6">
          <Card title="Modèles">
            {templates.loading ? (
              <Loading />
            ) : templates.error ? (
              <ErrorBanner message={errorMessage(templates.error)} onRetry={templates.reload} />
            ) : (
              <ul className="space-y-2">
                {(templates.data ?? []).map((t) => (
                  <li key={t.key} className="rounded-lg border border-card-border bg-navy-deep p-3">
                    <div className="flex items-start gap-2">
                      <LayoutTemplate className="mt-0.5 h-4 w-4 shrink-0 text-emerald-accent" aria-hidden="true" />
                      <div className="min-w-0 flex-1">
                        <p className="text-sm font-semibold text-white">{t.crops.join(", ")}</p>
                        <p className="text-xs text-slate-400">
                          {t.region} · {fmtKg(t.harvest_kg)} · {t.buyer_count} acheteurs
                        </p>
                      </div>
                    </div>
                    <Button
                      className="mt-2 w-full"
                      onClick={() => applyTemplate(t.key)}
                      busy={creatingTemplate === t.key}
                      data-testid={`use-template-${t.key}`}
                    >
                      Utiliser ce modèle
                    </Button>
                  </li>
                ))}
              </ul>
            )}
          </Card>
          <Card title="Mes jeux de données">
            {datasets.loading && !datasets.data ? (
              <Loading />
            ) : (datasets.data?.items ?? []).length === 0 ? (
              <p className="text-sm text-slate-400">Aucun jeu de données. Partez d&apos;un modèle.</p>
            ) : (
              <ul className="space-y-1">
                {(datasets.data?.items ?? []).map((d) => (
                  <li key={d.id}>
                    <button
                      type="button"
                      onClick={() => select(d.id)}
                      aria-pressed={d.id === datasetId}
                      className={cx(
                        "flex w-full items-center gap-2 rounded-lg px-2 py-1.5 text-left text-sm",
                        d.id === datasetId ? "bg-emerald-500/10 text-white" : "text-slate-300 hover:bg-white/5",
                      )}
                    >
                      <Database className="h-4 w-4 shrink-0 text-slate-500" aria-hidden="true" />
                      <span className="min-w-0 flex-1 truncate">{d.name}</span>
                      <span className="text-xs text-slate-500">v{d.current_version_no}</span>
                    </button>
                  </li>
                ))}
              </ul>
            )}
          </Card>
        </div>

        <Card title="Configuration">
          {!datasetId ? (
            <EmptyState title="Aucune donnée sélectionnée">Choisissez un modèle ou un jeu de données à gauche.</EmptyState>
          ) : detail.loading || !detail.data ? (
            detail.error ? <ErrorBanner message={errorMessage(detail.error)} onRetry={detail.reload} /> : <Loading />
          ) : (
            <>
              <DatasetOverview detail={detail.data} />
              {detail.data.current_version.is_valid ? (
                <RunConfigForm key={detail.data.dataset.id} payload={detail.data.current_version.payload} submitting={submitting} onSubmit={launch} />
              ) : (
                <p className="text-sm text-rose-300">Corrigez les erreurs de validation avant d&apos;optimiser.</p>
              )}
            </>
          )}
        </Card>
      </div>
    </>
  );
}

"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useState, type FormEvent } from "react";
import { Copy, GitBranch, GitCompare, RefreshCw, Trash2 } from "lucide-react";
import { Badge, Button, Card, ErrorBanner, inputClass, Loading, PageHeader } from "@/components/ui/primitives";
import { errorMessage } from "@/lib/api/client";
import { api } from "@/lib/api/endpoints";
import { useApi } from "@/lib/hooks/useApi";
import type { ChangeInput, RunConfig, ScenarioChangeOut, ScenarioDetail } from "@/lib/api/types";
import { RunList } from "@/features/optimization/RunList";
import { RunConfigForm } from "@/features/optimization/RunConfigForm";
import { ChangeBuilder } from "./ChangeBuilder";
import { ChangeList, moveId } from "./ChangeList";
import { DiffPreview } from "./DiffPreview";
import { ScenarioTextInput } from "./ScenarioTextInput";
import { ScenarioTree } from "./ScenarioTree";
import { ScenarioStatusBadge, StaleBadge } from "./StaleBadge";

function BranchForm({ onSubmit, busy }: { onSubmit: (name: string) => void; busy: boolean }) {
  const [name, setName] = useState("");
  const submit = (e: FormEvent) => {
    e.preventDefault();
    if (name.trim()) onSubmit(name.trim());
  };
  return (
    <form onSubmit={submit} className="flex flex-wrap items-center gap-2" aria-label="Créer une branche">
      <input className={`${inputClass} w-56`} placeholder="Nom de la branche" aria-label="Nom de la branche" value={name} onChange={(e) => setName(e.target.value)} maxLength={120} />
      <Button type="submit" busy={busy} disabled={!name.trim()}>
        Créer
      </Button>
    </form>
  );
}

export function ScenarioStudio({ scenarioId }: { scenarioId: string }) {
  const router = useRouter();
  const detail = useApi(() => api.scenario(scenarioId), [scenarioId]);
  const [previewKey, setPreviewKey] = useState(0);
  const preview = useApi(() => api.previewScenario(scenarioId), [scenarioId, previewKey]);
  const meta = useApi(() => api.meta(), []);
  const datasetId = detail.data?.scenario.dataset_id;
  const siblings = useApi(datasetId ? () => api.scenarios({ dataset_id: datasetId }) : null, [datasetId]);

  const [busy, setBusy] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [branching, setBranching] = useState(false);

  async function mutate(key: string, action: () => Promise<ScenarioDetail | void>): Promise<boolean> {
    setBusy(key);
    setError(null);
    try {
      const updated = await action();
      if (updated) detail.setData(updated);
      setPreviewKey((k) => k + 1);
      return true;
    } catch (err) {
      setError(errorMessage(err));
      return false;
    } finally {
      setBusy(null);
    }
  }

  if (detail.loading && !detail.data) return <Loading label="Chargement du scénario…" />;
  if (detail.error || !detail.data) return <ErrorBanner message={errorMessage(detail.error)} onRetry={detail.reload} />;

  const d = detail.data;
  const s = d.scenario;
  const changes = d.changes;
  const ids = [...changes].sort((a, b) => a.position - b.position).map((c) => c.id);
  const lastSucceeded = d.runs.find((r) => r.status === "succeeded");

  const addChange = (change: ChangeInput) => mutate("add", () => api.addChange(scenarioId, change));
  const toggle = (c: ScenarioChangeOut) => mutate(`toggle-${c.id}`, () => api.patchChange(scenarioId, c.id, { enabled: !c.enabled }));
  const remove = (c: ScenarioChangeOut) => mutate(`delete-${c.id}`, () => api.deleteChange(scenarioId, c.id));
  const move = (c: ScenarioChangeOut, dir: -1 | 1) => mutate(`move-${c.id}`, () => api.reorderChanges(scenarioId, moveId(ids, c.id, dir)));

  async function navigateAfter(key: string, action: () => Promise<string>) {
    setBusy(key);
    setError(null);
    try {
      router.push(await action());
    } catch (err) {
      setError(errorMessage(err));
      setBusy(null);
    }
  }

  const duplicate = () => navigateAfter("duplicate", async () => `/scenarios/${(await api.duplicateScenario(scenarioId)).scenario.id}`);
  const branch = (name: string) => navigateAfter("branch", async () => `/scenarios/${(await api.branchScenario(scenarioId, name)).scenario.id}`);
  const run = (config: RunConfig, label: string | null) =>
    navigateAfter("run", async () => `/runs/${(await api.runScenario(scenarioId, config, label ?? s.name)).id}/summary`);
  const destroy = () => {
    if (!window.confirm(`Supprimer « ${s.name} » et ses branches ?`)) return;
    void navigateAfter("delete", async () => {
      await api.deleteScenario(scenarioId, true);
      return "/scenarios";
    });
  };

  return (
    <>
      <nav aria-label="Lignée" className="mb-2 flex flex-wrap items-center gap-1 text-xs text-slate-500">
        <Link href="/scenarios" className="hover:text-slate-300">
          Scénarios
        </Link>
        {d.lineage.map((l) => (
          <span key={l.id} className="flex items-center gap-1">
            <span>/</span>
            {l.id === s.id ? (
              <span className="text-slate-300">{l.name}</span>
            ) : (
              <Link href={`/scenarios/${l.id}`} className="hover:text-slate-300">
                {l.name}
              </Link>
            )}
          </span>
        ))}
      </nav>
      <PageHeader
        title={s.name}
        subtitle={
          <span className="flex flex-wrap items-center gap-2">
            <ScenarioStatusBadge status={s.status} />
            {d.stale && <StaleBadge baseVersion={s.base_version_no} currentVersion={d.current_version_no} />}
            <span>Base : données v{s.base_version_no}</span>
            {s.description && <span>· {s.description}</span>}
          </span>
        }
        actions={
          <>
            {d.stale && (
              <Button variant="primary" onClick={() => mutate("rebase", () => api.rebaseScenario(scenarioId))} busy={busy === "rebase"}>
                <RefreshCw className="h-4 w-4" aria-hidden="true" />
                Rebaser sur v{d.current_version_no}
              </Button>
            )}
            <Button onClick={duplicate} busy={busy === "duplicate"}>
              <Copy className="h-4 w-4" aria-hidden="true" />
              Dupliquer
            </Button>
            <Button onClick={() => setBranching((b) => !b)} aria-expanded={branching}>
              <GitBranch className="h-4 w-4" aria-hidden="true" />
              Brancher
            </Button>
            {lastSucceeded && (
              <Link
                href={`/compare?runs=${lastSucceeded.id}`}
                className="inline-flex min-h-9 items-center gap-2 rounded-lg border border-card-border px-3 py-1.5 text-sm font-semibold text-slate-200 hover:border-slate-500"
              >
                <GitCompare className="h-4 w-4" aria-hidden="true" />
                Comparer
              </Link>
            )}
            <Button variant="danger" onClick={destroy} busy={busy === "delete"} aria-label="Supprimer le scénario">
              <Trash2 className="h-4 w-4" aria-hidden="true" />
            </Button>
          </>
        }
      />
      {branching && (
        <div className="mb-4 rounded-xl border border-card-border bg-card-surface p-4">
          <p className="mb-2 text-sm text-slate-400">Une branche applique d&apos;abord les modifications de ce scénario, puis les siennes.</p>
          <BranchForm onSubmit={branch} busy={busy === "branch"} />
        </div>
      )}
      {error && (
        <div className="mb-4">
          <ErrorBanner message={error} />
        </div>
      )}

      <div className="grid grid-cols-1 gap-6 xl:grid-cols-[minmax(0,1fr)_minmax(0,380px)]">
        <div className="space-y-6">
          <Card title={`Modifications (${changes.length})`}>
            <ChangeList changes={changes} applied={preview.data?.applied} onToggle={toggle} onDelete={remove} onMove={move} busy={busy !== null} />
          </Card>
          <Card title="Aperçu des données effectives">
            {preview.loading && !preview.data ? (
              <Loading />
            ) : preview.error ? (
              <ErrorBanner message={errorMessage(preview.error)} onRetry={preview.reload} />
            ) : preview.data ? (
              <DiffPreview preview={preview.data} />
            ) : null}
          </Card>
          <Card title="Exécutions du scénario">
            {d.runs.length === 0 ? <p className="text-sm text-slate-400">Pas encore exécuté.</p> : <RunList runs={d.runs} />}
          </Card>
        </div>
        <div className="space-y-6">
          <Card title="Décrire en langage naturel">
            <ScenarioTextInput scenarioId={scenarioId} onAdd={addChange} />
          </Card>
          <Card title="Ajouter une modification">
            {meta.loading ? (
              <Loading />
            ) : meta.error || !meta.data ? (
              <ErrorBanner message={errorMessage(meta.error)} onRetry={meta.reload} />
            ) : (
              <ChangeBuilder ops={meta.data.change_ops ?? []} payload={preview.data?.effective_payload} onAdd={addChange} submitting={busy === "add"} />
            )}
          </Card>
          <Card title="Optimiser ce scénario">
            {preview.data && (preview.data.validation.errors ?? []).length === 0 ? (
              <RunConfigForm
                key={s.base_version_no}
                payload={preview.data.effective_payload}
                submitting={busy === "run"}
                submitLabel="Exécuter le scénario"
                onSubmit={run}
              />
            ) : preview.data ? (
              <p className="text-sm text-rose-300">Corrigez les modifications : les données effectives sont invalides.</p>
            ) : (
              <Loading />
            )}
          </Card>
          {siblings.data && siblings.data.items.length > 1 && (
            <Card title="Arborescence">
              <ScenarioTree scenarios={siblings.data.items} activeId={s.id} />
            </Card>
          )}
          {s.tags.length > 0 && (
            <div className="flex flex-wrap gap-1">
              {s.tags.map((t) => (
                <Badge key={t}>{t}</Badge>
              ))}
            </div>
          )}
        </div>
      </div>
    </>
  );
}

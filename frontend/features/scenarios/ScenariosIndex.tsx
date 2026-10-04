"use client";

import { useRouter } from "next/navigation";
import { useId, useState, type FormEvent } from "react";
import { Button, Card, EmptyState, ErrorBanner, Field, inputClass, Loading, PageHeader } from "@/components/ui/primitives";
import { errorMessage } from "@/lib/api/client";
import { api } from "@/lib/api/endpoints";
import { useApi } from "@/lib/hooks/useApi";
import { ScenarioList } from "./ScenarioList";
import { ScenarioTree } from "./ScenarioTree";

function NewScenarioForm() {
  const router = useRouter();
  const id = useId();
  const datasets = useApi(() => api.datasets(), []);
  const [name, setName] = useState("");
  const [datasetId, setDatasetId] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const items = datasets.data?.items ?? [];
  const selected = datasetId || items[0]?.id || "";

  async function submit(event: FormEvent) {
    event.preventDefault();
    if (!name.trim() || !selected) return;
    setBusy(true);
    setError(null);
    try {
      const created = await api.createScenario({ name: name.trim(), dataset_id: selected, changes: [] });
      router.push(`/scenarios/${created.scenario.id}`);
    } catch (err) {
      setError(errorMessage(err));
      setBusy(false);
    }
  }

  if (datasets.loading) return <Loading />;
  if (items.length === 0) return <p className="text-sm text-slate-400">Créez d&apos;abord un jeu de données depuis un modèle (Optimiser).</p>;
  return (
    <form onSubmit={submit} className="space-y-3" aria-label="Nouveau scénario">
      <Field label="Nom" htmlFor={`${id}-name`}>
        <input id={`${id}-name`} className={inputClass} maxLength={120} required value={name} onChange={(e) => setName(e.target.value)} placeholder="ex. Prix −10 %" />
      </Field>
      <Field label="Données de base" htmlFor={`${id}-ds`}>
        <select id={`${id}-ds`} className={inputClass} value={selected} onChange={(e) => setDatasetId(e.target.value)}>
          {items.map((d) => (
            <option key={d.id} value={d.id}>
              {d.name} (v{d.current_version_no})
            </option>
          ))}
        </select>
      </Field>
      {error && <ErrorBanner message={error} />}
      <Button type="submit" variant="primary" busy={busy} disabled={!name.trim()}>
        Créer le scénario
      </Button>
    </form>
  );
}

export function ScenariosIndex() {
  const scenarios = useApi(() => api.scenarios(), []);
  const datasets = useApi(() => api.datasets(), []);
  const datasetNames = Object.fromEntries((datasets.data?.items ?? []).map((d) => [d.id, d.name]));
  const items = scenarios.data?.items ?? [];

  return (
    <>
      <PageHeader title="Scenario Studio" subtitle="Décrivez des « et si » comme une suite de modifications typées, puis optimisez et comparez." />
      <div className="grid grid-cols-1 gap-6 lg:grid-cols-[minmax(0,1fr)_minmax(0,320px)]">
        <Card title="Scénarios">
          {scenarios.loading && !scenarios.data ? (
            <Loading />
          ) : scenarios.error ? (
            <ErrorBanner message={errorMessage(scenarios.error)} onRetry={scenarios.reload} />
          ) : items.length === 0 ? (
            <EmptyState title="Aucun scénario pour l'instant." />
          ) : (
            <ScenarioList scenarios={items} datasetNames={datasetNames} />
          )}
        </Card>
        <div className="space-y-6">
          <Card title="Nouveau scénario">
            <NewScenarioForm />
          </Card>
          {items.length > 0 && (
            <Card title="Arborescence">
              <ScenarioTree scenarios={items} />
            </Card>
          )}
        </div>
      </div>
    </>
  );
}

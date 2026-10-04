"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useRef, useState, type FormEvent } from "react";
import { FileUp, LayoutTemplate } from "lucide-react";
import { Badge, Button, Card, EmptyState, ErrorBanner, Field, inputClass, Loading, numClass, PageHeader, Table, tdClass, thClass } from "@/components/ui/primitives";
import { errorMessage } from "@/lib/api/client";
import { api } from "@/lib/api/endpoints";
import type { ImportResult } from "@/lib/api/types";
import { useApi } from "@/lib/hooks/useApi";
import { fmtDate, fmtKg } from "@/lib/format";

/** Upload a JSON dataset (schema v2, or a v1 file converted by the backend with its assumptions). */
export function ImportPanel({ onImported, autoFocus = false }: { onImported: (result: ImportResult) => void; autoFocus?: boolean }) {
  const fileRef = useRef<HTMLInputElement>(null);
  const [name, setName] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function submit(event: FormEvent) {
    event.preventDefault();
    const file = fileRef.current?.files?.[0];
    if (!file) {
      setError("Choisissez un fichier JSON.");
      return;
    }
    setBusy(true);
    setError(null);
    try {
      onImported(await api.importDataset(file, name.trim() || undefined));
    } catch (err) {
      setError(errorMessage(err));
    } finally {
      setBusy(false);
    }
  }

  return (
    <form onSubmit={submit} className="space-y-3" aria-label="Importer un fichier de données">
      <Field label="Fichier JSON (format v2 ou v1)" htmlFor="import-file">
        <input id="import-file" ref={fileRef} type="file" autoFocus={autoFocus} accept="application/json,.json" className={`${inputClass} file:mr-3 file:rounded file:border-0 file:bg-white/10 file:px-2 file:py-1 file:text-slate-200`} />
      </Field>
      <Field label="Nom (facultatif)" htmlFor="import-name">
        <input id="import-name" className={inputClass} value={name} maxLength={120} onChange={(e) => setName(e.target.value)} placeholder="Nom du fichier par défaut" />
      </Field>
      {error && <ErrorBanner message={error} />}
      <Button type="submit" variant="primary" busy={busy}>
        <FileUp className="h-4 w-4" aria-hidden="true" />
        Importer
      </Button>
    </form>
  );
}

export function DatasetsIndex({ openImport = false }: { openImport?: boolean }) {
  const router = useRouter();
  const [q, setQ] = useState("");
  const [showArchived, setShowArchived] = useState(false);
  const datasets = useApi(() => api.datasets({ page_size: 100, q: q.trim() || undefined, archived: showArchived ? null : false }), [q, showArchived]);
  const templates = useApi(() => api.templates(), []);
  const [creating, setCreating] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  async function fromTemplate(key: string) {
    setCreating(key);
    setError(null);
    try {
      const created = await api.createDatasetFromTemplate(key);
      router.push(`/datasets/${created.dataset.id}`);
    } catch (err) {
      setError(errorMessage(err));
      setCreating(null);
    }
  }

  const items = datasets.data?.items ?? [];
  return (
    <>
      <PageHeader title="Données" subtitle="Jeux de données versionnés : créer depuis un modèle, importer (v1 ou v2), modifier, valider, exporter." />
      {error && (
        <div className="mb-4">
          <ErrorBanner message={error} />
        </div>
      )}
      <div className="grid grid-cols-1 gap-6 xl:grid-cols-[1fr_minmax(0,360px)]">
        <Card
          title="Jeux de données"
          actions={
            <>
              <input
                type="search"
                className={`${inputClass} w-48`}
                placeholder="Rechercher…"
                aria-label="Rechercher un jeu de données"
                value={q}
                onChange={(e) => setQ(e.target.value)}
              />
              <label className="flex items-center gap-2 text-xs text-slate-400">
                <input type="checkbox" checked={showArchived} onChange={(e) => setShowArchived(e.target.checked)} />
                Archivés
              </label>
            </>
          }
        >
          {datasets.loading && !datasets.data ? (
            <Loading />
          ) : datasets.error ? (
            <ErrorBanner message={errorMessage(datasets.error)} onRetry={datasets.reload} />
          ) : items.length === 0 ? (
            <EmptyState title="Aucun jeu de données.">Créez-en un depuis un modèle ou importez un fichier.</EmptyState>
          ) : (
            <Table label="Jeux de données">
              <thead>
                <tr>
                  <th className={thClass}>Nom</th>
                  <th className={thClass}>Cultures</th>
                  <th className={`${thClass} ${numClass}`}>Récolte</th>
                  <th className={`${thClass} ${numClass}`}>Acheteurs</th>
                  <th className={thClass}>Version</th>
                  <th className={thClass}>Modifié</th>
                </tr>
              </thead>
              <tbody>
                {items.map((d) => (
                  <tr key={d.id}>
                    <td className={tdClass}>
                      <Link href={`/datasets/${d.id}`} className="font-semibold text-emerald-300 hover:underline">
                        {d.name}
                      </Link>
                      {d.archived && (
                        <span className="ml-2">
                          <Badge>archivé</Badge>
                        </span>
                      )}
                    </td>
                    <td className={tdClass}>{d.crops.join(", ") || "—"}</td>
                    <td className={`${tdClass} ${numClass}`}>{fmtKg(d.harvest_kg)}</td>
                    <td className={`${tdClass} ${numClass}`}>{d.buyer_count ?? "—"}</td>
                    <td className={tdClass}>
                      v{d.current_version_no ?? "?"}{" "}
                      <Badge tone={d.is_valid ? "success" : "danger"}>{d.is_valid ? "valide" : "invalide"}</Badge>
                    </td>
                    <td className={tdClass}>{fmtDate(d.updated_at)}</td>
                  </tr>
                ))}
              </tbody>
            </Table>
          )}
        </Card>
        <div className="space-y-6">
          <Card title="Importer un fichier">
            <ImportPanel autoFocus={openImport} onImported={(result) => router.push(`/datasets/${result.dataset.dataset.id}?imported=${result.source_format}`)} />
          </Card>
          <Card title="Depuis un modèle">
            {templates.loading && !templates.data ? (
              <Loading />
            ) : templates.error ? (
              <ErrorBanner message={errorMessage(templates.error)} onRetry={templates.reload} />
            ) : (
              <ul className="space-y-2">
                {(templates.data ?? []).map((t) => (
                  <li key={t.key} className="flex items-center justify-between gap-2">
                    <span className="min-w-0 text-sm">
                      <span className="block truncate font-semibold text-slate-200">{t.name}</span>
                      <span className="text-xs text-slate-500">
                        {t.region} · {fmtKg(t.harvest_kg)} · {t.buyer_count} acheteurs
                      </span>
                    </span>
                    <Button onClick={() => fromTemplate(t.key)} busy={creating === t.key} disabled={creating !== null} aria-label={`Créer depuis le modèle ${t.name}`}>
                      <LayoutTemplate className="h-4 w-4" aria-hidden="true" />
                      Créer
                    </Button>
                  </li>
                ))}
              </ul>
            )}
          </Card>
        </div>
      </div>
    </>
  );
}

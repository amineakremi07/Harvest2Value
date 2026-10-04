"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useState } from "react";
import { CheckCircle2, Copy, Download, Play, Save, Trash2 } from "lucide-react";
import { Badge, Button, Card, cx, ErrorBanner, Field, inputClass, Loading, numClass, PageHeader, Table, tdClass, thClass } from "@/components/ui/primitives";
import { ApiError, errorMessage } from "@/lib/api/client";
import { api, downloads } from "@/lib/api/endpoints";
import type { DatasetDetail, DatasetPayload, ValidationReport } from "@/lib/api/types";
import { useApi } from "@/lib/hooks/useApi";
import { fmtDate } from "@/lib/format";
import { FieldDiffTable, ValidationSummary } from "@/features/scenarios/DiffPreview";

type Draft = { text: string; parsed: DatasetPayload | null; parseError: string | null };

export function draftOf(payload: DatasetPayload): Draft {
  return { text: JSON.stringify(payload, null, 2), parsed: payload, parseError: null };
}

export function parseDraft(text: string): Draft {
  try {
    const parsed: unknown = JSON.parse(text);
    if (typeof parsed !== "object" || parsed === null || Array.isArray(parsed)) return { text, parsed: null, parseError: "Le JSON doit être un objet." };
    return { text, parsed: parsed as DatasetPayload, parseError: null };
  } catch (err) {
    return { text, parsed: null, parseError: `JSON invalide : ${err instanceof Error ? err.message : String(err)}` };
  }
}

/** Immutable update of one numeric field of a buyer or a harvest lot. */
export function withField(payload: DatasetPayload, list: "buyers" | "harvest_lots", id: string, field: string, value: number): DatasetPayload {
  const rows = payload[list] as unknown as Record<string, unknown>[];
  return { ...payload, [list]: rows.map((row) => (row.id === id ? { ...row, [field]: value } : row)) } as DatasetPayload;
}

function NumberCell({ label, value, onChange }: { label: string; value: number; onChange: (value: number) => void }) {
  const [text, setText] = useState(String(value));
  return (
    <input
      type="number"
      inputMode="decimal"
      step="any"
      min={0}
      aria-label={label}
      className={`${inputClass} w-28 text-right font-mono`}
      value={text}
      onChange={(e) => {
        setText(e.target.value);
        const n = Number(e.target.value);
        if (e.target.value !== "" && Number.isFinite(n)) onChange(n);
      }}
    />
  );
}

function QuickEdit({ payload, onChange }: { payload: DatasetPayload; onChange: (payload: DatasetPayload) => void }) {
  return (
    <div className="space-y-6">
      <Table label="Acheteurs (édition rapide)">
        <thead>
          <tr>
            <th className={thClass}>Acheteur</th>
            <th className={`${thClass} ${numClass}`}>Prix ({payload.currency ?? "TND"}/kg)</th>
            <th className={`${thClass} ${numClass}`}>Demande max. (kg)</th>
          </tr>
        </thead>
        <tbody>
          {payload.buyers.map((b) => (
            <tr key={b.id}>
              <td className={tdClass}>{b.name}</td>
              <td className={`${tdClass} ${numClass}`}>
                <NumberCell label={`Prix de ${b.name}`} value={b.price_per_kg} onChange={(v) => onChange(withField(payload, "buyers", b.id, "price_per_kg", v))} />
              </td>
              <td className={`${tdClass} ${numClass}`}>
                <NumberCell label={`Demande max. de ${b.name}`} value={b.max_demand_kg} onChange={(v) => onChange(withField(payload, "buyers", b.id, "max_demand_kg", v))} />
              </td>
            </tr>
          ))}
        </tbody>
      </Table>
      <Table label="Lots récoltés (édition rapide)">
        <thead>
          <tr>
            <th className={thClass}>Lot</th>
            <th className={`${thClass} ${numClass}`}>Quantité (kg)</th>
            <th className={`${thClass} ${numClass}`}>Jour de disponibilité</th>
          </tr>
        </thead>
        <tbody>
          {payload.harvest_lots.map((l) => (
            <tr key={l.id}>
              <td className={`${tdClass} font-mono text-xs`}>{l.id}</td>
              <td className={`${tdClass} ${numClass}`}>
                <NumberCell label={`Quantité du lot ${l.id}`} value={l.quantity_kg} onChange={(v) => onChange(withField(payload, "harvest_lots", l.id, "quantity_kg", v))} />
              </td>
              <td className={`${tdClass} ${numClass}`}>
                <NumberCell label={`Jour du lot ${l.id}`} value={l.available_day} onChange={(v) => onChange(withField(payload, "harvest_lots", l.id, "available_day", Math.round(v)))} />
              </td>
            </tr>
          ))}
        </tbody>
      </Table>
    </div>
  );
}

function Versions({ datasetId, current }: { datasetId: string; current: number }) {
  const versions = useApi(() => api.datasetVersions(datasetId), [datasetId, current]);
  const [pair, setPair] = useState<[number, number] | null>(current > 1 ? [current - 1, current] : null);
  const diff = useApi(pair ? () => api.datasetDiff(datasetId, pair[0], pair[1]) : null, [datasetId, pair]);
  const items = versions.data?.items ?? [];
  return (
    <div className="space-y-4">
      {versions.loading && !versions.data ? (
        <Loading />
      ) : versions.error ? (
        <ErrorBanner message={errorMessage(versions.error)} onRetry={versions.reload} />
      ) : (
        <Table label="Versions">
          <thead>
            <tr>
              <th className={thClass}>Version</th>
              <th className={thClass}>Créée</th>
              <th className={thClass}>Note</th>
              <th className={thClass}>Validité</th>
              <th className={thClass}>Actions</th>
            </tr>
          </thead>
          <tbody>
            {items.map((v) => (
              <tr key={v.version_no}>
                <td className={tdClass}>
                  v{v.version_no} {v.version_no === current && <Badge tone="info">actuelle</Badge>}
                </td>
                <td className={tdClass}>{fmtDate(v.created_at)}</td>
                <td className={tdClass}>{v.note || "—"}</td>
                <td className={tdClass}>
                  <Badge tone={v.is_valid ? "success" : "danger"}>{v.is_valid ? "valide" : "invalide"}</Badge>
                </td>
                <td className={tdClass}>
                  <span className="flex flex-wrap gap-2">
                    {v.version_no > 1 && (
                      <Button variant="ghost" onClick={() => setPair([v.version_no - 1, v.version_no])} aria-label={`Différences v${v.version_no - 1} → v${v.version_no}`}>
                        Différences
                      </Button>
                    )}
                    <a href={downloads.datasetExport(datasetId, "json", v.version_no)} download className="text-xs font-semibold text-cyan-300 hover:underline" aria-label={`Exporter la version ${v.version_no} en JSON`}>
                      JSON
                    </a>
                  </span>
                </td>
              </tr>
            ))}
          </tbody>
        </Table>
      )}
      {pair && (
        <div className="space-y-2">
          <h3 className="text-sm font-semibold text-slate-300">
            Différences v{pair[0]} → v{pair[1]}
          </h3>
          {diff.loading && !diff.data ? (
            <Loading />
          ) : diff.error ? (
            <ErrorBanner message={errorMessage(diff.error)} onRetry={diff.reload} />
          ) : diff.data ? (
            <FieldDiffTable diff={diff.data.changes} label={`Différences entre v${pair[0]} et v${pair[1]}`} emptyTitle="Aucune différence." />
          ) : null}
        </div>
      )}
    </div>
  );
}

type Tab = "quick" | "json" | "versions";

/** What a save hands over to the next editor: the editor is remounted per version (fresh draft). */
type SaveNotice = { text: string; report: ValidationReport };

function Editor({ detail, notice, onSaved }: { detail: DatasetDetail; notice: SaveNotice | null; onSaved: (detail: DatasetDetail, notice?: SaveNotice) => void }) {
  const router = useRouter();
  const d = detail.dataset;
  const version = detail.current_version;
  const [tab, setTab] = useState<Tab>("quick");
  const [draft, setDraft] = useState<Draft>(() => draftOf(version.payload));
  const [quickKey, setQuickKey] = useState(0);
  const [note, setNote] = useState("");
  const [name, setName] = useState(d.name);
  const [report, setReport] = useState<ValidationReport | null>(notice?.report ?? null);
  const [busy, setBusy] = useState<string | null>(null);
  const [message, setMessage] = useState<{ tone: "ok" | "error"; text: string } | null>(notice ? { tone: "ok", text: notice.text } : null);
  const dirty = draft.text !== JSON.stringify(version.payload, null, 2);

  const setPayload = (payload: DatasetPayload) => setDraft(draftOf(payload));

  async function run(key: string, action: () => Promise<void>) {
    setBusy(key);
    setMessage(null);
    try {
      await action();
    } catch (err) {
      const text =
        err instanceof ApiError && err.code === "VERSION_CONFLICT"
          ? "Une autre version a été enregistrée entre-temps. Rechargez la page pour repartir de la dernière version."
          : errorMessage(err);
      setMessage({ tone: "error", text });
    } finally {
      setBusy(null);
    }
  }

  const validate = () =>
    run("validate", async () => {
      if (!draft.parsed) return;
      setReport(await api.validateDataset(d.id, draft.parsed));
    });

  const save = () =>
    run("save", async () => {
      if (!draft.parsed) return;
      const saved = await api.saveDatasetPayload(d.id, draft.parsed, version.version_no, note.trim() || undefined);
      onSaved(await api.dataset(d.id), { text: `Version v${saved.version_no} enregistrée.`, report: saved.validation });
    });

  const rename = () =>
    run("rename", async () => {
      await api.patchDataset(d.id, { name: name.trim() });
      onSaved(await api.dataset(d.id));
    });

  const archive = () =>
    run("archive", async () => {
      await api.patchDataset(d.id, { archived: !d.archived });
      onSaved(await api.dataset(d.id));
    });

  const duplicate = () =>
    run("duplicate", async () => {
      const copy = await api.duplicateDataset(d.id);
      router.push(`/datasets/${copy.dataset.id}`);
    });

  const remove = () => {
    if (!window.confirm(`Supprimer « ${d.name} » et toutes ses versions ?`)) return;
    void run("delete", async () => {
      await api.deleteDataset(d.id);
      router.push("/datasets");
    });
  };

  const linkButton = "inline-flex min-h-9 items-center gap-2 rounded-lg border border-card-border bg-navy-deep px-3 py-1.5 text-sm font-semibold text-slate-200 hover:border-slate-500";
  const tabs: { key: Tab; label: string }[] = [
    { key: "quick", label: "Édition rapide" },
    { key: "json", label: "JSON complet" },
    { key: "versions", label: "Versions" },
  ];

  return (
    <>
      <nav aria-label="Fil d'Ariane" className="mb-2 text-xs text-slate-500">
        <Link href="/datasets" className="hover:text-slate-300">
          Données
        </Link>{" "}
        / <span className="text-slate-300">{d.name}</span>
      </nav>
      <PageHeader
        title={d.name}
        subtitle={
          <span className="flex flex-wrap items-center gap-2">
            <span>Version v{version.version_no}</span>
            <Badge tone={version.is_valid ? "success" : "danger"}>{version.is_valid ? "valide" : "invalide"}</Badge>
            {d.archived && <Badge>archivé</Badge>}
            <span>· source {d.source}</span>
          </span>
        }
        actions={
          <>
            <Link href={`/optimize?dataset=${d.id}`} className={`${linkButton} border-emerald-500/50 text-emerald-200`}>
              <Play className="h-4 w-4" aria-hidden="true" />
              Optimiser
            </Link>
            <a href={downloads.datasetExport(d.id, "json")} download className={linkButton}>
              <Download className="h-4 w-4" aria-hidden="true" />
              JSON
            </a>
            <a href={downloads.datasetExport(d.id, "csv")} download className={linkButton}>
              <Download className="h-4 w-4" aria-hidden="true" />
              CSV
            </a>
            <Button onClick={duplicate} busy={busy === "duplicate"}>
              <Copy className="h-4 w-4" aria-hidden="true" />
              Dupliquer
            </Button>
            <Button onClick={archive} busy={busy === "archive"}>
              {d.archived ? "Désarchiver" : "Archiver"}
            </Button>
            <Button variant="danger" onClick={remove} busy={busy === "delete"} aria-label="Supprimer le jeu de données">
              <Trash2 className="h-4 w-4" aria-hidden="true" />
            </Button>
          </>
        }
      />
      {message && (
        <div className="mb-4">
          {message.tone === "error" ? (
            <ErrorBanner message={message.text} />
          ) : (
            <p role="status" className="flex items-center gap-2 rounded-xl border border-emerald-500/30 bg-emerald-500/10 px-4 py-3 text-sm text-emerald-200">
              <CheckCircle2 className="h-4 w-4" aria-hidden="true" />
              {message.text}
            </p>
          )}
        </div>
      )}
      <div className="grid grid-cols-1 gap-6 xl:grid-cols-[1fr_minmax(0,340px)]">
        <div className="space-y-4">
          <div role="tablist" aria-label="Édition des données" className="flex flex-wrap gap-1 border-b border-card-border">
            {tabs.map((t) => (
              <button
                key={t.key}
                type="button"
                role="tab"
                aria-selected={tab === t.key}
                onClick={() => {
                  if (t.key === "quick") setQuickKey((k) => k + 1);
                  setTab(t.key);
                }}
                className={cx(
                  "border-b-2 px-3 py-2 text-sm font-semibold",
                  tab === t.key ? "border-emerald-accent text-white" : "border-transparent text-slate-400 hover:text-slate-200",
                )}
              >
                {t.label}
              </button>
            ))}
          </div>
          <div role="tabpanel" aria-label={tabs.find((t) => t.key === tab)?.label}>
            {tab === "quick" &&
              (draft.parsed && Array.isArray(draft.parsed.buyers) && Array.isArray(draft.parsed.harvest_lots) ? (
                <QuickEdit key={quickKey} payload={draft.parsed} onChange={setPayload} />
              ) : (
                <ErrorBanner message={draft.parseError ?? "Corrigez le JSON pour utiliser l'édition rapide."} />
              ))}
            {tab === "json" && (
              <div className="space-y-2">
                <textarea
                  aria-label="Données au format JSON"
                  spellCheck={false}
                  className={`${inputClass} h-[60vh] font-mono text-xs leading-relaxed`}
                  value={draft.text}
                  onChange={(e) => setDraft(parseDraft(e.target.value))}
                />
                {draft.parseError && <p className="text-sm text-rose-300">{draft.parseError}</p>}
              </div>
            )}
            {tab === "versions" && <Versions datasetId={d.id} current={version.version_no} />}
          </div>
        </div>
        <div className="space-y-6">
          <Card title="Enregistrer">
            <div className="space-y-3">
              <p className="text-sm text-slate-400">
                {dirty ? "Modifications non enregistrées." : "Aucune modification."} Chaque enregistrement crée une nouvelle version ; les exécutions passées gardent la leur.
              </p>
              <Field label="Note de version" htmlFor="version-note">
                <input id="version-note" className={inputClass} maxLength={500} value={note} onChange={(e) => setNote(e.target.value)} placeholder="Ex. : prix de mars" />
              </Field>
              <div className="flex flex-wrap gap-2">
                <Button onClick={validate} busy={busy === "validate"} disabled={!draft.parsed}>
                  <CheckCircle2 className="h-4 w-4" aria-hidden="true" />
                  Valider
                </Button>
                <Button variant="primary" onClick={save} busy={busy === "save"} disabled={!draft.parsed || !dirty}>
                  <Save className="h-4 w-4" aria-hidden="true" />
                  Enregistrer v{version.version_no + 1}
                </Button>
              </div>
              {report && (
                <div className="space-y-2" aria-label="Résultat de la validation" role="region">
                  {(report.errors ?? []).length === 0 && <p className="text-sm text-emerald-300">Données valides.</p>}
                  <ValidationSummary validation={report} invalidTitle="Données invalides :" />
                </div>
              )}
            </div>
          </Card>
          <Card title="Nom">
            <div className="flex gap-2">
              <input aria-label="Nom du jeu de données" className={inputClass} value={name} maxLength={120} onChange={(e) => setName(e.target.value)} />
              <Button onClick={rename} busy={busy === "rename"} disabled={!name.trim() || name.trim() === d.name}>
                Renommer
              </Button>
            </div>
          </Card>
          {(version.validation.assumptions ?? []).length > 0 && (
            <Card title="Hypothèses retenues">
              <ul className="list-disc space-y-1 pl-5 text-sm text-slate-300">
                {(version.validation.assumptions ?? []).map((a) => (
                  <li key={`${a.code}-${a.path}`}>{a.message}</li>
                ))}
              </ul>
            </Card>
          )}
        </div>
      </div>
    </>
  );
}

export function DatasetEditor({ datasetId, importedFrom }: { datasetId: string; importedFrom?: string }) {
  const detail = useApi(() => api.dataset(datasetId), [datasetId]);
  const [notice, setNotice] = useState<SaveNotice | null>(null);
  if (detail.loading && !detail.data) return <Loading label="Chargement des données…" />;
  if (detail.error || !detail.data) return <ErrorBanner message={errorMessage(detail.error)} onRetry={detail.reload} />;
  return (
    <>
      {importedFrom && (
        <p role="status" className="mb-4 rounded-xl border border-cyan-500/30 bg-cyan-500/10 px-4 py-3 text-sm text-cyan-200">
          Fichier importé (format {importedFrom}).{importedFrom === "v1" ? " Les hypothèses retenues pour la conversion sont listées à droite." : ""}
        </p>
      )}
      <Editor
        key={detail.data.current_version.version_no}
        detail={detail.data}
        notice={notice}
        onSaved={(next, saved) => {
          setNotice(saved ?? null);
          detail.setData(next);
        }}
      />
    </>
  );
}

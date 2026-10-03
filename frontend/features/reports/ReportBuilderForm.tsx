"use client";

import { useState, type FormEvent } from "react";
import { FileText } from "lucide-react";
import { Button, ErrorBanner, Field, inputClass } from "@/components/ui/primitives";
import { errorMessage } from "@/lib/api/client";
import type { ReportSection, ReportSpec, RunSummary } from "@/lib/api/types";
import { fmtDate, shortId } from "@/lib/format";
import { AI_DISABLED_TEXT, type AiStatus } from "@/features/copilot/useAiStatus";
import { SECTION_LABEL, SECTION_ORDER } from "./ReportDocument";

export const MAX_COMPARED_RUNS = 3;
const DEFAULT_SECTIONS: ReportSection[] = ["summary", "financial", "buyers", "insights"];

/** Builds the spec; the backend computes and freezes the snapshot. */
export function buildSpec(title: string, runId: string, compared: string[], sections: ReportSection[], narrative: boolean): ReportSpec {
  const ordered = SECTION_ORDER.filter((s) => sections.includes(s) && (s !== "comparison" || compared.length > 0));
  if (compared.length > 0 && !ordered.includes("comparison")) ordered.push("comparison");
  return { title: title.trim(), run_id: runId, compare_run_ids: compared.filter((r) => r !== runId), sections: ordered, include_narrative: narrative };
}

const runName = (r: RunSummary) => `${r.label || `Exécution ${shortId(r.id)}`} · ${fmtDate(r.created_at)}`;

export function ReportBuilderForm({
  runs,
  initialRun,
  ai,
  onSubmit,
}: {
  runs: RunSummary[];
  initialRun?: string;
  ai: AiStatus;
  onSubmit: (spec: ReportSpec) => Promise<void>;
}) {
  const [title, setTitle] = useState("Rapport de plan");
  const [runId, setRunId] = useState(initialRun && runs.some((r) => r.id === initialRun) ? initialRun : (runs[0]?.id ?? ""));
  const [compared, setCompared] = useState<string[]>([]);
  const [sections, setSections] = useState<ReportSection[]>(DEFAULT_SECTIONS);
  const [narrative, setNarrative] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const toggleSection = (s: ReportSection) => setSections((list) => (list.includes(s) ? list.filter((x) => x !== s) : [...list, s]));
  const toggleRun = (id: string) =>
    setCompared((list) => (list.includes(id) ? list.filter((x) => x !== id) : list.length < MAX_COMPARED_RUNS ? [...list, id] : list));

  const spec = buildSpec(title, runId, compared, sections, narrative && ai === "enabled");
  const valid = spec.title.length > 0 && Boolean(runId) && (spec.sections ?? []).length > 0;

  async function submit(event: FormEvent) {
    event.preventDefault();
    if (!valid) return;
    setBusy(true);
    setError(null);
    try {
      await onSubmit(spec);
    } catch (err) {
      setError(errorMessage(err));
      setBusy(false);
    }
  }

  return (
    <form onSubmit={submit} className="space-y-5" aria-label="Nouveau rapport">
      <Field label="Titre" htmlFor="report-title">
        <input id="report-title" className={inputClass} value={title} maxLength={160} onChange={(e) => setTitle(e.target.value)} />
      </Field>
      <Field label="Exécution principale" htmlFor="report-run">
        <select
          id="report-run"
          className={inputClass}
          value={runId}
          onChange={(e) => {
            setRunId(e.target.value);
            setCompared((list) => list.filter((r) => r !== e.target.value));
          }}
        >
          {runs.map((r) => (
            <option key={r.id} value={r.id}>
              {runName(r)}
            </option>
          ))}
        </select>
      </Field>
      <fieldset className="space-y-2">
        <legend className="text-xs font-semibold uppercase tracking-wider text-slate-400">Sections</legend>
        <div className="grid grid-cols-2 gap-2 md:grid-cols-4">
          {SECTION_ORDER.filter((s) => s !== "comparison").map((s) => (
            <label key={s} className="flex items-center gap-2 text-sm text-slate-200">
              <input type="checkbox" checked={sections.includes(s)} onChange={() => toggleSection(s)} />
              {SECTION_LABEL[s]}
            </label>
          ))}
        </div>
      </fieldset>
      <fieldset className="space-y-2">
        <legend className="text-xs font-semibold uppercase tracking-wider text-slate-400">
          Exécutions à comparer (jusqu&apos;à {MAX_COMPARED_RUNS}, même culture)
        </legend>
        <div className="max-h-48 space-y-1 overflow-y-auto">
          {runs
            .filter((r) => r.id !== runId)
            .map((r) => (
              <label key={r.id} className="flex items-center gap-2 text-sm text-slate-200">
                <input
                  type="checkbox"
                  checked={compared.includes(r.id)}
                  disabled={!compared.includes(r.id) && compared.length >= MAX_COMPARED_RUNS}
                  onChange={() => toggleRun(r.id)}
                />
                {runName(r)}
              </label>
            ))}
        </div>
        {compared.length > 0 && <p className="text-xs text-slate-500">La section « Comparaison » est ajoutée automatiquement.</p>}
      </fieldset>
      <label className="flex items-start gap-2 text-sm text-slate-200">
        <input type="checkbox" checked={narrative && ai === "enabled"} disabled={ai !== "enabled"} onChange={(e) => setNarrative(e.target.checked)} />
        <span>
          Inclure un récit rédigé par l&apos;IA (chiffres vérifiés)
          {ai === "disabled" && <span className="block text-xs text-slate-500">{AI_DISABLED_TEXT}</span>}
        </span>
      </label>
      <p className="text-xs text-slate-500">
        Le rapport est une copie figée : il ne changera plus, même si les données, scénarios ou exécutions sont modifiés ensuite.
      </p>
      {error && <ErrorBanner message={error} />}
      <Button type="submit" variant="primary" busy={busy} disabled={!valid}>
        <FileText className="h-4 w-4" aria-hidden="true" />
        Créer le rapport
      </Button>
    </form>
  );
}

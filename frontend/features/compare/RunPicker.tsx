"use client";

import { useId } from "react";
import { Field, inputClass } from "@/components/ui/primitives";
import { fmtDate, shortId } from "@/lib/format";
import type { RunSummary } from "@/lib/api/types";

export const MAX_COMPARED = 3;

export function runOptionLabel(r: RunSummary): string {
  return `${r.label ?? shortId(r.id)}${r.scenario_id ? " · scénario" : ""} · ${fmtDate(r.created_at)}`;
}

/** Most recent baseline (non-scenario) run of the same dataset as the first compared run. */
export function defaultBaseline(runs: RunSummary[], runIds: string[]): string | undefined {
  const first = runs.find((r) => r.id === runIds[0]);
  const candidates = runs
    .filter((r) => !runIds.includes(r.id) && r.status === "succeeded")
    .filter((r) => !first || r.dataset_id === first.dataset_id)
    .sort((a, b) => b.created_at.localeCompare(a.created_at));
  return (candidates.find((r) => r.scenario_id === null) ?? candidates[0])?.id;
}

export function RunPicker({
  runs,
  baselineId,
  runIds,
  onChange,
}: {
  runs: RunSummary[];
  baselineId: string | undefined;
  runIds: string[];
  onChange: (baselineId: string | undefined, runIds: string[]) => void;
}) {
  const id = useId();
  const baseline = runs.find((r) => r.id === baselineId);
  // Runs of another crop/dataset are usually incomparable: list the baseline's dataset first.
  const candidates = runs.filter((r) => r.id !== baselineId);
  const sameDataset = baseline ? candidates.filter((r) => r.dataset_id === baseline.dataset_id) : candidates;
  const others = baseline ? candidates.filter((r) => r.dataset_id !== baseline.dataset_id) : [];

  function toggle(runId: string) {
    if (runIds.includes(runId)) onChange(baselineId, runIds.filter((x) => x !== runId));
    else if (runIds.length < MAX_COMPARED) onChange(baselineId, [...runIds, runId]);
  }

  const option = (r: RunSummary) => {
    const checked = runIds.includes(r.id);
    return (
      <li key={r.id}>
        <label className="flex items-center gap-2 py-1 text-sm text-slate-200">
          <input type="checkbox" checked={checked} disabled={!checked && runIds.length >= MAX_COMPARED} onChange={() => toggle(r.id)} />
          {runOptionLabel(r)}
        </label>
      </li>
    );
  };

  return (
    <div className="grid grid-cols-1 gap-4 md:grid-cols-[minmax(0,1fr)_minmax(0,2fr)]">
      <Field label="Référence" htmlFor={`${id}-baseline`}>
        <select
          id={`${id}-baseline`}
          className={inputClass}
          value={baselineId ?? ""}
          onChange={(e) => onChange(e.target.value || undefined, runIds.filter((x) => x !== e.target.value))}
        >
          <option value="">— choisir —</option>
          {runs.map((r) => (
            <option key={r.id} value={r.id}>
              {runOptionLabel(r)}
            </option>
          ))}
        </select>
      </Field>
      <fieldset>
        <legend className="mb-1 text-xs font-semibold uppercase tracking-wider text-slate-400">
          Exécutions comparées ({runIds.length}/{MAX_COMPARED})
        </legend>
        <ul className="max-h-48 overflow-y-auto rounded-lg border border-card-border bg-navy-deep px-3 py-1">
          {sameDataset.map(option)}
          {others.length > 0 && <li className="pt-2 text-xs text-slate-500">Autres jeux de données</li>}
          {others.map(option)}
        </ul>
      </fieldset>
    </div>
  );
}

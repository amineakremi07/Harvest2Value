"use client";

import { useId, useState, type FormEvent } from "react";
import { Play } from "lucide-react";
import { Button, Field, inputClass } from "@/components/ui/primitives";
import type { DatasetPayload, ObjectiveKind, RunConfig } from "@/lib/api/types";
import { harvestedCrops, MAX_HORIZON_DAYS, suggestedHorizon } from "./horizon";
import { ObjectivePicker } from "./ObjectivePicker";

export interface RunConfigDraft {
  cropId: string;
  objective: ObjectiveKind;
  horizonDays: string;
  timeLimitS: string;
  gapPct: string;
  salvageValuePct: string;
  disposalCostPerKg: string;
  serviceLevelPct: string;
  minProfit: string;
  weightProfit: string;
  weightWaste: string;
  weightCost: string;
  label: string;
}

export function initialDraft(payload: DatasetPayload, config?: Partial<RunConfig>): RunConfigDraft {
  const crops = harvestedCrops(payload);
  const cropId = config?.crop_id ?? crops[0]?.id ?? "";
  const str = (v: number | null | undefined, fallback = "") => (v == null ? fallback : String(v));
  return {
    cropId,
    objective: config?.objective ?? "profit",
    horizonDays: str(config?.horizon_days, String(suggestedHorizon(payload, cropId))),
    timeLimitS: str(config?.time_limit_s),
    gapPct: config?.gap == null ? "" : String(config.gap * 100),
    salvageValuePct: str(config?.salvage_value_pct, "0"),
    disposalCostPerKg: str(config?.disposal_cost_per_kg, "0"),
    serviceLevelPct: config?.service_level_min == null ? "80" : String(config.service_level_min * 100),
    minProfit: str(config?.min_profit),
    weightProfit: str(config?.weights?.profit, "1"),
    weightWaste: str(config?.weights?.waste, "0.5"),
    weightCost: str(config?.weights?.cost, "0"),
    label: "",
  };
}

function num(value: string): number | null {
  if (value.trim() === "") return null;
  const n = Number(value.replace(",", "."));
  return Number.isFinite(n) ? n : null;
}

/** Turns the form state into a RunConfig; only the parameters of the chosen objective are sent. */
export function buildRunConfig(draft: RunConfigDraft, cropCount: number): RunConfig {
  const config: RunConfig = {
    objective: draft.objective,
    crop_id: cropCount > 1 ? draft.cropId : null,
    horizon_days: num(draft.horizonDays),
    time_limit_s: num(draft.timeLimitS),
    gap: num(draft.gapPct) == null ? null : (num(draft.gapPct) as number) / 100,
    salvage_value_pct: num(draft.salvageValuePct) ?? 0,
    disposal_cost_per_kg: num(draft.disposalCostPerKg) ?? 0,
  };
  if (draft.objective === "weighted") {
    config.weights = {
      profit: num(draft.weightProfit) ?? 0,
      waste: num(draft.weightWaste) ?? 0,
      cost: num(draft.weightCost) ?? 0,
    };
  }
  if (draft.objective === "cost") config.service_level_min = (num(draft.serviceLevelPct) ?? 0) / 100;
  if (draft.objective === "waste") config.min_profit = num(draft.minProfit);
  return config;
}

export function validateDraft(draft: RunConfigDraft): string | null {
  const horizon = num(draft.horizonDays);
  if (horizon !== null && (!Number.isInteger(horizon) || horizon < 1 || horizon > MAX_HORIZON_DAYS)) {
    return `L'horizon doit être un entier entre 1 et ${MAX_HORIZON_DAYS} jours.`;
  }
  if (draft.objective === "weighted") {
    const total = (num(draft.weightProfit) ?? 0) + (num(draft.weightWaste) ?? 0) + (num(draft.weightCost) ?? 0);
    if (total <= 0) return "Au moins un poids doit être strictement positif.";
  }
  if (draft.objective === "cost") {
    const level = num(draft.serviceLevelPct);
    if (level === null || level < 0 || level > 100) return "Le taux de vente minimal doit être entre 0 et 100 %.";
  }
  return null;
}

export function RunConfigForm({
  payload,
  initialConfig,
  submitting = false,
  submitLabel = "Lancer l'optimisation",
  onSubmit,
}: {
  payload: DatasetPayload;
  initialConfig?: Partial<RunConfig>;
  submitting?: boolean;
  submitLabel?: string;
  onSubmit: (config: RunConfig, label: string | null) => void;
}) {
  const [draft, setDraft] = useState<RunConfigDraft>(() => initialDraft(payload, initialConfig));
  const [error, setError] = useState<string | null>(null);
  const [advanced, setAdvanced] = useState(false);
  const id = useId();
  const crops = harvestedCrops(payload);
  const suggested = suggestedHorizon(payload, draft.cropId);

  const set = <K extends keyof RunConfigDraft>(key: K, value: RunConfigDraft[K]) =>
    setDraft((d) => ({ ...d, [key]: value }));

  function submit(event: FormEvent) {
    event.preventDefault();
    const problem = validateDraft(draft);
    setError(problem);
    if (problem) return;
    onSubmit(buildRunConfig(draft, crops.length), draft.label.trim() || null);
  }

  return (
    <form onSubmit={submit} className="space-y-5" aria-label="Configuration de l'exécution">
      <ObjectivePicker value={draft.objective} onChange={(o) => set("objective", o)} />

      <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
        {crops.length > 1 && (
          <Field label="Culture" htmlFor={`${id}-crop`}>
            <select
              id={`${id}-crop`}
              className={inputClass}
              value={draft.cropId}
              onChange={(e) => {
                const cropId = e.target.value;
                setDraft((d) => ({ ...d, cropId, horizonDays: String(suggestedHorizon(payload, cropId)) }));
              }}
            >
              {crops.map((c) => (
                <option key={c.id} value={c.id}>
                  {c.name}
                </option>
              ))}
            </select>
          </Field>
        )}
        <Field
          label="Horizon (jours)"
          htmlFor={`${id}-horizon`}
          hint={
            <>
              Suggéré : {suggested} j{" "}
              {draft.horizonDays !== String(suggested) && (
                <button type="button" className="text-cyan-300 underline" onClick={() => set("horizonDays", String(suggested))}>
                  rétablir
                </button>
              )}
            </>
          }
        >
          <input
            id={`${id}-horizon`}
            className={inputClass}
            inputMode="numeric"
            value={draft.horizonDays}
            onChange={(e) => set("horizonDays", e.target.value)}
          />
        </Field>
        <Field label="Libellé (optionnel)" htmlFor={`${id}-label`}>
          <input
            id={`${id}-label`}
            className={inputClass}
            maxLength={120}
            placeholder="ex. Référence saison"
            value={draft.label}
            onChange={(e) => set("label", e.target.value)}
          />
        </Field>

        {draft.objective === "weighted" && (
          <>
            <Field label="Poids profit" htmlFor={`${id}-wp`}>
              <input id={`${id}-wp`} className={inputClass} value={draft.weightProfit} onChange={(e) => set("weightProfit", e.target.value)} />
            </Field>
            <Field label="Poids pertes" htmlFor={`${id}-ww`}>
              <input id={`${id}-ww`} className={inputClass} value={draft.weightWaste} onChange={(e) => set("weightWaste", e.target.value)} />
            </Field>
            <Field label="Poids coûts" htmlFor={`${id}-wc`}>
              <input id={`${id}-wc`} className={inputClass} value={draft.weightCost} onChange={(e) => set("weightCost", e.target.value)} />
            </Field>
          </>
        )}
        {draft.objective === "cost" && (
          <Field label="Taux de vente minimal (%)" htmlFor={`${id}-sl`}>
            <input id={`${id}-sl`} className={inputClass} value={draft.serviceLevelPct} onChange={(e) => set("serviceLevelPct", e.target.value)} />
          </Field>
        )}
        {draft.objective === "waste" && (
          <Field label="Profit minimal (optionnel)" htmlFor={`${id}-mp`}>
            <input id={`${id}-mp`} className={inputClass} value={draft.minProfit} onChange={(e) => set("minProfit", e.target.value)} />
          </Field>
        )}
      </div>

      <div>
        <button type="button" className="text-xs font-semibold text-slate-400 hover:text-slate-200" aria-expanded={advanced} onClick={() => setAdvanced((a) => !a)}>
          {advanced ? "▾" : "▸"} Paramètres avancés
        </button>
        {advanced && (
          <div className="mt-3 grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
            <Field label="Limite de temps (s)" htmlFor={`${id}-tl`} hint="Vide : valeur du serveur">
              <input id={`${id}-tl`} className={inputClass} value={draft.timeLimitS} onChange={(e) => set("timeLimitS", e.target.value)} />
            </Field>
            <Field label="Écart MIP (%)" htmlFor={`${id}-gap`} hint="Vide : 1 %">
              <input id={`${id}-gap`} className={inputClass} value={draft.gapPct} onChange={(e) => set("gapPct", e.target.value)} />
            </Field>
            <Field label="Valeur résiduelle du stock (%)" htmlFor={`${id}-sv`}>
              <input id={`${id}-sv`} className={inputClass} value={draft.salvageValuePct} onChange={(e) => set("salvageValuePct", e.target.value)} />
            </Field>
            <Field label="Coût d'élimination (/kg)" htmlFor={`${id}-dc`}>
              <input id={`${id}-dc`} className={inputClass} value={draft.disposalCostPerKg} onChange={(e) => set("disposalCostPerKg", e.target.value)} />
            </Field>
          </div>
        )}
      </div>

      {error && (
        <p role="alert" className="text-sm text-rose-300">
          {error}
        </p>
      )}
      <Button type="submit" variant="primary" busy={submitting}>
        <Play className="h-4 w-4" aria-hidden="true" />
        {submitLabel}
      </Button>
    </form>
  );
}

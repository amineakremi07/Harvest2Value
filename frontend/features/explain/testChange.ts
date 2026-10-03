import { api } from "@/lib/api/endpoints";
import type { ChangeInput, RunDetail } from "@/lib/api/types";

/** Narrows a backend `suggested_change` (an untyped dict) to a change, or null if malformed. */
export function asChangeInput(value: Record<string, unknown> | null | undefined): ChangeInput | null {
  if (!value || typeof value.op !== "string") return null;
  const target = typeof value.target === "string" ? value.target : null;
  const params = typeof value.params === "object" && value.params !== null ? (value.params as Record<string, unknown>) : {};
  return { op: value.op, target, params };
}

/** Compare page of a baseline run against a trial run. */
export function compareHref(baselineRunId: string, trialRunId: string): string {
  return `/compare?baseline=${baselineRunId}&runs=${trialRunId}`;
}

/**
 * Tries a suggested change: a scenario on top of the run's own scenario (or of its dataset
 * version), optimized with the same configuration. Returns the trial run id.
 */
export async function trySuggestedChange(run: RunDetail, change: ChangeInput, name: string): Promise<string> {
  const base = run.scenario_id
    ? { parent_id: run.scenario_id }
    : { dataset_id: run.dataset_id, version_no: run.version_no };
  const scenario = await api.createScenario({
    name: name.slice(0, 120),
    ...base,
    changes: [{ ...change, source: "recommendation" }],
  });
  const trial = await api.runScenario(scenario.scenario.id, run.config, name.slice(0, 120));
  return trial.id;
}

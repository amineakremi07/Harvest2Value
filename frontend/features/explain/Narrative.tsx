"use client";

import { api } from "@/lib/api/endpoints";
import { NarrativeCard } from "@/features/copilot/NarrativeCard";

/** LLM narrative of the plan, written from the same verified facts as the copilot. */
export function Narrative({ runId }: { runId: string }) {
  return (
    <NarrativeCard
      title="Récit du plan"
      load={() => api.runNarrative(runId)}
      hint="L'IA résume le plan à partir des résultats, explications et alertes calculés par le backend. Chaque chiffre est vérifié."
    />
  );
}

"use client";

import { api } from "@/lib/api/endpoints";
import { NarrativeCard } from "@/features/copilot/NarrativeCard";

/** AI summary of the dashboard's run; the figures next to it come from the solver. */
export function AiSummary({ runId }: { runId: string }) {
  return (
    <NarrativeCard
      key={runId}
      title="Synthèse IA"
      load={() => api.runNarrative(runId)}
      hint="Résumé du dernier plan rédigé par l'IA à partir des résultats du solveur ; chaque chiffre est vérifié."
    />
  );
}

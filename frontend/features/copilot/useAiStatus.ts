"use client";

import { api } from "@/lib/api/endpoints";
import { useApi } from "@/lib/hooks/useApi";

export type AiStatus = "loading" | "enabled" | "disabled" | "unreachable";

/** Whether an LLM key is configured (GET /meta). Without one the app works, the AI parts say so. */
export function useAiStatus(): AiStatus {
  const meta = useApi(() => api.meta(), []);
  if (meta.error) return "unreachable";
  if (!meta.data) return "loading";
  return meta.data.llm.configured ? "enabled" : "disabled";
}

export const AI_DISABLED_TEXT =
  "IA désactivée : aucune clé LLM n'est configurée sur le serveur (LLM_API_KEY). Toutes les autres fonctions restent disponibles.";

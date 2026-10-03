import type { Tone } from "@/components/ui/primitives";
import type { ObjectiveKind, RunStatus } from "@/lib/api/types";

export const RUN_STATUS_LABEL: Record<RunStatus, string> = {
  queued: "En file",
  running: "En cours",
  succeeded: "Terminé",
  infeasible: "Infaisable",
  timeout: "Délai dépassé",
  failed: "Échec",
  cancelled: "Annulé",
  interrupted: "Interrompu",
};

export const RUN_STATUS_TONE: Record<RunStatus, Tone> = {
  queued: "info",
  running: "info",
  succeeded: "success",
  infeasible: "warning",
  timeout: "warning",
  failed: "danger",
  cancelled: "neutral",
  interrupted: "danger",
};

export const OBJECTIVE_LABEL: Record<ObjectiveKind, string> = {
  profit: "Profit",
  revenue: "Chiffre d'affaires",
  waste: "Pertes",
  cost: "Coûts",
  weighted: "Pondéré",
};

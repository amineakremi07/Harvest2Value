import type { DecisionCard } from "@/lib/api/types";

type LimitingCode = NonNullable<DecisionCard["limiting_factor"]>["code"];

/** Short French title of each limiting factor (backend `domain/explanation.py`, checked in this order). */
export const LIMITING_LABEL: Record<LimitingCode, string> = {
  UNPROFITABLE: "Non rentable",
  DEMAND_CAP: "Demande maximale atteinte",
  DAILY_DEMAND_CAP: "Plafond journalier atteint",
  FLEET_TIME: "Flotte saturée",
  COLD_CHAIN: "Chaîne du froid",
  SHELF_LIFE_WINDOW: "Fenêtre de conservation",
  MOQ: "Commande minimale",
  OPPORTUNITY: "Meilleurs débouchés ailleurs",
  STORAGE_CAP: "Entrepôt plein",
};

export const FAMILY_LABEL: Record<string, string> = {
  storage_capacity: "Capacité de stockage",
  demand_max: "Demande maximale",
  demand_day: "Demande journalière",
  demand_min: "Contrat minimum",
  moq_min: "Commande minimale",
  trip_capacity: "Capacité des trajets",
  fleet_time: "Heures de conduite",
  fleet_trips: "Trajets par jour",
  trip_duration: "Durée du trajet",
  cold_chain_vehicle: "Chaîne du froid (véhicule)",
  cold_chain_storage: "Chaîne du froid (entrepôt)",
  service_level: "Taux de vente minimal",
  min_profit: "Profit minimal",
};

export function familyLabel(family: string): string {
  return FAMILY_LABEL[family] ?? family.replace(/_/g, " ");
}

export const DUAL_TOOLTIP =
  "Valeur duale : variation locale de l'objectif pour +1 unité de la contrainte, les décisions entières " +
  "(trajets, acheteurs servis) étant figées. Elle ne vaut que pour une très petite variation et peut être " +
  "nulle ou trompeuse quand plusieurs contraintes se partagent la limite. La valeur mesurée par " +
  "ré-optimisation (perturbation) fait foi.";

export const PROBE_TOOLTIP =
  "Effet mesuré : le modèle est ré-optimisé avec la modification proposée (nombres entiers compris). " +
  "« Non significatif » signifie que l'écart reste dans la marge d'optimalité du solveur.";

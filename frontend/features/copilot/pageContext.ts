import type { PageContext } from "@/lib/api/types";

/** What the user has on screen, sent with each copilot message (the backend re-validates it). */
export function contextFromLocation(pathname: string, search: URLSearchParams): PageContext {
  const context: PageContext = { page: pathname, compare_run_ids: [], run_id: null, dataset_id: null, scenario_id: null };
  const run = pathname.match(/^\/runs\/([^/]+)/);
  if (run) context.run_id = decodeURIComponent(run[1]);
  const scenario = pathname.match(/^\/scenarios\/([^/]+)/);
  if (scenario) context.scenario_id = decodeURIComponent(scenario[1]);
  if (pathname.startsWith("/optimize") && search.get("dataset")) context.dataset_id = search.get("dataset");
  if (pathname.startsWith("/analytics") && search.get("run")) context.run_id = search.get("run");
  if (pathname.startsWith("/compare")) {
    const baseline = search.get("baseline");
    const runs = (search.get("runs") ?? "").split(",").filter(Boolean);
    if (baseline) context.run_id = baseline;
    context.compare_run_ids = runs.filter((r) => r !== baseline).slice(0, 4);
  }
  return context;
}

export const SUGGESTIONS = [
  "Pourquoi ce plan ? Quel est le profit réalisé ?",
  "Quel est le principal goulot d'étranglement ?",
  "Pourquoi l'acheteur le mieux payé ne reçoit-il pas plus ?",
  "Crée un scénario où le prix de tous les acheteurs baisse de 10 %",
] as const;

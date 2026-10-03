import Link from "next/link";
import { Badge, Table, tdClass, thClass } from "@/components/ui/primitives";
import { fmtDate } from "@/lib/format";
import type { ScenarioSummary } from "@/lib/api/types";
import { ScenarioStatusBadge, StaleBadge } from "./StaleBadge";

export function ScenarioList({ scenarios, datasetNames = {} }: { scenarios: ScenarioSummary[]; datasetNames?: Record<string, string> }) {
  const names = new Map(scenarios.map((s) => [s.id, s.name]));
  return (
    <Table label="Scénarios">
      <thead>
        <tr>
          <th className={thClass}>Scénario</th>
          <th className={thClass}>Statut</th>
          <th className={thClass}>Données</th>
          <th className={thClass}>Parent</th>
          <th className={thClass}>Dernière exécution</th>
          <th className={thClass}>Mis à jour</th>
        </tr>
      </thead>
      <tbody>
        {scenarios.map((s) => (
          <tr key={s.id}>
            <td className={tdClass}>
              <Link href={`/scenarios/${s.id}`} className="font-medium text-cyan-300 hover:underline">
                {s.name}
              </Link>
              {s.tags.map((t) => (
                <span key={t} className="ml-2">
                  <Badge>{t}</Badge>
                </span>
              ))}
            </td>
            <td className={tdClass}>
              {s.status === "stale" ? <StaleBadge baseVersion={s.base_version_no} /> : <ScenarioStatusBadge status={s.status} />}
            </td>
            <td className={tdClass}>
              {datasetNames[s.dataset_id] ?? s.dataset_id} <span className="text-slate-500">v{s.base_version_no}</span>
            </td>
            <td className={tdClass}>{s.parent_id ? (names.get(s.parent_id) ?? "—") : "—"}</td>
            <td className={tdClass}>
              {s.latest_run_id ? (
                <Link href={`/runs/${s.latest_run_id}/summary`} className="text-cyan-300 hover:underline">
                  voir
                </Link>
              ) : (
                <span className="text-slate-500">—</span>
              )}
            </td>
            <td className={`${tdClass} text-slate-400`}>{fmtDate(s.updated_at)}</td>
          </tr>
        ))}
      </tbody>
    </Table>
  );
}

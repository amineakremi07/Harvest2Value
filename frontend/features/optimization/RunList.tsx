"use client";

import Link from "next/link";
import { Badge, cx, numClass, Table, tdClass, thClass } from "@/components/ui/primitives";
import { fmtDate, fmtKg, fmtMoney, fmtPct, shortId } from "@/lib/format";
import type { RunSummary } from "@/lib/api/types";
import { OBJECTIVE_LABEL, RUN_STATUS_LABEL, RUN_STATUS_TONE } from "./runStatus";

export function RunList({ runs, datasetNames = {} }: { runs: RunSummary[]; datasetNames?: Record<string, string> }) {
  return (
    <Table label="Exécutions">
      <thead>
        <tr>
          <th className={thClass}>Exécution</th>
          <th className={thClass}>Statut</th>
          <th className={thClass}>Données</th>
          <th className={thClass}>Objectif</th>
          <th className={cx(thClass, "text-right")}>Profit réalisé</th>
          <th className={cx(thClass, "text-right")}>Vendu</th>
          <th className={cx(thClass, "text-right")}>Pertes</th>
          <th className={thClass}>Créée</th>
        </tr>
      </thead>
      <tbody>
        {runs.map((r) => (
          <tr key={r.id} className="hover:bg-white/[0.02]">
            <td className={tdClass}>
              <Link href={`/runs/${r.id}/summary`} className="font-medium text-cyan-300 hover:underline">
                {r.label ?? shortId(r.id)}
              </Link>
              {r.scenario_id && (
                <span className="ml-2">
                  <Badge tone="info">scénario</Badge>
                </span>
              )}
            </td>
            <td className={tdClass}>
              <Badge tone={RUN_STATUS_TONE[r.status]}>{RUN_STATUS_LABEL[r.status]}</Badge>
            </td>
            <td className={tdClass}>
              {datasetNames[r.dataset_id] ?? shortId(r.dataset_id)} <span className="text-slate-500">v{r.version_no}</span>
            </td>
            <td className={tdClass}>{OBJECTIVE_LABEL[r.objective]}</td>
            <td className={cx(tdClass, numClass)}>{fmtMoney(r.headline?.realized_profit)}</td>
            <td className={cx(tdClass, numClass)}>{fmtKg(r.headline?.sold_kg)}</td>
            <td className={cx(tdClass, numClass)}>{fmtPct(r.headline?.waste_rate_pct)}</td>
            <td className={cx(tdClass, "text-slate-400")}>{fmtDate(r.created_at)}</td>
          </tr>
        ))}
      </tbody>
    </Table>
  );
}

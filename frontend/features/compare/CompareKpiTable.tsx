import { Badge, cx, numClass, Table, tdClass, thClass } from "@/components/ui/primitives";
import { fmtSigned, fmtUnit } from "@/lib/format";
import type { Delta, KpiRow } from "@/lib/api/types";

/** Whether a delta is an improvement given the KPI's direction (null = neutral or no change). */
export function deltaQuality(delta: Delta | undefined, better: KpiRow["better"]): boolean | null {
  if (!delta || delta.abs == null || delta.abs === 0 || better === "neutral") return null;
  return better === "higher" ? delta.abs > 0 : delta.abs < 0;
}

export function CompareKpiTable({
  rows,
  baselineId,
  runIds,
  labels,
  currency,
}: {
  rows: KpiRow[];
  baselineId: string;
  runIds: string[];
  labels: Record<string, string>;
  currency?: string;
}) {
  return (
    <Table label="Comparaison des indicateurs">
      <thead>
        <tr>
          <th className={thClass}>Indicateur</th>
          <th className={cx(thClass, "text-right")}>
            {labels[baselineId]} <span className="font-normal normal-case text-slate-500">(référence)</span>
          </th>
          {runIds.map((id) => (
            <th key={id} className={cx(thClass, "text-right")}>
              {labels[id]}
            </th>
          ))}
        </tr>
      </thead>
      <tbody>
        {rows.map((row) => (
          <tr key={row.kpi} data-kpi={row.kpi}>
            <th scope="row" className={cx(tdClass, "font-medium")}>
              {row.label}
            </th>
            <td className={cx(tdClass, numClass)}>
              {fmtUnit(row.values[baselineId], row.unit, currency)}
              {row.best_run_id === baselineId && (
                <span className="ml-2">
                  <Badge tone="success">meilleur</Badge>
                </span>
              )}
            </td>
            {runIds.map((id) => {
              const delta = row.deltas[id];
              const quality = deltaQuality(delta, row.better);
              return (
                <td key={id} className={cx(tdClass, numClass)}>
                  <div>
                    {fmtUnit(row.values[id], row.unit, currency)}
                    {row.best_run_id === id && (
                      <span className="ml-2">
                        <Badge tone="success">meilleur</Badge>
                      </span>
                    )}
                  </div>
                  {delta && delta.abs != null && (
                    <div
                      className={cx(
                        "text-xs",
                        quality === null ? "text-slate-500" : quality ? "text-emerald-300" : "text-rose-300",
                      )}
                    >
                      {fmtSigned(delta.abs)}
                      {delta.pct != null && ` (${fmtSigned(delta.pct, " %")})`}
                    </div>
                  )}
                </td>
              );
            })}
          </tr>
        ))}
      </tbody>
    </Table>
  );
}

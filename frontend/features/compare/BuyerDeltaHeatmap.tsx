import type { CSSProperties } from "react";
import { Badge, cx, numClass, Table, tdClass, thClass } from "@/components/ui/primitives";
import { fmtKg, fmtSigned } from "@/lib/format";
import type { BuyerRow } from "@/lib/api/types";

/** Diverging color: green when a buyer receives more than in the baseline, red when less. */
export function heatStyle(delta: number | null | undefined, maxAbs: number): CSSProperties | undefined {
  if (delta == null || delta === 0 || maxAbs <= 0) return undefined;
  const alpha = (0.15 + 0.55 * Math.min(1, Math.abs(delta) / maxAbs)).toFixed(2);
  return { backgroundColor: delta > 0 ? `rgba(16, 185, 129, ${alpha})` : `rgba(244, 63, 94, ${alpha})` };
}

export function BuyerDeltaHeatmap({
  rows,
  baselineId,
  runIds,
  labels,
}: {
  rows: BuyerRow[];
  baselineId: string;
  runIds: string[];
  labels: Record<string, string>;
}) {
  const maxAbs = Math.max(0, ...rows.flatMap((r) => runIds.map((id) => Math.abs(r.cells[id]?.delta_kg ?? 0))));
  return (
    <Table label="Volumes par acheteur et écarts à la référence">
      <thead>
        <tr>
          <th className={thClass}>Acheteur</th>
          <th className={cx(thClass, "text-right")}>{labels[baselineId]} (kg)</th>
          {runIds.map((id) => (
            <th key={id} className={cx(thClass, "text-right")}>
              Δ {labels[id]}
            </th>
          ))}
        </tr>
      </thead>
      <tbody>
        {rows.map((row) => {
          const base = row.cells[baselineId];
          return (
            <tr key={row.buyer_id}>
              <th scope="row" className={cx(tdClass, "font-medium")}>
                {row.buyer_name}
              </th>
              <td className={cx(tdClass, numClass)}>{base?.status === "absent" || base?.status === "added" ? "—" : fmtKg(base?.sold_kg)}</td>
              {runIds.map((id) => {
                const cell = row.cells[id];
                return (
                  <td
                    key={id}
                    className={cx(tdClass, numClass)}
                    style={heatStyle(cell?.delta_kg, maxAbs)}
                    title={cell ? `${fmtKg(cell.sold_kg)} vendus` : undefined}
                  >
                    {cell?.status === "added" ? (
                      <Badge tone="success">ajouté · {fmtKg(cell.sold_kg)}</Badge>
                    ) : cell?.status === "removed" ? (
                      <Badge tone="danger">retiré</Badge>
                    ) : cell?.status === "absent" || !cell ? (
                      <span className="text-slate-600">—</span>
                    ) : (
                      fmtSigned(cell.delta_kg, " kg")
                    )}
                  </td>
                );
              })}
            </tr>
          );
        })}
      </tbody>
    </Table>
  );
}

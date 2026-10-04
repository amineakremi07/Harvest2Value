"use client";

import { useState, type CSSProperties } from "react";
import { cx, numClass, Table, tdClass, thClass } from "@/components/ui/primitives";
import { blend, readableText } from "@/lib/color";
import { fmtKg, fmtNum } from "@/lib/format";
import type { Theme } from "@/lib/theme/theme";
import { useTheme } from "@/lib/theme/useTheme";
import type { AllocationRow, BuyerSummary } from "@/lib/api/types";
import { nameOf, type NameIndex } from "./names";

export interface MatrixCell {
  kg: number;
  revenue: number;
  sources: { lot: string; facility: string | null; kg: number }[];
}

export interface Matrix {
  rows: { buyerId: string; name: string; total: number }[];
  days: number[];
  cells: Record<string, Record<number, MatrixCell>>;
  dayTotals: Record<number, number>;
  max: number;
  total: number;
}

/** Buyer x delivery-day matrix of sold kg, built from the solver allocation rows. */
export function buildMatrix(allocations: AllocationRow[], buyers: BuyerSummary[]): Matrix {
  const cells: Matrix["cells"] = {};
  const dayTotals: Record<number, number> = {};
  const totals = new Map<string, number>();
  for (const a of allocations) {
    const byDay = (cells[a.buyer_id] ??= {});
    const cell = (byDay[a.day] ??= { kg: 0, revenue: 0, sources: [] });
    cell.kg += a.kg;
    cell.revenue += a.revenue;
    cell.sources.push({ lot: a.lot_id, facility: a.facility_id, kg: a.kg });
    dayTotals[a.day] = (dayTotals[a.day] ?? 0) + a.kg;
    totals.set(a.buyer_id, (totals.get(a.buyer_id) ?? 0) + a.kg);
  }
  const names = new Map(buyers.map((b) => [b.buyer_id, b.buyer_name]));
  const ids = [...new Set([...buyers.map((b) => b.buyer_id), ...totals.keys()])];
  const rows = ids
    .map((id) => ({ buyerId: id, name: names.get(id) ?? id, total: totals.get(id) ?? 0 }))
    .sort((a, b) => b.total - a.total);
  const days = Object.keys(dayTotals).map(Number).sort((a, b) => a - b);
  const max = Math.max(0, ...Object.values(cells).flatMap((byDay) => Object.values(byDay).map((c) => c.kg)));
  const total = [...totals.values()].reduce((s, v) => s + v, 0);
  return { rows, days, cells, dayTotals, max, total };
}

const EMERALD: [number, number, number] = [16, 185, 129];
const SURFACE = { dark: [19, 27, 46], light: [255, 255, 255] } as const;

/** Heat color, and the text color that keeps WCAG AA contrast on it in the current theme. */
export function cellStyle(kg: number, max: number, theme: Theme = "dark"): CSSProperties | undefined {
  if (kg <= 0 || max <= 0) return undefined;
  const alpha = Math.round((0.12 + 0.6 * (kg / max)) * 100) / 100;
  const background = blend(EMERALD, alpha, [...SURFACE[theme]]);
  return { backgroundColor: `rgb(${background.join(", ")})`, color: readableText(background) };
}

export function AllocationMatrix({
  allocations,
  buyers,
  names = {},
}: {
  allocations: AllocationRow[];
  buyers: BuyerSummary[];
  names?: NameIndex;
}) {
  const { theme } = useTheme();
  const matrix = buildMatrix(allocations, buyers);
  const [selected, setSelected] = useState<{ buyer: string; day: number } | null>(null);
  const detail = selected ? matrix.cells[selected.buyer]?.[selected.day] : undefined;

  if (matrix.days.length === 0) {
    return <p className="py-6 text-sm text-slate-400">Aucune vente dans ce plan.</p>;
  }

  return (
    <div className="space-y-4">
      <Table label="Matrice d'allocation acheteur × jour">
        <thead>
          <tr>
            <th className={cx(thClass, "sticky left-0 bg-card-surface")}>Acheteur</th>
            {matrix.days.map((d) => (
              <th key={d} className={cx(thClass, "text-right")}>
                J{d}
              </th>
            ))}
            <th className={cx(thClass, "text-right")}>Total</th>
          </tr>
        </thead>
        <tbody>
          {matrix.rows.map((row) => (
            <tr key={row.buyerId}>
              <th scope="row" className={cx(tdClass, "sticky left-0 bg-card-surface font-medium")}>
                {row.name}
              </th>
              {matrix.days.map((d) => {
                const cell = matrix.cells[row.buyerId]?.[d];
                const isSelected = selected?.buyer === row.buyerId && selected.day === d;
                return (
                  <td key={d} className={cx(tdClass, numClass, "p-0")} style={cellStyle(cell?.kg ?? 0, matrix.max, theme)}>
                    {cell ? (
                      <button
                        type="button"
                        className={cx("w-full px-3 py-2 text-right", isSelected && "outline outline-2 outline-cyan-accent")}
                        aria-label={`${row.name}, jour ${d} : ${fmtKg(cell.kg)}`}
                        onClick={() => setSelected(isSelected ? null : { buyer: row.buyerId, day: d })}
                      >
                        {fmtNum(Math.round(cell.kg))}
                      </button>
                    ) : (
                      <span className="block px-3 py-2 text-slate-700">·</span>
                    )}
                  </td>
                );
              })}
              <td className={cx(tdClass, numClass, "font-semibold")}>{fmtKg(row.total)}</td>
            </tr>
          ))}
        </tbody>
        <tfoot>
          <tr>
            <th scope="row" className={cx(thClass, "sticky left-0 bg-card-surface")}>
              Total / jour
            </th>
            {matrix.days.map((d) => (
              <td key={d} className={cx(tdClass, numClass, "text-slate-400")}>
                {fmtNum(Math.round(matrix.dayTotals[d]))}
              </td>
            ))}
            <td className={cx(tdClass, numClass, "font-bold")}>{fmtKg(matrix.total)}</td>
          </tr>
        </tfoot>
      </Table>

      {selected && detail && (
        <div className="rounded-lg border border-card-border bg-navy-deep p-3 text-sm" aria-live="polite">
          <p className="mb-2 font-semibold text-white">
            {nameOf(names.buyers, selected.buyer)} — jour {selected.day} : {fmtKg(detail.kg)}
          </p>
          <ul className="space-y-1 text-slate-300">
            {detail.sources.map((s, i) => (
              <li key={i}>
                {fmtKg(s.kg)} du lot {nameOf(names.lots, s.lot)} —{" "}
                {s.facility ? `depuis ${nameOf(names.facilities, s.facility)}` : "vente directe"}
              </li>
            ))}
          </ul>
        </div>
      )}
    </div>
  );
}

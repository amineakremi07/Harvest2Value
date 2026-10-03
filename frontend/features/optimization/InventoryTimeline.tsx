"use client";

import { StackedTimeline, type TimelinePoint, type TimelineSeries } from "@/components/charts/StackedTimeline";
import { CHART } from "@/components/charts/theme";
import type { OptimizationResult } from "@/lib/api/types";
import { nameOf, type NameIndex } from "./names";

/** Stock at the end of each day per facility (stacked), with sales and losses of the day. */
export function inventorySeries(result: OptimizationResult, names: NameIndex = {}): { data: TimelinePoint[]; series: TimelineSeries[] } {
  const facilities = [...new Set(result.inventory.map((r) => r.facility_id))].sort();
  const points = new Map<number, TimelinePoint>();
  const point = (day: number): TimelinePoint => {
    let p = points.get(day);
    if (!p) {
      p = { day, sold: 0, lost: 0 } as TimelinePoint;
      for (const f of facilities) p[`stock:${f}`] = 0;
      points.set(day, p);
    }
    return p;
  };
  for (let day = 0; day < result.horizon_days; day++) point(day);
  for (const r of result.inventory) point(r.day)[`stock:${r.facility_id}`] += r.kg_end;
  for (const a of result.allocations) point(a.day).sold += a.kg;
  for (const w of result.waste) point(w.day).lost += w.kg;

  const series: TimelineSeries[] = [
    ...facilities.map((f) => ({ key: `stock:${f}`, label: `Stock ${nameOf(names.facilities, f)}`, kind: "area" as const })),
    { key: "sold", label: "Vendu", kind: "bar", color: "#38BDF8" },
    { key: "lost", label: "Pertes", kind: "line", color: CHART.negative },
  ];
  return { data: [...points.values()].sort((a, b) => a.day - b.day), series };
}

export function InventoryTimeline({ result, names }: { result: OptimizationResult; names?: NameIndex }) {
  const { data, series } = inventorySeries(result, names);
  return <StackedTimeline data={data} series={series} ariaLabel="Évolution du stock, des ventes et des pertes par jour" />;
}

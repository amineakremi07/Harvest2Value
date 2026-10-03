"use client";

import { Area, Bar, CartesianGrid, ComposedChart, Legend, Line, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import { CHART, seriesColor, tooltipStyle } from "./theme";

export interface TimelineSeries {
  key: string;
  label: string;
  kind: "area" | "bar" | "line";
  color?: string;
}

export type TimelinePoint = { day: number } & Record<string, number>;

/** Day-indexed chart: stacked areas (stock), bars and lines share one kg axis. */
export function StackedTimeline({
  data,
  series,
  height = 300,
  unit = "kg",
  ariaLabel,
}: {
  data: TimelinePoint[];
  series: TimelineSeries[];
  height?: number;
  unit?: string;
  ariaLabel: string;
}) {
  if (data.length === 0) return <p className="py-10 text-center text-sm text-slate-500">Aucune donnée.</p>;
  return (
    <div role="img" aria-label={ariaLabel} style={{ height }}>
      <ResponsiveContainer width="100%" height="100%">
        <ComposedChart data={data} margin={{ top: 8, right: 12, bottom: 0, left: 0 }}>
          <CartesianGrid stroke={CHART.grid} vertical={false} />
          <XAxis dataKey="day" stroke={CHART.axis} tick={{ fill: CHART.text, fontSize: 11 }} tickFormatter={(d: number) => `J${d}`} />
          <YAxis stroke={CHART.axis} tick={{ fill: CHART.text, fontSize: 11 }} width={64} tickFormatter={(v: number) => v.toLocaleString("fr-FR")} />
          <Tooltip
            {...tooltipStyle}
            labelFormatter={(d) => `Jour ${String(d)}`}
            formatter={(v) => (typeof v === "number" ? `${Math.round(v).toLocaleString("fr-FR")} ${unit}` : String(v))}
          />
          <Legend wrapperStyle={{ fontSize: 12, color: CHART.text }} />
          {series.map((s, i) => {
            const color = s.color ?? seriesColor(i);
            if (s.kind === "area") {
              return <Area key={s.key} type="stepAfter" dataKey={s.key} name={s.label} stackId="stock" stroke={color} fill={color} fillOpacity={0.35} />;
            }
            if (s.kind === "bar") return <Bar key={s.key} dataKey={s.key} name={s.label} fill={color} barSize={10} />;
            return <Line key={s.key} type="monotone" dataKey={s.key} name={s.label} stroke={color} dot={false} strokeWidth={2} />;
          })}
        </ComposedChart>
      </ResponsiveContainer>
    </div>
  );
}

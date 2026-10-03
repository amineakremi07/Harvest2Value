"use client";

import { Bar, BarChart, CartesianGrid, Cell, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import { CHART, tooltipStyle } from "./theme";

export interface WaterfallStep {
  label: string;
  /** Totals are absolute levels; deltas move the running level up or down. */
  kind: "total" | "delta";
  value: number;
}

export interface WaterfallBar {
  label: string;
  base: number;
  size: number;
  value: number;
  kind: "total" | "up" | "down";
}

/** Floating bars: each delta starts where the previous level ended. */
export function waterfallBars(steps: WaterfallStep[]): WaterfallBar[] {
  let level = 0;
  return steps.map((s) => {
    if (s.kind === "total") {
      level = s.value;
      return { label: s.label, base: Math.min(0, s.value), size: Math.abs(s.value), value: s.value, kind: "total" };
    }
    const start = level;
    level += s.value;
    return { label: s.label, base: Math.min(start, level), size: Math.abs(s.value), value: s.value, kind: s.value >= 0 ? "up" : "down" };
  });
}

const FILL = { total: CHART.total, up: CHART.positive, down: CHART.negative } as const;

export function WaterfallChart({
  steps,
  height = 300,
  formatValue = (v: number) => Math.round(v).toLocaleString("fr-FR"),
  ariaLabel,
}: {
  steps: WaterfallStep[];
  height?: number;
  formatValue?: (value: number) => string;
  ariaLabel: string;
}) {
  const bars = waterfallBars(steps);
  return (
    <div role="img" aria-label={ariaLabel} style={{ height }}>
      <ResponsiveContainer width="100%" height="100%">
        <BarChart data={bars} margin={{ top: 8, right: 12, bottom: 0, left: 0 }}>
          <CartesianGrid stroke={CHART.grid} vertical={false} />
          <XAxis dataKey="label" stroke={CHART.axis} tick={{ fill: CHART.text, fontSize: 11 }} interval={0} />
          <YAxis stroke={CHART.axis} tick={{ fill: CHART.text, fontSize: 11 }} width={72} tickFormatter={(v: number) => v.toLocaleString("fr-FR")} />
          <Tooltip
            {...tooltipStyle}
            cursor={{ fill: "rgba(255,255,255,0.04)" }}
            formatter={(_value, name, item) => {
              const bar = (item as { payload?: WaterfallBar }).payload;
              if (name !== "size" || !bar) return null;
              const sign = bar.kind === "total" ? "" : bar.value >= 0 ? "+" : "−";
              return [`${sign}${formatValue(Math.abs(bar.value))}`, bar.label];
            }}
          />
          <Bar dataKey="base" stackId="w" fill="transparent" isAnimationActive={false} />
          <Bar dataKey="size" stackId="w" isAnimationActive={false}>
            {bars.map((b) => (
              <Cell key={b.label} fill={FILL[b.kind]} />
            ))}
          </Bar>
        </BarChart>
      </ResponsiveContainer>
    </div>
  );
}

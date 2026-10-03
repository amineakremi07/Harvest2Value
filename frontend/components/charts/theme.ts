// Shared chart palette for the dark analytics theme (design.md).
export const CHART = {
  grid: "#1E293B",
  axis: "#64748B",
  text: "#94A3B8",
  tooltipBg: "#0B101D",
  tooltipBorder: "#1E293B",
  positive: "#10B981",
  negative: "#F43F5E",
  neutral: "#64748B",
  total: "#06B6D4",
} as const;

/** Categorical series colors, distinguishable on the dark surface. */
export const SERIES = ["#10B981", "#06B6D4", "#F59E0B", "#A78BFA", "#F472B6", "#84CC16", "#38BDF8", "#FB923C"] as const;

export function seriesColor(index: number): string {
  return SERIES[index % SERIES.length];
}

export const tooltipStyle = {
  contentStyle: { background: CHART.tooltipBg, border: `1px solid ${CHART.tooltipBorder}`, borderRadius: 8, fontSize: 12 },
  labelStyle: { color: "#E2E8F0" },
  itemStyle: { color: "#CBD5E1" },
} as const;

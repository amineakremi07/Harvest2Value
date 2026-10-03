import { render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";
import { waterfallBars } from "@/components/charts/WaterfallChart";
import type { RunSummary } from "@/lib/api/types";
import { OLIVES_COMPARISON, OLIVES_RUN } from "@/test/fixtures";
import { BuyerDeltaHeatmap, heatStyle } from "./BuyerDeltaHeatmap";
import { CompareKpiTable, deltaQuality } from "./CompareKpiTable";
import { NotableChanges } from "./NotableChanges";
import { profitBridge } from "./ProfitWaterfall";
import { defaultBaseline, RunPicker } from "./RunPicker";
import { runLabels } from "./runLabels";

const C = OLIVES_COMPARISON;
const BASE = C.baseline_run_id;
const [SCEN] = C.run_ids;
const labels = runLabels(C);

describe("<CompareKpiTable>", () => {
  it("shows baseline and compared values with colored deltas", () => {
    render(<CompareKpiTable rows={C.kpi_table} baselineId={BASE} runIds={C.run_ids} labels={labels} />);
    const profit = screen.getByRole("row", { name: /Realized profit/ });
    expect(within(profit).getByText(/−3\s?140,14/)).toHaveClass("text-rose-300"); // profit fell: bad
    expect(within(profit).getByText("meilleur")).toBeInTheDocument(); // baseline wins
    expect(screen.getAllByRole("row")).toHaveLength(C.kpi_table.length + 1);
  });

  it("deltaQuality follows the KPI direction", () => {
    expect(deltaQuality({ abs: -5, pct: -1 }, "lower")).toBe(true);
    expect(deltaQuality({ abs: -5, pct: -1 }, "higher")).toBe(false);
    expect(deltaQuality({ abs: 3, pct: 1 }, "neutral")).toBeNull();
    expect(deltaQuality({ abs: 0, pct: 0 }, "higher")).toBeNull();
  });
});

describe("ProfitWaterfall", () => {
  it("bridges the baseline profit to the scenario profit through revenue and cost deltas", () => {
    const steps = profitBridge(C.kpi_table, BASE, SCEN);
    const value = (kpi: string, id: string) => C.kpi_table.find((r) => r.kpi === kpi)?.values[id] ?? 0;
    expect(steps[0]).toEqual({ label: "Profit référence", kind: "total", value: value("realized_profit", BASE) });
    expect(steps.at(-1)).toEqual({ label: "Profit scénario", kind: "total", value: value("realized_profit", SCEN) });
    const bars = waterfallBars(steps);
    const deltas = steps.filter((s) => s.kind === "delta").reduce((sum, s) => sum + s.value, 0);
    expect(steps[0].value + deltas).toBeCloseTo(value("realized_profit", SCEN), 1);
    // The revenue drop (price -10 %) is a falling step.
    expect(bars[1].kind).toBe("down");
  });

  it("waterfallBars floats each delta from the running level", () => {
    const bars = waterfallBars([
      { label: "start", kind: "total", value: 100 },
      { label: "up", kind: "delta", value: 30 },
      { label: "down", kind: "delta", value: -50 },
      { label: "end", kind: "total", value: 80 },
    ]);
    expect(bars.map((b) => [b.base, b.size, b.kind])).toEqual([
      [0, 100, "total"],
      [100, 30, "up"],
      [80, 50, "down"],
      [0, 80, "total"],
    ]);
  });
});

describe("<BuyerDeltaHeatmap>", () => {
  it("renders one row per buyer with the delta per compared run", () => {
    render(<BuyerDeltaHeatmap rows={C.buyer_matrix} baselineId={BASE} runIds={C.run_ids} labels={labels} />);
    expect(screen.getAllByRole("row")).toHaveLength(C.buyer_matrix.length + 1);
    expect(screen.getByText("Huilerie Sfax Export")).toBeInTheDocument();
  });

  it("colors gains green and losses red, no color for no change", () => {
    expect(heatStyle(100, 100)?.backgroundColor).toMatch(/16, 185, 129/);
    expect(heatStyle(-100, 100)?.backgroundColor).toMatch(/244, 63, 94/);
    expect(heatStyle(0, 100)).toBeUndefined();
  });
});

describe("<NotableChanges>", () => {
  it("lists the backend's notable changes, largest first", () => {
    render(<NotableChanges changes={C.notable_changes} labels={labels} />);
    expect(screen.getByText(/Realized profit falls/)).toBeInTheDocument();
  });
});

const summary = (id: string, patch: Partial<RunSummary>): RunSummary => ({ ...OLIVES_RUN, id, label: id, ...patch });

describe("RunPicker", () => {
  const runs = [
    summary("scen", { scenario_id: "s1", created_at: "2026-10-02T10:00:00Z" }),
    summary("old-base", { scenario_id: null, created_at: "2026-10-01T10:00:00Z" }),
    summary("new-base", { scenario_id: null, created_at: "2026-10-02T09:00:00Z" }),
    summary("other", { scenario_id: null, dataset_id: "other-ds", created_at: "2026-10-03T09:00:00Z" }),
  ];

  it("defaults the baseline to the latest non-scenario run of the same dataset", () => {
    expect(defaultBaseline(runs, ["scen"])).toBe("new-base");
  });

  it("limits the selection to three compared runs", async () => {
    const onChange = vi.fn();
    render(<RunPicker runs={runs} baselineId="old-base" runIds={["scen", "new-base", "other"]} onChange={onChange} />);
    const boxes = screen.getAllByRole("checkbox");
    expect(boxes.filter((b) => (b as HTMLInputElement).checked)).toHaveLength(3);
    await userEvent.click(screen.getByRole("checkbox", { name: /scen/ }));
    expect(onChange).toHaveBeenCalledWith("old-base", ["new-base", "other"]);
  });
});

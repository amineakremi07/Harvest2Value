import { render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";
import { toRechartsSankey } from "@/components/charts/SankeyChart";
import type { RunDetail } from "@/lib/api/types";
import { OLIVES_PAYLOAD, OLIVES_RESULT, OLIVES_RUN } from "@/test/fixtures";
import { AllocationMatrix, buildMatrix } from "./AllocationMatrix";
import { inventorySeries } from "./InventoryTimeline";
import { nameIndex } from "./names";
import { RunKpis } from "./RunKpis";
import { RunStatusBanner } from "./RunStatusBanner";
import { supplyFlow } from "./supplyFlow";
import { TripsTable } from "./TripsTable";

const names = nameIndex(OLIVES_PAYLOAD);
const sum = (values: number[]) => values.reduce((s, v) => s + v, 0);

describe("supplyFlow (Sankey harvest -> storage -> buyers -> losses)", () => {
  const graph = supplyFlow(OLIVES_RESULT, names);

  it("conserves the harvest: sold + lost + ending stock leave the harvest node", () => {
    const out = sum(graph.links.filter((l) => l.source === "harvest").map((l) => l.value));
    const { harvest_kg, sold_kg, lost_kg, ending_inventory_kg } = OLIVES_RESULT.kpis;
    expect(out).toBeCloseTo(sold_kg + lost_kg + ending_inventory_kg, 0);
    expect(out).toBeCloseTo(harvest_kg, 0);
  });

  it("routes sales through the direct node or the facility they left from", () => {
    const toBuyers = sum(graph.links.filter((l) => l.target.startsWith("b:")).map((l) => l.value));
    expect(toBuyers).toBeCloseTo(OLIVES_RESULT.kpis.sold_kg, 1);
    expect(graph.nodes.find((n) => n.id === "f:hangar_sfax")?.label).toBe("Hangar ambiant Sfax");
    expect(graph.nodes.some((n) => n.id === "direct")).toBe(true);
    expect(graph.nodes.find((n) => n.id === "loss")?.kind).toBe("loss");
  });

  it("converts to index-based recharts data without dangling links", () => {
    const data = toRechartsSankey(graph);
    for (const l of data.links) {
      expect(data.nodes[l.source]).toBeDefined();
      expect(data.nodes[l.target]).toBeDefined();
    }
  });
});

describe("<AllocationMatrix>", () => {
  it("aggregates kg per buyer and delivery day", () => {
    const m = buildMatrix(OLIVES_RESULT.allocations, OLIVES_RESULT.buyers);
    expect(m.total).toBeCloseTo(OLIVES_RESULT.kpis.sold_kg, 1);
    expect(m.days).toEqual([...new Set(OLIVES_RESULT.allocations.map((a) => a.day))].sort((a, b) => a - b));
  });

  it("renders a buyer x day table and details a cell's sources on click", async () => {
    render(<AllocationMatrix allocations={OLIVES_RESULT.allocations} buyers={OLIVES_RESULT.buyers} names={names} />);
    const table = screen.getByRole("table", { name: /allocation/i });
    expect(within(table).getByText("Huilerie Sfax Export")).toBeInTheDocument();
    const cell = screen.getByRole("button", { name: /Huilerie Sfax Export, jour 0/ });
    await userEvent.click(cell);
    expect(screen.getByText(/vente directe/)).toBeInTheDocument();
  });

  it("says so when nothing is sold", () => {
    render(<AllocationMatrix allocations={[]} buyers={[]} />);
    expect(screen.getByText(/aucune vente/i)).toBeInTheDocument();
  });
});

describe("inventorySeries", () => {
  it("has one point per horizon day and a stacked stock series per facility", () => {
    const { data, series } = inventorySeries(OLIVES_RESULT, names);
    expect(data).toHaveLength(OLIVES_RESULT.horizon_days);
    expect(series.filter((s) => s.kind === "area").map((s) => s.label)).toContain("Stock Hangar ambiant Sfax");
    expect(sum(data.map((p) => p.sold))).toBeCloseTo(OLIVES_RESULT.kpis.sold_kg, 1);
    expect(sum(data.map((p) => p.lost))).toBeCloseTo(OLIVES_RESULT.kpis.lost_kg, 1);
  });
});

describe("<TripsTable>", () => {
  it("lists trips with vehicle names and totals", () => {
    render(<TripsTable trips={OLIVES_RESULT.trips} names={names} />);
    const rows = screen.getAllByRole("row");
    expect(rows).toHaveLength(OLIVES_RESULT.trips.length + 2); // header + footer
    expect(screen.getAllByText("Camion 3 t").length).toBe(OLIVES_RESULT.trips.length);
    const footer = rows[rows.length - 1];
    expect(within(footer).getByText(String(OLIVES_RESULT.kpis.trips))).toBeInTheDocument();
  });
});

describe("<RunKpis>", () => {
  it("shows realized profit and economic value separately", () => {
    render(<RunKpis kpis={OLIVES_RESULT.kpis} currency="TND" />);
    expect(screen.getByText("Profit réalisé")).toBeInTheDocument();
    expect(screen.getByText("Valeur économique")).toBeInTheDocument();
    expect(screen.getByText(/pas un profit/)).toBeInTheDocument();
  });
});

describe("<RunStatusBanner>", () => {
  const run = (patch: Partial<RunDetail>): RunDetail => ({ ...OLIVES_RUN, ...patch });

  it("shows progress and a cancel button while queued", async () => {
    const onCancel = vi.fn();
    render(<RunStatusBanner run={run({ status: "queued" })} polling onCancel={onCancel} />);
    expect(screen.getByText("En file")).toBeInTheDocument();
    expect(screen.getByText(/chaque seconde/)).toBeInTheDocument();
    await userEvent.click(screen.getByRole("button", { name: /annuler/i }));
    expect(onCancel).toHaveBeenCalled();
  });

  it("shows the solve time when succeeded, without cancel", () => {
    render(<RunStatusBanner run={run({ status: "succeeded" })} polling={false} onCancel={vi.fn()} />);
    expect(screen.getByText("Terminé")).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: /annuler/i })).toBeNull();
  });

  it("explains an infeasible run with its conflicts", () => {
    render(
      <RunStatusBanner
        run={run({
          status: "infeasible",
          diagnostics: {
            method: "elastic",
            conflicts: [{ key: "k", family: "contract_min", label: "Contrat minimum Sousse", relaxation_needed: 500, unit: "kg" }],
            suggestions: ["Réduire le contrat"],
          },
        })}
        polling={false}
      />,
    );
    expect(screen.getByText("Infaisable")).toBeInTheDocument();
    expect(screen.getByText(/Contrat minimum Sousse/)).toBeInTheDocument();
    expect(screen.getByText("Réduire le contrat")).toBeInTheDocument();
  });
});

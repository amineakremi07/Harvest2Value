import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { useState } from "react";
import { describe, expect, it } from "vitest";
import { OLIVES_NETWORK, OLIVES_NETWORK_DAY0, OLIVES_RESULT } from "@/test/fixtures";
import { COLUMN, layoutNetwork } from "./layout";
import { PeriodScrubber } from "./PeriodScrubber";

describe("layoutNetwork", () => {
  it("keeps every API edge and places nodes in producer -> lot -> storage -> vehicle -> buyer columns", () => {
    const { nodes, edges } = layoutNetwork(OLIVES_NETWORK);
    expect(edges).toHaveLength(OLIVES_NETWORK.edges.length);
    for (const n of nodes) expect(n.position.x).toBe(COLUMN[n.data.kind] * 260);
    const buyers = OLIVES_NETWORK.nodes.filter((n) => n.kind === "buyer").map((n) => n.id);
    expect(nodes.filter((n) => n.data.kind === "buyer").map((n) => n.id)).toEqual(buyers);
  });

  it("labels flows with the API quantities", () => {
    const { edges } = layoutNetwork(OLIVES_NETWORK);
    const sale = OLIVES_NETWORK.edges.find((e) => e.kind === "sale")!;
    const edge = edges.find((e) => e.source === sale.source && e.target === sale.target)!;
    expect(edge.label).toBe(`${Math.round(sale.kg).toLocaleString("fr-FR")} kg`);
    expect(edge.animated).toBe(true);
  });

  it("drops idle lots and storage on a single day", () => {
    const { nodes } = layoutNetwork(OLIVES_NETWORK_DAY0);
    const lots = nodes.filter((n) => n.data.kind === "lot");
    expect(lots.every((l) => OLIVES_NETWORK_DAY0.edges.some((e) => e.source === l.id || e.target === l.id))).toBe(true);
    expect(nodes.some((n) => n.data.kind === "producer")).toBe(true);
  });
});

function Harness() {
  const [day, setDay] = useState<number | null>(null);
  return (
    <>
      <PeriodScrubber horizon={OLIVES_RESULT.horizon_days} day={day} onChange={setDay} />
      <span data-testid="day">{day === null ? "all" : day}</span>
    </>
  );
}

describe("PeriodScrubber", () => {
  it("switches between the whole period and single days", async () => {
    render(<Harness />);
    expect(screen.getByTestId("day")).toHaveTextContent("all");
    expect(screen.getByText(`J0 – J${OLIVES_RESULT.horizon_days - 1}`)).toBeInTheDocument();
    await userEvent.click(screen.getByRole("checkbox", { name: "Toute la période" }));
    expect(screen.getByTestId("day")).toHaveTextContent("0");
    await userEvent.click(screen.getByRole("button", { name: "Jour suivant" }));
    await userEvent.click(screen.getByRole("button", { name: "Jour suivant" }));
    expect(screen.getByTestId("day")).toHaveTextContent("2");
    await userEvent.click(screen.getByRole("button", { name: "Jour précédent" }));
    expect(screen.getByTestId("day")).toHaveTextContent("1");
    await userEvent.click(screen.getByRole("checkbox", { name: "Toute la période" }));
    expect(screen.getByTestId("day")).toHaveTextContent("all");
  });
});

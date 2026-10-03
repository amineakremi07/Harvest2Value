import { render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";
import type { Bottleneck, DecisionCard as DecisionCardData } from "@/lib/api/types";
import { OLIVES_EXPLANATION, OLIVES_MARGINAL, OLIVES_RESULT, WHEAT_INSIGHTS } from "@/test/fixtures";
import { InsightCard } from "@/features/insights/InsightCard";
import { BindingConstraintsTable } from "./BindingConstraintsTable";
import { BottleneckList } from "./BottleneckList";
import { buyerWhy, DecisionCard } from "./DecisionCard";
import { LIMITING_LABEL } from "./labels";
import { MarginalValueChart, probeBars } from "./MarginalValueChart";
import { MarginalValues, sortMarginalValues } from "./MarginalValues";
import { asChangeInput, compareHref } from "./testChange";

const E = OLIVES_EXPLANATION;
const buyerCards = E.decisions.filter((d) => d.kind === "buyer");

describe("DecisionCard — every buyer gets 'why, and why not more'", () => {
  it("the API returns one buyer card per buyer of the plan", () => {
    expect(buyerCards.map((c) => c.entity_id).sort()).toEqual(OLIVES_RESULT.buyers.map((b) => b.buyer_id).sort());
  });

  it.each(buyerCards.map((c) => [c.name, c] as const))("%s: why + why-not-more sections with the API's limiting factor", (_name, card) => {
    render(<DecisionCard card={card} currency="TND" />);
    const article = screen.getByRole("article", { name: `Décision : ${card.name}` });
    const why = within(article).getByRole("region", { name: "Pourquoi" });
    expect(why.textContent).not.toBe("");
    const whyNot = within(article).getByRole("region", { name: /Pourquoi pas (plus|servi)/ });
    expect(card.limiting_factor).not.toBeNull();
    expect(whyNot).toHaveTextContent(card.limiting_factor!.message);
    expect(whyNot).toHaveTextContent(LIMITING_LABEL[card.limiting_factor!.code]);
    expect(within(article).getByText(card.decision)).toBeInTheDocument();
  });

  it("uses the net price and market rank from the API metrics", () => {
    const card = buyerCards.find((c) => c.entity_id === "buyer_tn_01") as DecisionCardData;
    const lines = buyerWhy(card.metrics, "TND");
    expect(lines[0]).toContain("2,34 TND/kg");
    expect(lines[1]).toContain("Rang n°2");
  });

  it("an unserved buyer says why it was not served", () => {
    const card = buyerCards.find((c) => c.metrics.sold_kg === 0) as DecisionCardData;
    render(<DecisionCard card={card} />);
    expect(screen.getByRole("region", { name: "Pourquoi pas servi" })).toBeInTheDocument();
  });
});

describe("MarginalValues — perturbation first, dual as a local indicator", () => {
  const card = buyerCards.find((c) => (c.marginal_values ?? []).some((v) => v.kind === "dual")) as DecisionCardData;

  it("orders probes before duals", () => {
    const { probes, duals } = sortMarginalValues(card.marginal_values ?? []);
    expect(probes.length).toBeGreaterThan(0);
    expect(duals.length).toBeGreaterThan(0);
  });

  it("shows the probe as the headline value and the dual with a tooltip on its limits", async () => {
    const { container } = render(<MarginalValues values={card.marginal_values ?? []} currency="TND" />);
    const probe = container.querySelector('[data-kind="probe"]');
    const dual = container.querySelector('[data-kind="dual"]');
    expect(probe).toHaveClass("text-lg");
    expect(dual).not.toHaveClass("text-lg");
    expect(screen.getByText("Effet mesuré")).toBeInTheDocument();
    expect(screen.getByText("Indicateur local")).toBeInTheDocument();
    await userEvent.hover(screen.getByRole("button", { name: "Limites de l'indicateur local" }));
    expect(screen.getByRole("tooltip")).toHaveTextContent(/décisions entières/);
  });

  it("flags a probe within the MIP-gap noise band as not significant", () => {
    render(<MarginalValues values={[{ kind: "probe", label: "x", delta_objective: 3, reliable: false, change: null }]} />);
    expect(screen.getByText("non significatif")).toBeInTheDocument();
  });
});

describe("MarginalValueChart", () => {
  it("charts every measured probe, largest effect first", () => {
    const bars = probeBars(OLIVES_MARGINAL);
    expect(bars.length).toBe((OLIVES_MARGINAL.probes ?? []).filter((p) => p.delta_objective != null).length);
    expect(Math.abs(bars[0].value)).toBeGreaterThanOrEqual(Math.abs(bars[bars.length - 1].value));
    render(<MarginalValueChart report={OLIVES_MARGINAL} />);
    expect(screen.getByRole("img", { name: /Effet mesuré/ })).toBeInTheDocument();
  });
});

describe("BottleneckList", () => {
  it("ranks bottlenecks, shows the suggestion and tests it", async () => {
    const onTest = vi.fn();
    render(<BottleneckList bottlenecks={E.bottlenecks} onTest={onTest} measured={E.sensitivity_computed} />);
    const items = within(screen.getByRole("list", { name: "Goulots d'étranglement" })).getAllByRole("listitem");
    expect(items).toHaveLength(E.bottlenecks.length);
    expect(items[0]).toHaveTextContent(E.bottlenecks.find((b) => b.rank === 1)!.label);
    await userEvent.click(within(items[0]).getByRole("button", { name: "Tester" }));
    expect(onTest).toHaveBeenCalledWith(expect.objectContaining({ rank: 1 }));
  });

  it("shows the measured gain as the main value when the probe is significant", () => {
    const b: Bottleneck = { ...E.bottlenecks[0], probe_gain: 120.5, dual: 0.1 };
    render(<BottleneckList bottlenecks={[b]} measured />);
    expect(screen.getByText(/\+120,5 TND/)).toHaveClass("font-bold");
    expect(screen.getByText(/Indicateur local/)).toBeInTheDocument();
  });

  it("says 'no significant effect' rather than 'not measured' once probes ran", () => {
    render(<BottleneckList bottlenecks={[{ ...E.bottlenecks[0], probe_gain: null }]} measured />);
    expect(screen.getByText("pas d'effet significatif mesuré")).toBeInTheDocument();
  });
});

describe("BindingConstraintsTable", () => {
  it("lists binding constraints and filters by family", async () => {
    render(<BindingConstraintsTable constraints={E.binding} />);
    const table = screen.getByRole("table", { name: "Contraintes saturées" });
    expect(within(table).getAllByRole("row").length).toBe(Math.min(15, E.binding.length) + 1);
    const family = E.binding[0].family;
    await userEvent.selectOptions(screen.getByLabelText("Filtrer par famille"), family);
    const rows = within(table).getAllByRole("row").slice(1);
    expect(rows.length).toBe(Math.min(15, E.binding.filter((c) => c.family === family).length));
  });
});

describe("'Tester cette recommandation'", () => {
  it("the wheat insight carries a suggested change and shows the test button", async () => {
    const insight = WHEAT_INSIGHTS.find((i) => i.suggested_changes.length > 0)!;
    const onTry = vi.fn();
    render(<InsightCard insight={insight} onTry={onTry} />);
    await userEvent.click(screen.getByRole("button", { name: "Tester cette recommandation" }));
    expect(onTry).toHaveBeenCalled();
  });

  it("narrows suggested changes and links to the comparison", () => {
    expect(asChangeInput(E.bottlenecks[0].suggested_change)).toMatchObject({ op: "buyer_demand", target: "buyer_tn_01" });
    expect(asChangeInput({ foo: 1 })).toBeNull();
    expect(compareHref("a", "b")).toBe("/compare?baseline=a&runs=b");
  });
});

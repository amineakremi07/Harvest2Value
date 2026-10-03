import { render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, describe, expect, it, vi } from "vitest";
import { api } from "@/lib/api/endpoints";
import type { RunSummary } from "@/lib/api/types";
import { fmtKg, fmtMoney } from "@/lib/format";
import { OLIVES_BUYERS, OLIVES_CROPS, OLIVES_FINANCIAL, OLIVES_LOGISTICS, OLIVES_OPERATIONAL, OLIVES_RUN } from "@/test/fixtures";
import { AnalyticsCenter, headlines } from "./AnalyticsCenter";
import { BuyersPanel, CropPanel, FinancialPanel, financialSteps, LogisticsPanel, OperationalPanel } from "./sections";

afterEach(() => vi.restoreAllMocks());

/** Exact text of an element (the formatted values contain narrow no-break spaces). */
const exact = (text: string) => (_: string, el: Element | null) => el?.children.length === 0 && el.textContent === text;

describe("analytics panels show the API's values", () => {
  it("financial: profit, waterfall from revenue to profit, one row per buyer", () => {
    render(<FinancialPanel data={OLIVES_FINANCIAL} currency="TND" />);
    expect(screen.getAllByText(exact(fmtMoney(OLIVES_FINANCIAL.realized_profit, "TND"))).length).toBeGreaterThan(0);
    const rows = within(screen.getByRole("table", { name: "Revenus par acheteur" })).getAllByRole("row");
    expect(rows).toHaveLength(OLIVES_FINANCIAL.by_buyer.length + 1);
    const steps = financialSteps(OLIVES_FINANCIAL);
    expect(steps[0]).toMatchObject({ label: "Chiffre d'affaires", kind: "total", value: OLIVES_FINANCIAL.realized_revenue });
    expect(steps.at(-1)).toMatchObject({ label: "Profit réalisé", kind: "total", value: OLIVES_FINANCIAL.realized_profit });
    expect(steps.filter((s) => s.kind === "delta").every((s) => s.value <= 0)).toBe(true);
  });

  it("operational, buyers, logistics and crop panels", () => {
    const { unmount } = render(<OperationalPanel data={OLIVES_OPERATIONAL} />);
    expect(screen.getAllByText(exact(fmtKg(OLIVES_OPERATIONAL.sold_kg)))[0]).toBeInTheDocument();
    unmount();

    render(<BuyersPanel data={OLIVES_BUYERS} currency="TND" />);
    const table = screen.getByRole("table", { name: "Analyse des acheteurs" });
    for (const b of OLIVES_BUYERS.buyers) expect(within(table).getByText(b.buyer_name)).toBeInTheDocument();
    expect(within(table).getAllByRole("row")[1]).toHaveTextContent("n°1");

    render(<LogisticsPanel data={OLIVES_LOGISTICS} currency="TND" />);
    expect(screen.getByRole("table", { name: "Utilisation des véhicules" })).toBeInTheDocument();

    render(<CropPanel data={OLIVES_CROPS} currency="TND" />);
    expect(within(screen.getByRole("table", { name: "Devenir des lots" })).getAllByRole("row")).toHaveLength(OLIVES_CROPS.lots.length + 1);
  });

  it("headlines carry the compared values straight from the sections", () => {
    const h = headlines("financial", OLIVES_FINANCIAL);
    expect(h.find((x) => x.key === "realized_profit")?.value).toBe(OLIVES_FINANCIAL.realized_profit);
    expect(headlines("buyers", OLIVES_BUYERS)).toHaveLength(OLIVES_BUYERS.buyers.length);
  });
});

describe("<AnalyticsCenter>", () => {
  const other: RunSummary = { ...OLIVES_RUN, id: "run-b", label: "Prix -10 %" };
  const lower = { ...OLIVES_FINANCIAL, run_id: "run-b", realized_profit: OLIVES_FINANCIAL.realized_profit - 1000 };

  function mockApi() {
    vi.spyOn(api, "runs").mockResolvedValue({ items: [OLIVES_RUN, other], total: 2, page: 1, page_size: 100 });
    vi.spyOn(api, "financial").mockImplementation(async (id) => (id === "run-b" ? lower : OLIVES_FINANCIAL));
    vi.spyOn(api, "buyers").mockResolvedValue(OLIVES_BUYERS);
  }

  it("filters by run and switches sections", async () => {
    mockApi();
    render(<AnalyticsCenter />);
    expect((await screen.findAllByText(exact(fmtMoney(OLIVES_FINANCIAL.realized_profit, "TND")))).length).toBeGreaterThan(0);
    await userEvent.click(screen.getByRole("tab", { name: "Acheteurs" }));
    expect(await screen.findByRole("table", { name: "Analyse des acheteurs" })).toBeInTheDocument();
    expect(api.buyers).toHaveBeenCalledWith(OLIVES_RUN.id);
  });

  it("compared view: both runs side by side and the gap", async () => {
    mockApi();
    render(<AnalyticsCenter initialRun={OLIVES_RUN.id} initialCompare="run-b" />);
    const gaps = await screen.findByRole("table", { name: "Écarts entre les deux exécutions" });
    const profit = within(gaps).getByText("Profit réalisé").closest("tr") as HTMLElement;
    expect(profit).toHaveTextContent("−1 000");
    expect(screen.getByRole("region", { name: "Analyse : Prix -10 %" })).toBeInTheDocument();
  });
});

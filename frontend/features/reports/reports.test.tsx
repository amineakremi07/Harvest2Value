import { render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, describe, expect, it, vi } from "vitest";
import { api, downloads } from "@/lib/api/endpoints";
import { fmtMoney, fmtPct } from "@/lib/format";
import { OLIVES_REPORT, OLIVES_RUN } from "@/test/fixtures";
import { buildSpec, ReportBuilderForm } from "./ReportBuilderForm";
import { asSnapshot, cellText, ReportDocument, SECTION_LABEL } from "./ReportDocument";
import { ReportView } from "./ReportsPages";

afterEach(() => vi.restoreAllMocks());

const snapshot = asSnapshot(OLIVES_REPORT.snapshot);

describe("<ReportDocument> renders the frozen snapshot only", () => {
  it("every section of the snapshot, with its tables", () => {
    render(<ReportDocument snapshot={snapshot} hash={OLIVES_REPORT.snapshot_hash} />);
    for (const section of OLIVES_REPORT.sections) {
      expect(screen.getByRole("region", { name: SECTION_LABEL[section as keyof typeof SECTION_LABEL] })).toBeInTheDocument();
    }
    expect(screen.getByText(`Empreinte : ${OLIVES_REPORT.snapshot_hash}`)).toBeInTheDocument();
    const buyers = screen.getByRole("table", { name: "Acheteurs — Acheteurs" });
    expect(within(buyers).getAllByRole("row")).toHaveLength(4 + 1);
  });

  it("does not change when the live data changes: nothing is fetched", () => {
    const spies = [vi.spyOn(api, "runResult"), vi.spyOn(api, "financial"), vi.spyOn(api, "compare")];
    const { container } = render(<ReportDocument snapshot={snapshot} />);
    const before = container.innerHTML;
    render(<ReportDocument snapshot={structuredClone(snapshot)} />);
    expect(spies.every((s) => s.mock.calls.length === 0)).toBe(true);
    expect(container.innerHTML).toBe(before);
  });

  it("formats KPI rows by KPI and unit, deltas as percentages", () => {
    const profitRow = { kpi: "realized_profit", value: 29174.84 };
    expect(cellText(profitRow, "value", "TND")).toBe(fmtMoney(29174.84, "TND"));
    const compared = { kpi: "realized_profit", unit: "currency", "Prix -10 %": 26034.7, "Prix -10 % (Δ %)": -10.76 };
    expect(cellText(compared, "Prix -10 %", "TND")).toBe(fmtMoney(26034.7, "TND"));
    expect(cellText(compared, "Prix -10 % (Δ %)", "TND")).toBe(fmtPct(-10.76));
  });

  it("an unavailable narrative says so", () => {
    render(<ReportDocument snapshot={{ ...snapshot, narrative: { status: "unavailable", reason: "IA désactivée" } }} />);
    expect(screen.getByText(/Récit indisponible : IA désactivée/)).toBeInTheDocument();
  });
});

describe("report builder", () => {
  it("adds the comparison section when runs are compared, keeps the canonical order", () => {
    expect(buildSpec(" T ", "r1", ["r2"], ["buyers", "summary"], false)).toEqual({
      title: "T",
      run_id: "r1",
      compare_run_ids: ["r2"],
      sections: ["summary", "buyers", "comparison"],
      include_narrative: false,
    });
    expect(buildSpec("T", "r1", [], ["comparison", "summary"], true).sections).toEqual(["summary"]);
  });

  it("submits the chosen spec; the narrative is unavailable without AI", async () => {
    const other = { ...OLIVES_RUN, id: "run-b", label: "Prix -10 %" };
    const onSubmit = vi.fn().mockResolvedValue(undefined);
    render(<ReportBuilderForm runs={[OLIVES_RUN, other]} initialRun={OLIVES_RUN.id} ai="disabled" onSubmit={onSubmit} />);
    expect(screen.getByRole("checkbox", { name: /Inclure un récit/ })).toBeDisabled();
    await userEvent.click(screen.getByRole("checkbox", { name: "Logistique" }));
    await userEvent.click(screen.getByRole("checkbox", { name: /Prix -10 %/ }));
    await userEvent.click(screen.getByRole("button", { name: "Créer le rapport" }));
    expect(onSubmit).toHaveBeenCalledWith({
      title: "Rapport de plan",
      run_id: OLIVES_RUN.id,
      compare_run_ids: ["run-b"],
      sections: ["summary", "financial", "buyers", "logistics", "insights", "comparison"],
      include_narrative: false,
    });
  });
});

describe("<ReportView>", () => {
  it("offers CSV per table, JSON export and the print page", async () => {
    vi.spyOn(api, "report").mockResolvedValue(OLIVES_REPORT);
    render(<ReportView reportId={OLIVES_REPORT.id} />);
    const csv = await screen.findByRole("link", { name: "Exporter en CSV : Acheteurs — buyers" });
    expect(csv).toHaveAttribute("href", downloads.reportCsv(OLIVES_REPORT.id, "buyers", "buyers"));
    expect(screen.getByRole("link", { name: /Export JSON/ })).toHaveAttribute("href", downloads.reportJson(OLIVES_REPORT.id));
    expect(screen.getByRole("link", { name: /Imprimer/ })).toHaveAttribute("href", `/reports/${OLIVES_REPORT.id}/print`);
  });
});

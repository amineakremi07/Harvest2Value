import { render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import { api } from "@/lib/api/endpoints";
import type { DashboardData, InsightView } from "@/lib/api/types";
import { META, OLIVES_RESULT, OLIVES_RUN } from "@/test/fixtures";
import { AiSummary } from "./AiSummary";
import { AlertsPanel } from "./AlertsPanel";
import { deltaBadge, ExecutiveKpis } from "./ExecutiveKpis";
import { RecentRuns } from "./RecentRuns";
import { TopRecommendations } from "./TopRecommendations";

const insight = (id: string, patch: Partial<InsightView>): InsightView => ({
  id,
  run_id: OLIVES_RUN.id,
  rule_id: "WASTE_HIGH",
  rule_version: 1,
  category: "risk",
  severity: "warning",
  entity_ref: null,
  message_key: "k",
  message_params: {},
  message: `message ${id}`,
  evidence: { metrics: [], thresholds: [], entities: [], formula_id: "f", run_id: OLIVES_RUN.id, rule_version: 1 },
  suggested_changes: [],
  dismissed: false,
  created_at: OLIVES_RUN.created_at,
  ...patch,
});

describe("<ExecutiveKpis>", () => {
  it("colors deltas by direction: less waste is good, less profit is bad", () => {
    expect(deltaBadge({ abs: -2, pct: -10 }, "lower")).toEqual({ text: "−10 %", good: true });
    expect(deltaBadge({ abs: -100, pct: -5 }, "higher")).toEqual({ text: "−5 %", good: false });
    expect(deltaBadge({ abs: null, pct: null }, "higher")).toBeUndefined();
  });

  it("renders the five executive KPIs", () => {
    render(<ExecutiveKpis kpis={OLIVES_RESULT.kpis} deltas={{ realized_profit: { abs: 50, pct: 2 } }} hasBaseline />);
    for (const label of ["Profit réalisé", "Chiffre d'affaires", "Vendu", "Taux de pertes", "Coûts totaux"]) {
      expect(screen.getByText(label)).toBeInTheDocument();
    }
    expect(screen.getByText("+2 %")).toHaveClass("text-emerald-300");
  });
});

describe("<AlertsPanel>", () => {
  it("shows risks only, opportunities go to recommendations", () => {
    render(<AlertsPanel runId="r" insights={[insight("a", {}), insight("b", { category: "opportunity" })]} />);
    expect(screen.getByText("message a")).toBeInTheDocument();
    expect(screen.queryByText("message b")).toBeNull();
  });
});

describe("<TopRecommendations>", () => {
  it("combines the main bottleneck, opportunities and the best buyer", () => {
    const data = {
      run: { run_id: "r" },
      top_insights: [insight("o", { category: "opportunity", message: "Plus de demande à Sfax" })],
      main_bottleneck: { key: "k", family: "f", entity: [], label: "Capacité camion", binding_days: [], rank: 1, suggested_label: "+1 camion" },
      best_buyer: { buyer_id: "b", buyer_name: "Huilerie Sfax Export", net_revenue: 1000, sold_kg: 500 },
    } as unknown as DashboardData;
    render(<TopRecommendations data={data} />);
    expect(screen.getByText(/Capacité camion — piste : \+1 camion/)).toBeInTheDocument();
    expect(screen.getByText("Plus de demande à Sfax")).toBeInTheDocument();
    expect(screen.getByText(/Meilleur acheteur : Huilerie Sfax Export/)).toBeInTheDocument();
  });
});

describe("<RecentRuns> and <AiSummary>", () => {
  it("links each run to its summary", () => {
    render(<RecentRuns runs={[OLIVES_RUN]} />);
    expect(screen.getByRole("link", { name: "Référence" })).toHaveAttribute("href", `/runs/${OLIVES_RUN.id}/summary`);
  });

  it("AI summary says the AI is disabled when no key is configured", async () => {
    vi.spyOn(api, "meta").mockResolvedValue({ ...META, llm: { ...META.llm, configured: false } });
    render(<AiSummary runId={OLIVES_RUN.id} />);
    expect(await screen.findByText(/IA désactivée/)).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: /Rédiger/ })).not.toBeInTheDocument();
  });
});

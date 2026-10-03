import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";
import type { DatasetPayload } from "@/lib/api/types";
import { OLIVES_PAYLOAD, OLIVES_RESULT } from "@/test/fixtures";
import { harvestedCrops, suggestedHorizon } from "./horizon";
import { buildRunConfig, initialDraft, RunConfigForm, validateDraft } from "./RunConfigForm";

const withoutColdRoom: DatasetPayload = {
  ...OLIVES_PAYLOAD,
  storage_facilities: (OLIVES_PAYLOAD.storage_facilities ?? []).filter((f) => !f.refrigerated),
};

describe("suggestedHorizon", () => {
  it("matches the backend default (last lot day + longest usable shelf life, capped at 60)", () => {
    // Lots up to day 10, cold shelf life 60 days -> 70, capped at 60 (backend result: 60).
    expect(suggestedHorizon(OLIVES_PAYLOAD)).toBe(60);
    expect(OLIVES_RESULT.horizon_days).toBe(60);
  });

  it("uses the ambient shelf life when there is no refrigerated storage", () => {
    expect(suggestedHorizon(withoutColdRoom)).toBe(10 + 45);
  });

  it("lists harvested crops only", () => {
    expect(harvestedCrops(OLIVES_PAYLOAD)).toEqual([{ id: "olives", name: "olives" }]);
  });
});

describe("buildRunConfig", () => {
  it("sends only the chosen objective's parameters", () => {
    const draft = { ...initialDraft(OLIVES_PAYLOAD), objective: "weighted" as const, weightWaste: "2" };
    const config = buildRunConfig(draft, 1);
    expect(config).toMatchObject({ objective: "weighted", horizon_days: 60, crop_id: null, weights: { profit: 1, waste: 2, cost: 0 } });
    expect(config.service_level_min).toBeUndefined();
  });

  it("converts the service level and the gap from percent", () => {
    const draft = { ...initialDraft(withoutColdRoom), objective: "cost" as const, serviceLevelPct: "90", gapPct: "0,5" };
    expect(buildRunConfig(draft, 1)).toMatchObject({ objective: "cost", service_level_min: 0.9, gap: 0.005, horizon_days: 55 });
  });

  it("rejects an out-of-range horizon and all-zero weights", () => {
    expect(validateDraft({ ...initialDraft(OLIVES_PAYLOAD), horizonDays: "61" })).toMatch(/horizon/i);
    expect(
      validateDraft({ ...initialDraft(OLIVES_PAYLOAD), objective: "weighted", weightProfit: "0", weightWaste: "0", weightCost: "0" }),
    ).toMatch(/poids/i);
    expect(validateDraft(initialDraft(OLIVES_PAYLOAD))).toBeNull();
  });
});

describe("<RunConfigForm>", () => {
  it("is prefilled with the suggested horizon and submits a profit config", async () => {
    const onSubmit = vi.fn();
    render(<RunConfigForm payload={withoutColdRoom} onSubmit={onSubmit} />);
    expect(screen.getByLabelText(/horizon/i)).toHaveValue("55");
    expect(screen.getByText(/Suggéré : 55 j/)).toBeInTheDocument();
    expect(screen.getByRole("radio", { name: /profit/i })).toHaveAttribute("aria-checked", "true");

    await userEvent.type(screen.getByLabelText(/libellé/i), "Référence");
    await userEvent.click(screen.getByRole("button", { name: /lancer/i }));
    expect(onSubmit).toHaveBeenCalledWith(expect.objectContaining({ objective: "profit", horizon_days: 55 }), "Référence");
  });

  it("shows the weights for the weighted objective and blocks invalid input", async () => {
    const onSubmit = vi.fn();
    render(<RunConfigForm payload={OLIVES_PAYLOAD} onSubmit={onSubmit} />);
    await userEvent.click(screen.getByRole("radio", { name: /pondéré/i }));
    for (const label of [/poids profit/i, /poids pertes/i, /poids coûts/i]) {
      await userEvent.clear(screen.getByLabelText(label));
      await userEvent.type(screen.getByLabelText(label), "0");
    }
    await userEvent.click(screen.getByRole("button", { name: /lancer/i }));
    expect(screen.getByRole("alert")).toHaveTextContent(/poids/i);
    expect(onSubmit).not.toHaveBeenCalled();
  });

  it("offers to restore the suggested horizon after an edit", async () => {
    render(<RunConfigForm payload={OLIVES_PAYLOAD} onSubmit={vi.fn()} />);
    const input = screen.getByLabelText(/horizon/i);
    await userEvent.clear(input);
    await userEvent.type(input, "20");
    await userEvent.click(screen.getByRole("button", { name: /rétablir/i }));
    expect(input).toHaveValue("60");
  });
});

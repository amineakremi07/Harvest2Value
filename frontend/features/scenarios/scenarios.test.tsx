import { render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, describe, expect, it, vi } from "vitest";
import * as apiModule from "@/lib/api/endpoints";
import type { ChangeOpInfo, ScenarioSummary } from "@/lib/api/types";
import { META, OLIVES_PAYLOAD, OLIVES_PREVIEW, OLIVES_SCENARIO } from "@/test/fixtures";
import { ChangeBuilder } from "./ChangeBuilder";
import { ChangeList, moveId } from "./ChangeList";
import { DiffPreview } from "./DiffPreview";
import { ScenarioTextInput } from "./ScenarioTextInput";
import { asJsonSchema, initialValue, toPayload } from "./jsonSchema";
import { buildForest, ScenarioTree } from "./ScenarioTree";
import { StaleBadge } from "./StaleBadge";
import { targetOptions } from "./targets";

afterEach(() => vi.restoreAllMocks());

const OPS: ChangeOpInfo[] = META.change_ops ?? [];
const op = (name: string) => OPS.find((o) => o.op === name) as ChangeOpInfo;

describe("jsonSchema helpers (params_schema from /meta)", () => {
  it("builds an initial value from defaults and enums", () => {
    const schema = asJsonSchema(op("buyer_price").params_schema);
    expect(initialValue(schema, schema)).toEqual({ mode: "absolute", value: "" });
    const cold = asJsonSchema(op("cold_chain").params_schema);
    expect(initialValue(cold, cold)).toEqual({ required: false, entity: "buyer" });
  });

  it("converts numeric strings, checks bounds and drops empty optionals", () => {
    const schema = asJsonSchema(op("buyer_price").params_schema);
    expect(toPayload({ mode: "relative_pct", value: "-10" }, schema, schema)).toEqual({ value: { mode: "relative_pct", value: -10 }, errors: {} });
    expect(toPayload({ mode: "absolute", value: "" }, schema, schema).errors).toHaveProperty("value");
    const timing = asJsonSchema(op("harvest_timing").params_schema);
    expect(toPayload({ shift_days: "1.5" }, timing, timing).errors.shift_days).toMatch(/entier/i);
    const route = asJsonSchema(op("route").params_schema);
    expect(toPayload({ field: "road_condition", mode: null, value: "poor" }, route, route).value).toEqual({ field: "road_condition", value: "poor" });
    expect(toPayload({ field: "distance_km", mode: "delta", value: "12" }, route, route).value).toEqual({ field: "distance_km", mode: "delta", value: 12 });
  });

  it("handles nested $defs (add_storage)", () => {
    const schema = asJsonSchema(op("add_storage").params_schema);
    const value = { facility: { id: "cold2", name: "Frigo 2", capacity_kg: "800", refrigerated: true, cost_per_kg_per_day: "0,1" } };
    expect(toPayload(value, schema, schema)).toEqual({
      value: { facility: { id: "cold2", name: "Frigo 2", capacity_kg: 800, refrigerated: true, cost_per_kg_per_day: 0.1 } },
      errors: {},
    });
  });
});

describe("targetOptions", () => {
  it("offers every buyer plus 'Tous' for one_or_all ops", () => {
    const options = targetOptions("buyer_price", "one_or_all", OLIVES_PAYLOAD);
    expect(options[0]).toEqual({ value: "*", label: "Tous" });
    expect(options).toHaveLength(1 + OLIVES_PAYLOAD.buyers.length);
  });

  it("follows params.entity for cold_chain and has no target for add_* ops", () => {
    expect(targetOptions("cold_chain", "one", OLIVES_PAYLOAD, { entity: "crop" }).map((o) => o.value)).toEqual(["olives"]);
    expect(targetOptions("add_storage", "none", OLIVES_PAYLOAD)).toEqual([]);
    expect(targetOptions("vehicle_count", "one", OLIVES_PAYLOAD).map((o) => o.label)).toEqual(["Camion 3 t"]);
  });
});

describe("<ChangeBuilder>", () => {
  it("lists the ops from /meta and builds a -10 % price change on every buyer", async () => {
    const onAdd = vi.fn().mockResolvedValue(true);
    render(<ChangeBuilder ops={OPS} payload={OLIVES_PAYLOAD} onAdd={onAdd} />);
    expect(within(screen.getByLabelText("Opération")).getAllByRole("option")).toHaveLength(OPS.length);

    await userEvent.selectOptions(screen.getByLabelText("Cible"), "*");
    await userEvent.selectOptions(screen.getByLabelText("Mode"), "relative_pct");
    await userEvent.type(screen.getByLabelText("Valeur"), "-10");
    await userEvent.click(screen.getByRole("button", { name: /ajouter la modification/i }));

    expect(onAdd).toHaveBeenCalledWith({ op: "buyer_price", target: "*", params: { mode: "relative_pct", value: -10 }, note: null });
  });

  it("regenerates the form when the op changes and validates it", async () => {
    const onAdd = vi.fn();
    render(<ChangeBuilder ops={OPS} payload={OLIVES_PAYLOAD} onAdd={onAdd} />);
    await userEvent.selectOptions(screen.getByLabelText("Opération"), "harvest_timing");
    expect(screen.getByLabelText("Décalage (jours)")).toBeInTheDocument();
    expect(within(screen.getByLabelText("Cible")).getAllByRole("option")).toHaveLength(OLIVES_PAYLOAD.harvest_lots.length);
    await userEvent.click(screen.getByRole("button", { name: /ajouter la modification/i }));
    expect(screen.getByText("Valeur requise")).toBeInTheDocument();
    expect(onAdd).not.toHaveBeenCalled();
  });

  it("renders a target-less op with nested params (add_storage)", async () => {
    render(<ChangeBuilder ops={OPS} payload={OLIVES_PAYLOAD} onAdd={vi.fn()} />);
    await userEvent.selectOptions(screen.getByLabelText("Opération"), "add_storage");
    expect(screen.queryByLabelText("Cible")).toBeNull();
    expect(screen.getByRole("group", { name: /facility|storage/i })).toBeInTheDocument();
  });
});

describe("<ChangeList>", () => {
  it("shows the backend summary of each change and its actions", async () => {
    const onToggle = vi.fn();
    const onDelete = vi.fn();
    render(
      <ChangeList changes={OLIVES_SCENARIO.changes} applied={OLIVES_PREVIEW.applied} onToggle={onToggle} onDelete={onDelete} onMove={vi.fn()} />,
    );
    expect(screen.getByText(/2.4 -> 2.16/)).toBeInTheDocument();
    expect(screen.getByText("tous")).toBeInTheDocument();
    await userEvent.click(screen.getByRole("checkbox", { name: /activer/i }));
    expect(onToggle).toHaveBeenCalledWith(OLIVES_SCENARIO.changes[0]);
    await userEvent.click(screen.getByRole("button", { name: "Supprimer" }));
    expect(onDelete).toHaveBeenCalled();
  });

  it("moveId swaps neighbours and ignores moves past the ends", () => {
    expect(moveId(["a", "b", "c"], "b", -1)).toEqual(["b", "a", "c"]);
    expect(moveId(["a", "b", "c"], "b", 1)).toEqual(["a", "c", "b"]);
    expect(moveId(["a", "b"], "a", -1)).toEqual(["a", "b"]);
  });
});

describe("<DiffPreview>", () => {
  it("lists the changed fields with before and after values", () => {
    render(<DiffPreview preview={OLIVES_PREVIEW} />);
    expect(screen.getByText("buyers[buyer_tn_01].price_per_kg")).toBeInTheDocument();
    expect(screen.getAllByText("modifié").length).toBe(OLIVES_PREVIEW.diff.length);
  });
});

const scenario = (id: string, parent: string | null, created: string): ScenarioSummary => ({
  ...OLIVES_SCENARIO.scenario,
  id,
  name: `S-${id}`,
  parent_id: parent,
  created_at: created,
});

describe("ScenarioTree", () => {
  const list = [scenario("c", "a", "2026-01-03"), scenario("a", null, "2026-01-01"), scenario("b", "a", "2026-01-02"), scenario("x", "gone", "2026-01-04")];

  it("nests branches under their parent, oldest first, orphans as roots", () => {
    const forest = buildForest(list);
    expect(forest.map((n) => n.scenario.id)).toEqual(["a", "x"]);
    expect(forest[0].children.map((n) => n.scenario.id)).toEqual(["b", "c"]);
  });

  it("marks the active scenario", () => {
    render(<ScenarioTree scenarios={list} activeId="b" />);
    expect(screen.getByRole("link", { name: "S-b" })).toHaveAttribute("aria-current", "page");
  });
});

describe("<StaleBadge>", () => {
  it("shows the base and current versions", () => {
    render(<StaleBadge baseVersion={1} currentVersion={3} />);
    expect(screen.getByText(/Obsolète · v1 → v3/)).toBeInTheDocument();
  });
});

describe("<ScenarioTextInput> — free text -> proposed changes, added one by one", () => {
  it("lists validated proposals, rejected ones with their reason, and adds as ai_proposed", async () => {
    vi.spyOn(apiModule.api, "meta").mockResolvedValue({ ...META, llm: { ...META.llm, configured: true } });
    const parse = vi.spyOn(apiModule.api, "parseScenarioText").mockResolvedValue({
      changes: [{ op: "buyer_price", target: "buyer_tn_01", params: { mode: "relative_pct", value: -10 }, summary: "Prix de Huilerie Sfax Export : -10 %", quote: "baisse de 10 %" }],
      rejected: [{ change: { op: "buyer_price" }, reason: "valeur(s) absente(s) de la phrase : -25" }],
      questions: [],
      prompt: "parse_changes@v1",
      model: "mock",
    });
    const onAdd = vi.fn().mockResolvedValue(true);
    render(<ScenarioTextInput scenarioId="s1" onAdd={onAdd} />);
    await userEvent.type(await screen.findByRole("textbox", { name: "Modification en langage naturel" }), "Et si le prix de Sfax baisse de 10 % ?");
    await userEvent.click(screen.getByRole("button", { name: /Traduire/ }));
    expect(parse).toHaveBeenCalledWith("Et si le prix de Sfax baisse de 10 % ?", { scenario_id: "s1" });
    expect(await screen.findByText(/absente\(s\) de la phrase/)).toBeInTheDocument();
    expect(onAdd).not.toHaveBeenCalled();
    await userEvent.click(screen.getByRole("button", { name: "Ajouter : Prix de Huilerie Sfax Export : -10 %" }));
    expect(onAdd).toHaveBeenCalledWith({ op: "buyer_price", target: "buyer_tn_01", params: { mode: "relative_pct", value: -10 }, source: "ai_proposed", note: "baisse de 10 %" });
    expect(screen.getByRole("button", { name: "Ajouter : Prix de Huilerie Sfax Export : -10 %" })).toHaveTextContent("Ajoutée");
  });

  it("says the AI is disabled without a key", async () => {
    vi.spyOn(apiModule.api, "meta").mockResolvedValue({ ...META, llm: { ...META.llm, configured: false } });
    render(<ScenarioTextInput scenarioId="s1" onAdd={vi.fn()} />);
    expect(await screen.findByText(/IA désactivée/)).toBeInTheDocument();
  });
});

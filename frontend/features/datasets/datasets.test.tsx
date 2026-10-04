import { render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, describe, expect, it, vi } from "vitest";
import { ApiError } from "@/lib/api/client";
import { api } from "@/lib/api/endpoints";
import type { DatasetDetail, ImportResult } from "@/lib/api/types";
import { OLIVES_PAYLOAD } from "@/test/fixtures";
import { DatasetEditor, parseDraft, withField } from "./DatasetEditor";
import { ImportPanel } from "./DatasetsIndex";

afterEach(() => vi.restoreAllMocks());

const detail = (version_no = 1): DatasetDetail => ({
  dataset: {
    id: "d1",
    name: "Olives",
    description: null,
    source: "template",
    template_key: "tunisia_olives",
    archived: false,
    current_version_no: version_no,
    is_valid: true,
    crops: ["olives"],
    harvest_kg: 12000,
    buyer_count: 4,
    created_at: "2026-10-03T10:00:00Z",
    updated_at: "2026-10-03T10:00:00Z",
  },
  current_version: {
    version_no,
    schema_version: "2.0",
    content_hash: "h",
    is_valid: true,
    note: null,
    created_at: "2026-10-03T10:00:00Z",
    validation: { errors: [], warnings: [], assumptions: [] },
    payload: OLIVES_PAYLOAD,
  },
});

describe("draft helpers", () => {
  it("parses JSON objects and reports invalid JSON", () => {
    expect(parseDraft('{"a": 1}').parsed).toEqual({ a: 1 });
    expect(parseDraft("[1]").parseError).toMatch(/objet/);
    expect(parseDraft("{").parseError).toMatch(/JSON invalide/);
  });

  it("updates one field of one buyer without touching the others", () => {
    const first = OLIVES_PAYLOAD.buyers[0];
    const next = withField(OLIVES_PAYLOAD, "buyers", first.id, "price_per_kg", 9.5);
    expect(next.buyers[0].price_per_kg).toBe(9.5);
    expect(next.buyers[1]).toBe(OLIVES_PAYLOAD.buyers[1]);
    expect(OLIVES_PAYLOAD.buyers[0].price_per_kg).toBe(first.price_per_kg);
  });
});

describe("<ImportPanel>", () => {
  it("uploads the chosen file", async () => {
    const result = { source_format: "v1", assumptions: [], dataset: detail() } as ImportResult;
    const spy = vi.spyOn(api, "importDataset").mockResolvedValue(result);
    const onImported = vi.fn();
    render(<ImportPanel onImported={onImported} />);
    const file = new File([JSON.stringify({ farm: {} })], "v1.json", { type: "application/json" });
    await userEvent.upload(screen.getByLabelText(/Fichier JSON/), file);
    await userEvent.type(screen.getByLabelText(/Nom/), "Ma ferme");
    await userEvent.click(screen.getByRole("button", { name: "Importer" }));
    expect(spy).toHaveBeenCalledWith(file, "Ma ferme");
    expect(onImported).toHaveBeenCalledWith(result);
  });

  it("asks for a file", async () => {
    render(<ImportPanel onImported={vi.fn()} />);
    await userEvent.click(screen.getByRole("button", { name: "Importer" }));
    expect(screen.getByRole("alert")).toHaveTextContent("Choisissez un fichier JSON.");
  });
});

describe("<DatasetEditor>", () => {
  it("quick edit -> validate -> save a new version with If-Match", async () => {
    vi.spyOn(api, "dataset").mockResolvedValueOnce(detail(1)).mockResolvedValueOnce(detail(2));
    vi.spyOn(api, "datasetVersions").mockResolvedValue({ items: [], total: 0, page: 1, page_size: 100 });
    const validate = vi.spyOn(api, "validateDataset").mockResolvedValue({ errors: [], warnings: [], assumptions: [] });
    const save = vi.spyOn(api, "saveDatasetPayload").mockResolvedValue({ ...detail(2).current_version });
    render(<DatasetEditor datasetId="d1" />);
    const buyer = OLIVES_PAYLOAD.buyers[0];
    const price = await screen.findByRole("spinbutton", { name: `Prix de ${buyer.name}` });
    await userEvent.clear(price);
    await userEvent.type(price, "3.1");
    await userEvent.click(screen.getByRole("button", { name: "Valider" }));
    expect(validate.mock.calls[0][1]).toMatchObject({ buyers: expect.arrayContaining([expect.objectContaining({ id: buyer.id, price_per_kg: 3.1 })]) });
    expect(await screen.findByText("Données valides.")).toBeInTheDocument();

    await userEvent.type(screen.getByLabelText("Note de version"), "prix de mars");
    await userEvent.click(screen.getByRole("button", { name: "Enregistrer v2" }));
    expect(save).toHaveBeenCalledWith("d1", expect.objectContaining({ buyers: expect.any(Array) }), 1, "prix de mars");
    expect(await screen.findByRole("button", { name: "Enregistrer v3" })).toBeDisabled();
    // The editor is remounted for v2: the confirmation and the validation report survive it.
    expect(screen.getByRole("status")).toHaveTextContent("Version v2 enregistrée.");
    expect(screen.getByText("Données valides.")).toBeInTheDocument();
  });

  it("explains a concurrent edit (VERSION_CONFLICT)", async () => {
    vi.spyOn(api, "dataset").mockResolvedValue(detail(1));
    vi.spyOn(api, "saveDatasetPayload").mockRejectedValue(new ApiError(409, "VERSION_CONFLICT", "conflict"));
    render(<DatasetEditor datasetId="d1" />);
    await userEvent.click(await screen.findByRole("tab", { name: "JSON complet" }));
    const textarea = screen.getByRole("textbox", { name: "Données au format JSON" });
    const changed = JSON.stringify({ ...OLIVES_PAYLOAD, currency: "EUR" }, null, 2);
    await userEvent.clear(textarea);
    await userEvent.click(textarea);
    await userEvent.paste(changed);
    await userEvent.click(screen.getByRole("button", { name: "Enregistrer v2" }));
    expect(await screen.findByRole("alert")).toHaveTextContent(/Une autre version a été enregistrée/);
  });

  it("shows the versions and their diff", async () => {
    vi.spyOn(api, "dataset").mockResolvedValue(detail(2));
    vi.spyOn(api, "datasetVersions").mockResolvedValue({
      items: [
        { version_no: 2, schema_version: "2.0", content_hash: "b", is_valid: true, note: "prix", created_at: "2026-10-03T11:00:00Z" },
        { version_no: 1, schema_version: "2.0", content_hash: "a", is_valid: true, note: null, created_at: "2026-10-03T10:00:00Z" },
      ],
      total: 2,
      page: 1,
      page_size: 100,
    });
    const diff = vi.spyOn(api, "datasetDiff").mockResolvedValue({ from_version: 1, to_version: 2, changes: [{ path: "buyers[0].price_per_kg", kind: "changed", before: 2.4, after: 3.1 }] });
    render(<DatasetEditor datasetId="d1" />);
    await userEvent.click(await screen.findByRole("tab", { name: "Versions" }));
    const table = await screen.findByRole("table", { name: "Différences entre v1 et v2" });
    expect(diff).toHaveBeenCalledWith("d1", 1, 2);
    expect(within(table).getByText("buyers[0].price_per_kg")).toBeInTheDocument();
    await waitFor(() => expect(screen.getByRole("link", { name: "Exporter la version 1 en JSON" })).toHaveAttribute("href", expect.stringContaining("version=1")));
  });
});

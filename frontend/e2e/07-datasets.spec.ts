// Phase 14 — datasets from the UI: import a v1 file, edit, validate, save a new version, diff, export.
import path from "node:path";
import { expect, test } from "@playwright/test";
import { API, unique } from "./helpers";

const V1_FILE = path.resolve("..", "backend", "tests", "fixtures", "v1", "tunisia_olives.json");

test("datasets: import v1 -> edit -> validate -> new version -> diff -> export -> optimize", async ({ page }) => {
  await page.goto("/datasets");
  const name = unique("Import v1");
  await page.getByLabel(/Fichier JSON/).setInputFiles(V1_FILE);
  await page.getByLabel(/Nom \(facultatif\)/).fill(name);
  await page.getByRole("button", { name: "Importer" }).click();

  await expect(page).toHaveURL(/\/datasets\/[^/?]+\?imported=v1$/);
  const datasetId = new URL(page.url()).pathname.split("/").pop() as string;
  await expect(page.getByRole("heading", { name })).toBeVisible();
  await expect(page.getByText(/format v1/)).toBeVisible();
  await expect(page.getByRole("heading", { name: "Hypothèses retenues" })).toBeVisible();

  // Quick edit of the first buyer's price, validated then saved as v2 (If-Match v1).
  const price = page.getByRole("spinbutton", { name: /^Prix de / }).first();
  await price.fill("3.33");
  await page.getByRole("button", { name: "Valider" }).click();
  await expect(page.getByRole("region", { name: "Résultat de la validation" })).toContainText("Données valides.");
  await page.getByLabel("Note de version").fill("prix e2e");
  await page.getByRole("button", { name: "Enregistrer v2" }).click();
  await expect(page.getByRole("status").filter({ hasText: "Version v2 enregistrée." })).toBeVisible();
  await expect(page.getByText("Version v2", { exact: true })).toBeVisible();

  // Versions and their diff.
  await page.getByRole("tab", { name: "Versions" }).click();
  const diff = page.getByRole("table", { name: "Différences entre v1 et v2" });
  await expect(diff).toContainText("price_per_kg");
  await expect(diff).toContainText("3,33");

  // Exports.
  const exported = await page.request.get(`${API}/datasets/${datasetId}/export?format=json`);
  expect(exported.ok()).toBeTruthy();
  expect((await exported.json()).buyers[0].price_per_kg).toBe(3.33);
  const csv = await page.request.get(`${API}/datasets/${datasetId}/export?format=csv`);
  expect(csv.headers()["content-type"]).toMatch(/csv|zip/);

  // The dataset is listed and can be optimized.
  await page.locator(`main a[href="/optimize?dataset=${datasetId}"]`).click();
  await expect(page).toHaveURL(new RegExp(`/optimize\\?dataset=${datasetId}`));
  await page.goto("/datasets");
  await expect(page.getByRole("link", { name })).toBeVisible();
});

test("datasets: create from a template, rename, invalid JSON is blocked", async ({ page }) => {
  await page.goto("/datasets");
  await page.getByRole("button", { name: /Créer depuis le modèle .*Dattes|Créer depuis le modèle/ }).first().click();
  await expect(page).toHaveURL(/\/datasets\/[^/?]+$/);
  const name = unique("Renommé");
  await page.getByLabel("Nom du jeu de données").fill(name);
  await page.getByRole("button", { name: "Renommer" }).click();
  await expect(page.getByRole("heading", { name })).toBeVisible();

  await page.getByRole("tab", { name: "JSON complet" }).click();
  await page.getByRole("textbox", { name: "Données au format JSON" }).fill("{ pas du json");
  await expect(page.getByText(/JSON invalide/)).toBeVisible();
  await expect(page.getByRole("button", { name: /Enregistrer v/ })).toBeDisabled();
});

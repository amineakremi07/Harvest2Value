// E2E n°1 — data -> run -> reading the result (phase 8, milestone M1).
import { expect, test } from "@playwright/test";
import { API, datasetFromTemplate, launchRun, unique } from "./helpers";

test("E2E n°1: template data -> optimization run -> every result tab", async ({ page }) => {
  // Root redirects to the dashboard.
  await page.goto("/");
  await expect(page).toHaveURL(/\/dashboard$/);

  // Data: the olives template becomes a dataset; the form is prefilled with the suggested horizon.
  await datasetFromTemplate(page, "tunisia_olives");
  await expect(page.getByLabel(/Horizon/)).toHaveValue("60");
  await expect(page.getByText("Suggéré : 60 j")).toBeVisible();
  await expect(page.getByRole("radio", { name: "Profit" })).toHaveAttribute("aria-checked", "true");

  // Run: the status banner polls until the solver is done.
  const label = unique("E2E olives");
  const runId = await launchRun(page, label);
  await expect(page.getByRole("heading", { name: label })).toBeVisible();

  // Summary: KPIs, Sankey and buyer table.
  await expect(page.getByTestId("outcome-label")).toContainText(/optimal/i);
  const kpis = page.getByLabel("Indicateurs clés");
  await expect(kpis.getByText("Profit réalisé")).toBeVisible();
  await expect(page.getByRole("img", { name: /Flux de la récolte/ })).toBeVisible();
  await expect(page.getByRole("table", { name: "Synthèse par acheteur" })).toContainText("Huilerie Sfax Export");

  // The numbers shown are the solver's.
  const result = await (await page.request.get(`${API}/runs/${runId}/result`)).json();
  const profit = Math.round(result.kpis.realized_profit).toLocaleString("fr-FR");
  await expect(kpis).toContainText(profit);

  // Allocation.
  await page.getByRole("link", { name: "Allocation", exact: true }).click();
  const matrix = page.getByRole("table", { name: "Matrice d'allocation acheteur × jour" });
  await expect(matrix).toContainText("Huilerie Sfax Export");
  await matrix.getByRole("button").first().click();
  await expect(page.getByText(/du lot/).first()).toBeVisible();

  // Inventory.
  await page.getByRole("link", { name: "Stock", exact: true }).click();
  await expect(page.getByRole("img", { name: /Évolution du stock/ })).toBeVisible();

  // Logistics.
  await page.getByRole("link", { name: "Logistique", exact: true }).click();
  await expect(page.getByRole("table", { name: "Utilisation de la flotte" })).toContainText("Camion 3 t");
  await expect(page.getByRole("table", { name: "Trajets planifiés" })).toBeVisible();

  // Explain and network (phase 10).
  await page.getByRole("link", { name: "Explication", exact: true }).click();
  await expect(page.getByRole("region", { name: "Décisions" })).toBeVisible();
  await page.getByRole("link", { name: "Réseau", exact: true }).click();
  await expect(page.getByTestId("supply-chain-graph")).toBeVisible();

  // Insights.
  await page.getByRole("link", { name: "Alertes", exact: true }).click();
  await expect(page.getByText("Alertes et opportunités")).toBeVisible();

  // Raw JSON.
  await page.getByRole("link", { name: "Données brutes", exact: true }).click();
  await expect(page.locator("pre")).toContainText(runId);

  // The run is listed and the dashboard shows the latest plan.
  await page.getByRole("link", { name: "Exécutions", exact: true }).click();
  await expect(page.getByRole("link", { name: label })).toBeVisible();
  await page.getByRole("link", { name: "Tableau de bord", exact: true }).click();
  await expect(page.getByRole("link", { name: label })).toBeVisible();
  await expect(page.getByLabel("Indicateurs exécutifs")).toContainText(profit);
});

test("settings link to the legacy interface", async ({ page }) => {
  await page.goto("/settings");
  await page.getByRole("link", { name: "Ancienne interface" }).click();
  await expect(page).toHaveURL(/\/legacy$/);
});

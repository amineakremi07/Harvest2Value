// E2E n°3 — scenario −10 % -> run -> comparison (phase 9, milestone M2), plus branch, duplicate
// and rebase of the scenario journey.
import { expect, test, type Page } from "@playwright/test";
import { API, datasetFromTemplate, launchRun, makeInputUnique, unique, waitForSucceeded } from "./helpers";

async function createScenario(page: Page, name: string, datasetId: string): Promise<string> {
  await page.goto("/scenarios");
  const form = page.getByRole("form", { name: "Nouveau scénario" });
  await form.getByLabel("Nom").fill(name);
  await form.getByLabel("Données de base").selectOption(datasetId);
  await form.getByRole("button", { name: "Créer le scénario" }).click();
  await expect(page).toHaveURL(/\/scenarios\/[^/]+$/);
  await expect(page.getByRole("heading", { name })).toBeVisible();
  return page.url().split("/scenarios/")[1];
}

async function addPriceDrop(page: Page) {
  const builder = page.getByRole("form", { name: "Nouvelle modification" });
  await builder.getByLabel("Opération").selectOption("buyer_price");
  await builder.getByLabel("Cible").selectOption("*");
  await builder.getByLabel("Mode").selectOption("relative_pct");
  await builder.getByLabel("Valeur", { exact: true }).fill("-10");
  await builder.getByRole("button", { name: "Ajouter la modification" }).click();
}

test("E2E n°3: scenario −10 % -> run -> comparison with the baseline", async ({ page }) => {
  // Baseline run on the olives template.
  const datasetId = await datasetFromTemplate(page, "tunisia_olives");
  await makeInputUnique(page.request, datasetId);
  await page.reload();
  await expect(page.getByRole("form", { name: "Configuration de l'exécution" })).toBeVisible();
  const baseLabel = unique("Base");
  const baselineId = await launchRun(page, baseLabel);

  // Scenario: every buyer price −10 %, built from the /meta params schema.
  const scenarioName = unique("Prix −10 %");
  await createScenario(page, scenarioName, datasetId);
  await addPriceDrop(page);
  const changes = page.getByTestId("change-item");
  await expect(changes).toHaveCount(1);
  await expect(changes.first()).toContainText("2.4 -> 2.16"); // backend summary of the applied change
  const diff = page.getByRole("table", { name: "Différences avec la version de base" });
  await expect(diff).toContainText("buyers[buyer_tn_01].price_per_kg");

  // Run the scenario.
  const scenarioRunId = await launchRun(page, scenarioName);
  await expect(page.getByText("scénario").first()).toBeVisible();

  // Compare: the baseline is picked automatically (latest non-scenario run of the dataset).
  await page.getByRole("main").getByRole("link", { name: "Comparer" }).click();
  await expect(page).toHaveURL(new RegExp(`baseline=${baselineId}.*runs=${scenarioRunId}`));
  await expect(page.getByRole("list", { name: "Changements notables" })).toContainText(/Realized profit falls/);
  const kpis = page.getByRole("table", { name: "Comparaison des indicateurs" });
  await expect(kpis.getByRole("row", { name: /Realized revenue/ })).toContainText("(−10 %)");
  await expect(page.getByRole("table", { name: /Volumes par acheteur/ })).toContainText("Huilerie Sfax Export");
  await expect(page.getByRole("img", { name: /Passage du profit/ })).toBeVisible();

  // The comparison matches the API.
  const comparison = await (
    await page.request.post(`${API}/comparisons`, { data: { baseline_run_id: baselineId, run_ids: [scenarioRunId] } })
  ).json();
  const revenue = comparison.kpi_table.find((r: { kpi: string }) => r.kpi === "realized_revenue");
  expect(revenue.deltas[scenarioRunId].pct).toBe(-10);
});

test("scenario journey: branch, duplicate, toggle, stale and rebase", async ({ page }) => {
  const datasetId = await datasetFromTemplate(page, "tunisia_wheat");
  const parentName = unique("Parent");
  const parentId = await createScenario(page, parentName, datasetId);
  await addPriceDrop(page);
  await expect(page.getByTestId("change-item")).toHaveCount(1);

  // Branch: the child inherits the parent's changes through the lineage.
  await page.getByRole("button", { name: "Brancher" }).click();
  const branchName = unique("Branche");
  await page.getByLabel("Nom de la branche").fill(branchName);
  await page.getByRole("form", { name: "Créer une branche" }).getByRole("button", { name: "Créer" }).click();
  await expect(page.getByRole("heading", { name: branchName })).toBeVisible();
  await expect(page.getByRole("navigation", { name: "Lignée" })).toContainText(parentName);
  await expect(page.getByRole("table", { name: "Différences avec la version de base" })).toContainText("price_per_kg");
  await expect(page.getByRole("list", { name: "Arbre des scénarios" })).toContainText(parentName);

  // Duplicate the parent: same changes, new scenario.
  await page.goto(`/scenarios/${parentId}`);
  await page.getByRole("button", { name: "Dupliquer" }).click();
  await expect(page).not.toHaveURL(new RegExp(`/scenarios/${parentId}$`));
  await expect(page.getByTestId("change-item")).toHaveCount(1);

  // Disabling the change empties the diff.
  await page.getByRole("checkbox", { name: /Activer/ }).click();
  await expect(page.getByText("Aucune différence avec la version de base.")).toBeVisible();

  // A new dataset version makes the parent stale; rebase moves it to the current version.
  const dataset = await (await page.request.get(`${API}/datasets/${datasetId}`)).json();
  const payload = dataset.current_version.payload;
  payload.harvest_lots[0].quantity_kg += 1000;
  const put = await page.request.put(`${API}/datasets/${datasetId}/payload`, {
    data: { payload, note: "e2e new version" },
    headers: { "If-Match": `"${dataset.current_version.version_no}"` },
  });
  expect(put.ok()).toBeTruthy();

  await page.goto(`/scenarios/${parentId}`);
  await expect(page.getByText(/Obsolète · v1 → v2/)).toBeVisible();
  await page.getByRole("button", { name: /Rebaser sur v2/ }).click();
  await expect(page.getByText(/Obsolète · v1/)).toHaveCount(0);
  await expect(page.getByText("Base : données v2")).toBeVisible();

  // The rebased scenario still runs.
  await launchRun(page, unique("Rebased"));
  await waitForSucceeded(page);
});

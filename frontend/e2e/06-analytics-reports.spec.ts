// Phases 12-13 — Analytics Center, and E2E n°5: frozen report -> CSV / JSON exports -> print page;
// the report does not change when the data and runs change afterwards.
import { expect, test } from "@playwright/test";
import { API, datasetFromTemplate, launchRun, makeInputUnique, unique } from "./helpers";

test("Analytics Center: five sections for a run", async ({ page }) => {
  const datasetId = await datasetFromTemplate(page, "tunisia_dates");
  await makeInputUnique(page.request, datasetId);
  await page.reload();
  const runId = await launchRun(page, unique("Analytics dates"));
  await page.locator(`a[href="/analytics?run=${runId}"]`).click();
  await expect(page).toHaveURL(new RegExp(`/analytics\\?run=${runId}`));
  await expect(page.getByRole("table", { name: "Revenus par acheteur" })).toBeVisible();
  for (const [tab, table] of [
    ["Opérationnel", "Utilisation du stockage"],
    ["Acheteurs", "Analyse des acheteurs"],
    ["Logistique", "Utilisation des véhicules"],
    ["Culture", "Devenir des lots"],
  ] as const) {
    await page.getByRole("tab", { name: tab }).click();
    await expect(page.getByRole("table", { name: table })).toBeVisible();
  }
});

test("E2E n°5: frozen report, exports and print page", async ({ page }) => {
  const datasetId = await datasetFromTemplate(page, "tunisia_olives");
  await makeInputUnique(page.request, datasetId);
  await page.reload();
  const label = unique("Rapport olives");
  const runId = await launchRun(page, label);

  await page.getByRole("link", { name: "Rapport", exact: true }).click();
  await expect(page).toHaveURL(new RegExp(`/reports/new\\?run=${runId}`));
  const title = unique("Bilan olives");
  await page.getByLabel("Titre").fill(title);
  await page.getByRole("checkbox", { name: "Logistique" }).check();
  await page.getByRole("button", { name: "Créer le rapport" }).click();
  await expect(page).toHaveURL(/\/reports\/(?!new)[^/?]+$/);
  const reportId = page.url().split("/reports/")[1];
  const report = page.getByRole("article", { name: `Rapport : ${title}` });
  await expect(report.getByRole("region", { name: "Logistique" })).toBeVisible();
  const buyersTable = report.getByRole("table", { name: "Acheteurs — Acheteurs" });
  const before = await buyersTable.innerText();

  // CSV per table and JSON exports.
  const csvHref = await page.getByRole("link", { name: "Exporter en CSV : Acheteurs — buyers" }).getAttribute("href");
  const csv = await page.request.get(csvHref as string);
  expect(csv.headers()["content-type"]).toContain("text/csv");
  expect(await csv.text()).toContain("buyer_name");
  const json = await page.request.get(`${API}/reports/${reportId}/export.json`);
  expect((await json.json()).snapshot.title).toBe(title);

  // The data and the run change: the report stays exactly the same.
  await makeInputUnique(page.request, datasetId);
  expect((await page.request.delete(`${API}/runs/${runId}`)).status()).toBe(204);
  await page.reload();
  await expect(buyersTable).toBeVisible();
  expect(await buyersTable.innerText()).toBe(before);

  // Print page: own layout (no app shell), paper colors, @page CSS.
  await page.goto(`/reports/${reportId}/print`);
  await expect(page.getByRole("article", { name: `Rapport : ${title}` })).toBeVisible();
  await expect(page.getByRole("navigation", { name: "Navigation principale" })).toHaveCount(0);
  await page.emulateMedia({ media: "print" });
  await expect(page.getByRole("button", { name: /Imprimer/ })).toBeHidden();
});

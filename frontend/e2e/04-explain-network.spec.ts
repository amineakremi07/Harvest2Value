// Phase 10 — Explainability Center and network; E2E n°4 (partial): alert -> test -> comparison.
import { expect, test } from "@playwright/test";
import { API, datasetFromTemplate, launchRun, makeInputUnique, unique } from "./helpers";

test("E2E n°4 (partial): every buyer explained, alert -> test the recommendation -> comparison", async ({ page }) => {
  const datasetId = await datasetFromTemplate(page, "tunisia_wheat");
  await makeInputUnique(page.request, datasetId);
  await page.reload();
  const runId = await launchRun(page, unique("Explain wheat"));

  await page.getByRole("link", { name: "Explication", exact: true }).click();
  await expect(page.getByRole("region", { name: "Décisions" })).toBeVisible();

  // Every buyer of the plan has a "why, and why not more" card.
  const result = await (await page.request.get(`${API}/runs/${runId}/result`)).json();
  for (const buyer of result.buyers as { buyer_name: string }[]) {
    const card = page.getByRole("article", { name: `Décision : ${buyer.buyer_name}` });
    await expect(card.getByRole("region", { name: "Pourquoi", exact: true })).toBeVisible();
    await expect(card.getByRole("region", { name: /Pourquoi pas (plus|servi)/ })).toBeVisible();
  }

  // Marginal values: measured by re-optimization, then shown as the main value.
  await page.getByRole("button", { name: "Mesurer par ré-optimisation" }).click();
  await expect(page.getByRole("img", { name: /Effet mesuré de chaque modification/ })).toBeVisible({ timeout: 60_000 });

  // Alert with a suggested change -> test it -> comparison against this run.
  await page.getByRole("button", { name: "Tester cette recommandation" }).first().click();
  await expect(page).toHaveURL(new RegExp(`/compare\\?baseline=${runId}&runs=`));
  await expect(page.getByRole("table", { name: "Comparaison des indicateurs" })).toBeVisible({ timeout: 60_000 });
  await expect(page.getByRole("img", { name: /Passage du profit/ })).toBeVisible();
});

test("supply-chain network with the period scrubber", async ({ page }) => {
  await datasetFromTemplate(page, "tunisia_olives");
  await launchRun(page, unique("Network olives"));
  await page.getByRole("link", { name: "Réseau", exact: true }).click();
  const graph = page.getByTestId("supply-chain-graph");
  await expect(graph).toHaveAttribute("aria-label", /sur toute la période/);
  await expect(graph.getByText("Huilerie Sfax Export")).toBeVisible();

  await page.getByRole("checkbox", { name: "Toute la période" }).uncheck();
  await expect(graph).toHaveAttribute("aria-label", /du jour 0/);
  await page.getByRole("button", { name: "Jour suivant" }).click();
  await expect(graph).toHaveAttribute("aria-label", /du jour 1/);
});

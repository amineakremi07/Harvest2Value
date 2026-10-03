import { expect, type APIRequestContext, type Page } from "@playwright/test";

export const API = "http://localhost:8000/api/v2";

export function unique(prefix: string): string {
  return `${prefix} ${Date.now().toString(36)}`;
}

/** /optimize: create a dataset from a template, returns its id (read from the URL). */
export async function datasetFromTemplate(page: Page, templateKey: string): Promise<string> {
  await page.goto("/optimize");
  await page.getByTestId(`use-template-${templateKey}`).click();
  await expect(page).toHaveURL(/\/optimize\?dataset=/);
  await expect(page.getByRole("form", { name: "Configuration de l'exécution" })).toBeVisible();
  return new URL(page.url()).searchParams.get("dataset") as string;
}

/** Fills the label, launches the run and waits for the run page to report it finished. */
export async function launchRun(page: Page, label: string): Promise<string> {
  await page.getByLabel(/Libellé/).fill(label);
  await page.getByRole("button", { name: /Lancer l'optimisation|Exécuter le scénario/ }).click();
  await expect(page).toHaveURL(/\/runs\/[^/]+\/summary$/);
  await waitForSucceeded(page);
  return page.url().split("/runs/")[1].split("/")[0];
}

export async function waitForSucceeded(page: Page): Promise<void> {
  const banner = page.getByRole("status").filter({ hasText: /Terminé|Infaisable|Échec|Délai/ });
  await expect(banner).toContainText("Terminé", { timeout: 60_000 });
}

/**
 * Saves a new dataset version whose first lot differs by a few kg, so the effective input is
 * unique and POST /runs cannot answer with a cached run from an earlier test (cache_hit).
 */
export async function makeInputUnique(request: APIRequestContext, datasetId: string): Promise<void> {
  const dataset = await (await request.get(`${API}/datasets/${datasetId}`)).json();
  const payload = dataset.current_version.payload;
  payload.harvest_lots[0].quantity_kg += 1 + (Date.now() % 997);
  const put = await request.put(`${API}/datasets/${datasetId}/payload`, {
    data: { payload, note: "e2e: unique input" },
    headers: { "If-Match": `"${dataset.current_version.version_no}"` },
  });
  expect(put.ok()).toBeTruthy();
}

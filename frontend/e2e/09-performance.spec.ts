// Phase 14 — front-end performance budgets: time until the main content of each page is usable
// (navigation + API calls + render), measured on a warmed route so dev-server compilation is not
// counted. Against the production build (`next start`) the numbers are lower still.
import { expect, test, type Page } from "@playwright/test";
import { API, unique } from "./helpers";

const BUDGET_MS = 3000;

let runId = "";

test.beforeAll(async ({ request }) => {
  const dataset = await (await request.post(`${API}/datasets`, { data: { template_key: "tunisia_wheat", name: unique("Perf") } })).json();
  const run = await (await request.post(`${API}/runs?wait=15`, { data: { dataset_id: dataset.dataset.id, label: unique("Perf run"), use_cache: false } })).json();
  expect(run.status).toBe("succeeded");
  runId = run.id;
});

const CASES: { name: string; url: () => string; ready: (page: Page) => ReturnType<Page["getByRole"]> }[] = [
  { name: "dashboard", url: () => "/dashboard", ready: (p) => p.getByLabel("Indicateurs exécutifs") },
  { name: "run summary", url: () => `/runs/${runId}/summary`, ready: (p) => p.getByRole("status").filter({ hasText: "Terminé" }) },
  { name: "allocation", url: () => `/runs/${runId}/allocation`, ready: (p) => p.getByRole("table").first() },
  { name: "explanation", url: () => `/runs/${runId}/explain`, ready: (p) => p.getByRole("region", { name: "Décisions" }) },
  { name: "analytics", url: () => `/analytics?run=${runId}`, ready: (p) => p.getByRole("table", { name: "Revenus par acheteur" }) },
  { name: "datasets", url: () => "/datasets", ready: (p) => p.getByRole("table", { name: "Jeux de données" }) },
];

for (const c of CASES) {
  test(`${c.name} is usable within ${BUDGET_MS} ms`, async ({ page }) => {
    const errors: string[] = [];
    page.on("pageerror", (e) => errors.push(String(e)));
    await page.goto(c.url());
    await expect(c.ready(page)).toBeVisible({ timeout: 60_000 }); // warm-up (compilation, caches)

    const started = Date.now();
    await page.goto(c.url());
    await expect(c.ready(page)).toBeVisible();
    const elapsed = Date.now() - started;
    test.info().annotations.push({ type: "time-to-usable", description: `${elapsed} ms` });
    expect(elapsed, `${c.name}: ${elapsed} ms`).toBeLessThan(BUDGET_MS);
    expect(errors).toEqual([]);
  });
}

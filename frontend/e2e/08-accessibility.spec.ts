// Phase 14 — accessibility audit: axe (WCAG 2.1 A/AA, contrast included) on every main page in both
// themes, no horizontal scrolling from 375 to 1440 px, and full keyboard navigation.
import AxeBuilder from "@axe-core/playwright";
import { expect, test, type Page } from "@playwright/test";
import { API, unique } from "./helpers";

const VIEWPORTS = [
  { width: 375, height: 812 },
  { width: 768, height: 1024 },
  { width: 1440, height: 900 },
] as const;

let runId = "";
let datasetId = "";

test.beforeAll(async ({ request }) => {
  const dataset = await (await request.post(`${API}/datasets`, { data: { template_key: "tunisia_olives", name: unique("A11y — jeu de données au nom volontairement long pour tester les petits écrans") } })).json();
  datasetId = dataset.dataset.id;
  const run = await (await request.post(`${API}/runs?wait=15`, { data: { dataset_id: datasetId, label: unique("A11y run"), use_cache: false } })).json();
  runId = run.id;
  expect(run.status).toBe("succeeded");
});

function pages(): string[] {
  return [
    "/dashboard",
    "/datasets",
    `/datasets/${datasetId}`,
    `/optimize?dataset=${datasetId}`,
    "/runs",
    `/runs/${runId}/summary`,
    `/runs/${runId}/allocation`,
    `/runs/${runId}/explain`,
    `/runs/${runId}/network`,
    "/scenarios",
    "/compare",
    `/analytics?run=${runId}`,
    "/reports",
    "/reports/new",
    "/copilot",
    "/settings",
  ];
}

async function setTheme(page: Page, theme: "light" | "dark") {
  await page.addInitScript((t) => window.localStorage.setItem("h2v.theme", t), theme);
}

async function settle(page: Page) {
  await expect(page.locator("main [role=status]").filter({ hasText: /Chargement/ })).toHaveCount(0, { timeout: 30_000 });
}

for (const theme of ["dark", "light"] as const) {
  test(`axe: no serious or critical violation (${theme} theme)`, async ({ page }) => {
    test.setTimeout(240_000);
    await setTheme(page, theme);
    const failures: string[] = [];
    for (const url of pages()) {
      await page.goto(url);
      await settle(page);
      const results = await new AxeBuilder({ page }).withTags(["wcag2a", "wcag2aa", "wcag21a", "wcag21aa"]).exclude(".react-flow__attribution").analyze();
      for (const v of results.violations.filter((x) => x.impact === "serious" || x.impact === "critical")) {
        const nodes = v.nodes.slice(0, 3).map((n) => `${n.target.join(" ")} :: ${n.failureSummary?.split("\n").slice(1, 2).join(" ") ?? ""}`);
        failures.push(`${url} [${v.id}] ${v.help} — ${nodes.join(" | ")}`);
      }
    }
    expect(failures, failures.join("\n")).toEqual([]);
  });
}

test("responsive: no horizontal scrolling from 375 to 1440 px", async ({ page }) => {
  test.setTimeout(240_000);
  const overflow: string[] = [];
  for (const viewport of VIEWPORTS) {
    await page.setViewportSize(viewport);
    for (const url of pages()) {
      await page.goto(url);
      await settle(page);
      const width = await page.evaluate(() => document.documentElement.scrollWidth - window.innerWidth);
      if (width > 1) overflow.push(`${viewport.width}px ${url}: +${width}px`);
    }
  }
  expect(overflow, overflow.join("\n")).toEqual([]);
});

test("keyboard: skip link, sidebar, command palette and drawer without a mouse", async ({ page }) => {
  await page.goto("/dashboard");
  await page.keyboard.press("Tab");
  const skip = page.getByRole("link", { name: "Aller au contenu" });
  await expect(skip).toBeFocused();
  await page.keyboard.press("Enter");
  await expect(page.locator("#main")).toBeFocused();

  // Ctrl+K -> type -> Enter navigates.
  await page.keyboard.press("Control+k");
  await page.keyboard.type("Rapports");
  await page.keyboard.press("Enter");
  await expect(page).toHaveURL(/\/reports$/);

  // Every focusable control of the sidebar is reachable with Tab and has a visible focus ring.
  await page.goto("/dashboard");
  for (let i = 0; i < 15; i++) {
    await page.keyboard.press("Tab");
    const focus = await page.evaluate(() => {
      const el = document.activeElement as HTMLElement | null;
      if (!el || el === document.body) return { visible: false, what: "body" };
      const style = getComputedStyle(el);
      const visible = (style.outlineStyle !== "none" && style.outlineWidth !== "0px") || style.boxShadow !== "none";
      return { visible, what: el.outerHTML.slice(0, 120) };
    });
    expect(focus.visible, `no visible focus on ${focus.what}`).toBe(true);
  }

  // The Copilot drawer opens and closes with the keyboard.
  await page.getByRole("button", { name: "Copilot", exact: true }).focus();
  await page.keyboard.press("Enter");
  await expect(page.getByRole("dialog", { name: "Copilot" })).toBeVisible();
  await page.keyboard.press("Escape");
  await expect(page.getByRole("dialog", { name: "Copilot" })).toBeHidden();
});

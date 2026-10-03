// Phase 11 — E2E n°4 Copilot: question -> verified answer; request -> proposal -> confirm -> scenario.
// The backend runs LLM_PROVIDER=mock with e2e/fixtures/copilot-script.json (scripted tool calls).
import { expect, test } from "@playwright/test";
import { API, datasetFromTemplate, launchRun, unique } from "./helpers";

test("E2E n°4 Copilot: verified figures, and no change without confirmation", async ({ page }) => {
  await datasetFromTemplate(page, "tunisia_olives");
  const runId = await launchRun(page, unique("Copilot olives"));
  const result = await (await page.request.get(`${API}/runs/${runId}/result`)).json();
  const scenariosBefore = (await (await page.request.get(`${API}/scenarios`)).json()).total as number;

  await page.getByRole("button", { name: "Copilot", exact: true }).click();
  const drawer = page.getByRole("dialog", { name: "Copilot" });
  const input = drawer.getByRole("textbox", { name: "Message au Copilot" });
  const log = drawer.getByRole("log", { name: "Messages du Copilot" });

  // 1. A question: the figure is rendered by the backend from the run (not by the model).
  await input.fill("Quel est le profit réalisé de ce plan ?");
  await input.press("Enter");
  const answer = log.locator('[data-role="assistant"]').first();
  await expect(answer).toContainText("Le profit réalisé de ce plan est de");
  await expect(answer).toContainText("Chiffres vérifiés");
  const expected = Math.round(result.kpis.realized_profit).toLocaleString("fr-FR").replace(/\s/g, "\\s");
  await expect(answer).toContainText(new RegExp(`${expected}\\sTND`));
  await expect(answer.locator("mark[data-unverified]")).toHaveCount(0);

  // 2. A request: only a pending proposal; nothing is created until confirmation.
  await input.fill("Crée un scénario où le prix de tous les acheteurs baisse de 10 %");
  await input.press("Enter");
  const proposal = log.getByRole("article", { name: "Proposition : Nouveau scénario" });
  await expect(proposal).toContainText("Copilot prix -10 %");
  await expect(proposal).toContainText("À confirmer");
  expect((await (await page.request.get(`${API}/scenarios`)).json()).total).toBe(scenariosBefore);

  await proposal.getByRole("button", { name: "Confirmer" }).click();
  await expect(proposal).toContainText("Exécutée");
  expect((await (await page.request.get(`${API}/scenarios`)).json()).total).toBe(scenariosBefore + 1);
  await proposal.getByRole("link", { name: /Ouvrir le scénario/ }).click();
  await expect(page.getByRole("heading", { name: "Copilot prix -10 %" })).toBeVisible();
});

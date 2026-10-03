// Milestone M1: end-to-end demonstration on the 5 templates.
import { expect, test } from "@playwright/test";
import { datasetFromTemplate, launchRun, unique } from "./helpers";

const TEMPLATES = ["tunisia_citrus", "tunisia_dates", "tunisia_olives", "tunisia_tomatoes", "tunisia_wheat"];

for (const key of TEMPLATES) {
  test(`M1 demo on ${key}: data -> run -> summary and allocation`, async ({ page }) => {
    await datasetFromTemplate(page, key);
    await expect(page.getByLabel(/Horizon/)).not.toHaveValue("");
    await launchRun(page, unique(`M1 ${key}`));
    await expect(page.getByLabel("Indicateurs clés")).toContainText("Profit réalisé");
    await expect(page.getByRole("img", { name: /Flux de la récolte/ })).toBeVisible();
    await page.getByRole("link", { name: "Allocation", exact: true }).click();
    await expect(page.getByRole("table", { name: "Matrice d'allocation acheteur × jour" })).toBeVisible();
  });
}

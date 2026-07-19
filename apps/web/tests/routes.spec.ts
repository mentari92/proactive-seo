import { expect, test } from "@playwright/test";
import { ROUTES } from "../lib/routes";

for (const route of ROUTES) {
  test(`${route} renders without a runtime error`, async ({ page }) => {
    await page.goto(route);
    await expect(page.locator("body")).not.toContainText("Application error");
    await expect(page.locator("h1, h2").first()).toBeVisible();
  });
}

test("command palette is keyboard accessible", async ({ page }) => {
  await page.goto("/overview");
  await page.keyboard.press("Control+K");
  await expect(page.getByRole("dialog", { name: "Command palette" })).toBeVisible();
  await page.keyboard.press("Escape");
  await expect(page.getByRole("dialog", { name: "Command palette" })).toBeHidden();
});


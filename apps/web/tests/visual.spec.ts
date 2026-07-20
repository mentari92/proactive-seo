import { expect, test } from "@playwright/test";

test("overview light-mode visual", async ({ page }) => {
  await page.goto("/overview");
  await expect(page).toHaveScreenshot("overview-light.png", {
    fullPage: true,
    animations: "disabled",
    maxDiffPixelRatio: 0.02
  });
});

test("overview dark-mode visual", async ({ page }) => {
  await page.goto("/overview");
  await page.getByRole("button", { name: "Toggle dark mode" }).click();
  await expect(page).toHaveScreenshot("overview-dark.png", {
    fullPage: true,
    animations: "disabled",
    maxDiffPixelRatio: 0.02
  });
});

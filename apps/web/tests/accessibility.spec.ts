import AxeBuilder from "@axe-core/playwright";
import { expect, test } from "@playwright/test";

for (const route of ["/login", "/overview", "/agents", "/campaigns", "/content/editor/demo", "/settings/profile"]) {
  test(`${route} has no serious accessibility violations`, async ({ page }) => {
    await page.goto(route);
    const results = await new AxeBuilder({ page }).analyze();
    const violations = results.violations.filter((item) => item.impact === "serious" || item.impact === "critical");
    const summary = violations.map((item) => ({
      id: item.id,
      nodes: item.nodes.map((node) => node.target.join(" "))
    }));
    expect(summary).toEqual([]);
  });
}

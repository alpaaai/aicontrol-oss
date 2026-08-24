import { test, expect } from "@playwright/test";

test.beforeEach(async ({ page }) => {
  await page.goto("/login");
  await page.evaluate(() => {
    sessionStorage.setItem(
      "ac_auth",
      JSON.stringify({
        email: "admin@aicontrol.dev",
        role: "admin",
        token: "test-token",
      })
    );
  });
});

test("paid destinations are absent from the nav on a community install", async ({ page }) => {
  await page.route("**/license/features", (route) =>
    route.fulfill({
      json: { tier: "free", features: { nl_authoring: false, simulation: false, hitl: false, compliance_reports: false } },
    }),
  );
  await page.goto("/overview");
  const nav = page.getByRole("navigation");
  await expect(nav.getByRole("link", { name: "Reviews" })).toHaveCount(0);
  await expect(nav.getByRole("link", { name: "Reports" })).toHaveCount(0);
});

test("review queue page shows enterprise lock overlay", async ({ page }) => {
  await page.goto("/reviews");
  await expect(page.getByText("Review Queue — Enterprise Feature")).toBeVisible();
});


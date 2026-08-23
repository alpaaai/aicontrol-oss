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

test("locked nav items are visible in their sections", async ({ page }) => {
  await page.goto("/overview");

  // Open Manual Reviews — Review queue (locked) should appear
  await page.getByText("Manual Reviews", { exact: true }).click();
  await expect(page.getByText("Review queue", { exact: true })).toBeVisible();

  // Open Reports — Compliance (locked) should appear
  await page.getByText("Reports", { exact: true }).click();
  await expect(page.getByText("Compliance", { exact: true })).toBeVisible();
});

test("review queue page shows enterprise lock overlay", async ({ page }) => {
  await page.goto("/reviews");
  await expect(page.getByText("Review Queue — Enterprise Feature")).toBeVisible();
});


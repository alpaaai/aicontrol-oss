import { test, expect } from "@playwright/test";

test.beforeEach(async ({ page }) => {
  await page.goto("/login");
  await page.evaluate(() => {
    sessionStorage.setItem(
      "ac_auth",
      JSON.stringify({ email: "admin@aicontrol.dev", role: "admin", token: "test-token" })
    );
  });
});

test("health page shows enterprise lock", async ({ page }) => {
  await page.goto("/health");
  await expect(page.getByRole("heading", { name: "System Health" })).toBeVisible();
  await expect(page.getByText("OPA Health Monitor — Enterprise")).toBeVisible();
});

test("activity log page is accessible (community)", async ({ page }) => {
  await page.route("http://localhost:8001/dashboard/activity-log*", (route) =>
    route.fulfill({
      status: 200,
      body: JSON.stringify({ logs: [], total: 0 }),
    })
  );
  await page.goto("/activity-log");
  await expect(page.getByRole("heading", { name: "Activity Log" })).toBeVisible();
  await expect(page.getByText("who changed what")).toBeVisible();
});

import { test, expect } from "@playwright/test";

test("login screen shows the real license tier, not a hardcoded enterprise claim", async ({ page }) => {
  await page.route("**/license-info", (route) =>
    route.fulfill({
      json: { plan: "business", company: "Acme", is_enterprise: false, is_business: true, expires_at: null },
    }),
  );
  await page.goto("/login");
  await expect(page.getByText("Secured by AIControl · Business tier")).toBeVisible();
  await expect(page.getByText("Enterprise tier")).toHaveCount(0);
});

test("login screen falls back to a plan-agnostic footer if license-info fails", async ({ page }) => {
  await page.route("**/license-info", (route) => route.fulfill({ status: 500, body: "error" }));
  await page.goto("/login");
  await expect(page.getByText("Secured by AIControl", { exact: true })).toBeVisible();
});

test("setup screen shows community tier on a fresh install", async ({ page }) => {
  await page.route("**/setup/status", (route) =>
    route.fulfill({ status: 200, body: JSON.stringify({ setup_required: true }) }),
  );
  await page.route("**/license-info", (route) =>
    route.fulfill({
      json: { plan: "community", company: null, is_enterprise: false, is_business: false, expires_at: null },
    }),
  );
  await page.goto("/setup");
  await expect(page.getByText("Secured by AIControl · Community tier")).toBeVisible();
});

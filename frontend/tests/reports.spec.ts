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

test("reports page shows enterprise lock for community", async ({ page }) => {
  await page.goto("/reports");
  await expect(page.getByRole("heading", { name: "Compliance Reports" })).toBeVisible();
  await expect(page.getByText("Compliance Reports — Enterprise")).toBeVisible();
});

test("reports page shows a reactivate prompt for an unreachable enterprise org, not the lock or content", async ({ page }) => {
  await page.route("**/license-info", (route) =>
    route.fulfill({
      json: { plan: "enterprise", company: "Acme", is_enterprise: true, is_business: true, expires_at: null },
    }),
  );
  await page.route("**/license/features", (route) =>
    route.fulfill({
      json: { tier: "enterprise", features: { nl_authoring: true, simulation: true, hitl: true, compliance_reports: true }, license_status: "unreachable" },
    }),
  );
  await page.goto("/reports");
  await expect(page.getByText(/Reactivate your plan/i)).toBeVisible();
  await expect(page.getByText("Compliance Reports — Enterprise")).not.toBeVisible();
});

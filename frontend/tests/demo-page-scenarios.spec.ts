import { test, expect } from "@playwright/test";

test.beforeEach(async ({ page }) => {
  await page.route("**/org-settings", (route) =>
    route.fulfill({ status: 200, body: JSON.stringify({ org_name: "Acme", timezone: "UTC" }) })
  );
  await page.route("**/license/features", (route) =>
    route.fulfill({
      status: 200,
      body: JSON.stringify({
        tier: "enterprise",
        features: { nl_authoring: true, simulation: true, hitl: true, compliance_reports: true },
      }),
    })
  );
  await page.route("**/dashboard/summary*", (route) =>
    route.fulfill({
      status: 200,
      body: JSON.stringify({
        intercepts_today: 0, intercepts_7d: 0, intercepts_30d: 0,
        allow_count_today: 0, deny_count_today: 0, review_count_today: 0,
        deny_rate_today: 0, active_sessions: 0, pending_reviews: 0,
        active_agents: 0, active_policies: 0, top_tools: [], decisions_by_hour: [],
      }),
    })
  );
  await page.goto("/login");
  await page.evaluate(() => {
    sessionStorage.setItem(
      "ac_auth",
      JSON.stringify({ email: "admin@aicontrol.dev", role: "admin", token: "demo-token" })
    );
  });
});

test("demo page lists all 8 approved industries fetched from the API", async ({ page }) => {
  await page.goto("/demo");
  const select = page.locator("select").first();
  await expect(select.locator("option")).toHaveCount(9);
  const options = await select.locator("option").allTextContents();
  const industries = options.filter((o) => o !== "Select industry…");
  expect(industries.sort()).toEqual(
    [
      "Banking / Lending",
      "Customer Support",
      "Healthcare",
      "ITSM",
      "Insurance",
      "Lucid Motors",
      "RevOps",
      "Toyota Motor Europe",
    ].sort()
  );
});

test("selecting a scenario shows its incident headline fetched from the API detail endpoint", async ({ page }) => {
  await page.goto("/demo");
  const select = page.locator("select").first();
  await expect(select.locator("option")).toHaveCount(9);
  await select.selectOption({ label: "Insurance" });
  await expect(page.getByText(/claims processing agent|commercial property claim/i)).toBeVisible();
});

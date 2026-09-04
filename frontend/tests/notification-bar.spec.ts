import { test, expect } from "@playwright/test";

test.beforeEach(async ({ page }) => {
  await page.goto("/login");
  await page.evaluate(() => {
    sessionStorage.setItem(
      "ac_auth",
      JSON.stringify({ email: "admin@aicontrol.dev", role: "admin", token: "test-token" })
    );
  });
  await page.route("**/license-info", (route) =>
    route.fulfill({
      json: { plan: "enterprise", company: "Acme", is_enterprise: true, is_business: true, expires_at: null },
    }),
  );
  await page.route("**/dashboard/summary*", (route) =>
    route.fulfill({ json: { pending_reviews: 0, deny_rate_today: 0 } }),
  );
  await page.route(/\/warnings\?/, (route) =>
    route.fulfill({
      json: [{
        id: "w1",
        warning_type: "UNGOVERNED_TOOL",
        agent_id: "a1",
        agent_name: "billing-agent",
        policy_id: null,
        policy_name: null,
        tool_name: "send_wire_transfer",
        message: "drift",
        is_active: true,
        created_at: new Date().toISOString(),
        resolved_at: null,
      }],
    }),
  );
});

test("clicking the drift warning notification navigates to /drift", async ({ page }) => {
  await page.goto("/overview");
  const link = page.getByRole("link", { name: /active policy drift warning/i });
  await expect(link).toBeVisible();
  await link.click();
  await expect(page).toHaveURL(/\/drift$/);
});

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

test("audit log timestamps use org timezone", async ({ page }) => {
  await page.route("**/org-settings", (route) =>
    route.fulfill({
      status: 200,
      body: JSON.stringify({ org_name: "Acme", timezone: "America/New_York" }),
    })
  );
  await page.route("**/audit-events*", (route) =>
    route.fulfill({
      status: 200,
      body: JSON.stringify({
        events: [
          {
            id: "1",
            agent_name: "test-agent",
            tool_name: "bash",
            decision: "allow",
            created_at: "2026-01-15T18:00:00Z",
            session_id: "s1",
            duration_ms: 10,
          },
        ],
        total: 1,
        limit: 50,
        offset: 0,
      }),
    })
  );
  await page.goto("/audit-log");
  // 2026-01-15T18:00:00Z in America/New_York is Jan 15, 13:00
  await expect(page.getByText(/Jan 15.*13:00/)).toBeVisible({ timeout: 10000 });
});


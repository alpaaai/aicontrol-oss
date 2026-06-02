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

test("activity log timestamps use org timezone", async ({ page }) => {
  await page.route("**/org-settings", (route) =>
    route.fulfill({
      status: 200,
      body: JSON.stringify({ org_name: "Acme", timezone: "Europe/London" }),
    })
  );
  await page.route("**/dashboard/activity-log*", (route) =>
    route.fulfill({
      status: 200,
      body: JSON.stringify({
        logs: [
          {
            id: "1",
            user_email: "admin@acme.com",
            action: "policy.create",
            resource_type: "policy",
            resource_id: null,
            before_state: null,
            after_state: null,
            ip_address: null,
            created_at: "2026-01-15T12:00:00Z",
          },
        ],
        total: 1,
      }),
    })
  );
  await page.goto("/activity-log");
  // 2026-01-15T12:00:00Z in Europe/London is Jan 15, 12:00
  await expect(page.getByText(/Jan 15.*12:00/)).toBeVisible({ timeout: 10000 });
});

import { test, expect } from "@playwright/test";

const MOCK_SUMMARY = {
  intercepts_today: 42,
  intercepts_7d: 300,
  intercepts_30d: 1200,
  allow_count_today: 35,
  deny_count_today: 5,
  review_count_today: 2,
  deny_rate_today: 11.9,
  active_sessions: 3,
  pending_reviews: 2,
  active_agents: 4,
  active_policies: 7,
  top_tools: [],
  decisions_by_hour: [],
};

const MOCK_AUDIT = {
  events: [],
  total: 0,
  limit: 20,
  offset: 0,
};

test.beforeEach(async ({ page }) => {
  await page.route("**/dashboard/summary", (route) =>
    route.fulfill({ status: 200, body: JSON.stringify(MOCK_SUMMARY) })
  );
  await page.route("**/audit-events**", (route) =>
    route.fulfill({ status: 200, body: JSON.stringify(MOCK_AUDIT) })
  );
  await page.goto("/login");
  await page.evaluate(() => {
    sessionStorage.setItem(
      "ac_auth",
      JSON.stringify({ email: "admin@aicontrol.dev", role: "admin", token: "test-token" })
    );
  });
});

test("overview renders stat cards", async ({ page }) => {
  await page.goto("/overview");
  await expect(page.getByText("Intercepts today")).toBeVisible();
  await expect(page.getByText("Deny rate")).toBeVisible();
  await expect(page.getByText("Live intercepts")).toBeVisible();
});

import { expect, test } from "@playwright/test";

function summaryFor(window: string) {
  return {
    window,
    granularity: window === "30d" ? "day" : "hour",
    intercepts_today: 10, intercepts_7d: 300, intercepts_30d: 1200,
    allow_count_today: 8, deny_count_today: 1, review_count_today: 1,
    deny_rate_today: 10, active_sessions: 2, pending_reviews: 1,
    active_agents: 4, active_policies: 7,
    top_tools: [{ tool: "release_payment", count: 12 }],
    decisions_by_hour: [{ hour: "2026-08-24T10:00:00", decision: "allow", count: 5 }],
    active_warnings: 0, overdue_reviews: 0, top_denied_tool: null, high_risk_sessions: 0,
  };
}

test.beforeEach(async ({ page }) => {
  await page.route("**/dashboard/summary*", (route) => {
    const url = new URL(route.request().url());
    const window = url.searchParams.get("window") ?? "7d";
    return route.fulfill({ json: summaryFor(window) });
  });
  await page.route("**/metrics*", (route) => {
    const type = route.request().resourceType();
    return type === "xhr" || type === "fetch"
      ? route.fulfill({ json: { policy_hit_rate: 12, avg_review_seconds: 300, top_agents_by_deny_rate: [] } })
      : route.continue();
  });
  await page.goto("/login");
  await page.evaluate(() => {
    sessionStorage.setItem(
      "ac_auth",
      JSON.stringify({ email: "admin@aicontrol.dev", role: "admin", token: "test-token" }),
    );
  });
});

test("the window selector defaults to 7 days", async ({ page }) => {
  await page.goto("/metrics");
  await expect(page.getByTestId("metrics-window-select")).toHaveValue("7d");
  await expect(page.getByText("Top tools — last 7d")).toBeVisible();
});

test("switching the window re-fetches summary with the new window", async ({ page }) => {
  let lastRequestedWindow = "";
  await page.route("**/dashboard/summary*", (route) => {
    const url = new URL(route.request().url());
    lastRequestedWindow = url.searchParams.get("window") ?? "";
    return route.fulfill({ json: summaryFor(lastRequestedWindow) });
  });
  await page.goto("/metrics");
  await page.getByTestId("metrics-window-select").selectOption("24h");
  await expect(page.getByText("Top tools — last 24h")).toBeVisible();
  expect(lastRequestedWindow).toBe("24h");
});

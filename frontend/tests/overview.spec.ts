import { expect, test } from "@playwright/test";

test.beforeEach(async ({ page }) => {
  await page.route("**/license/features", (route) =>
    route.fulfill({
      json: { tier: "enterprise", features: { nl_authoring: true, simulation: true, hitl: true, compliance_reports: true } },
    }),
  );
  await page.route("**/dashboard/outcomes*", (route) =>
    route.fulfill({
      json: {
        window: "7d",
        workflows: [
          {
            workflow: "claims_intake",
            agents: 4,
            calls: 412,
            held_for_approval: 3,
            denied: 5,
            outcomes: [
              { kind: "payment_held", count: 3 },
              { kind: "record_access_denied", count: 5 },
            ],
          },
        ],
      },
    }),
  );
  await page.route("**/audit-events*", (route) =>
    route.fulfill({ json: { events: [], total: 0 } }),
  );
  await page.goto("/login");
  await page.evaluate(() => {
    sessionStorage.setItem(
      "ac_auth",
      JSON.stringify({ email: "admin@aicontrol.dev", role: "admin", token: "test-token" }),
    );
  });
});

test("the first viewport is prose, not a tile grid", async ({ page }) => {
  await page.goto("/");
  const summary = page.getByTestId("outcome-summary");
  await expect(summary).toBeVisible();
  const text = (await summary.textContent()) ?? "";
  expect(text.length).toBeGreaterThan(60);
  await expect(page.getByTestId("stat-tile")).toHaveCount(0);
});

test("outcomes are phrased in business terms", async ({ page }) => {
  await page.goto("/");
  const summary = page.getByTestId("outcome-summary");
  await expect(summary).toContainText(/held for approval|denied|blocked/);
});

test("outcomes are grouped by workflow", async ({ page }) => {
  await page.goto("/");
  await expect(page.getByTestId("workflow-group").first()).toBeVisible();
});

test("the decision feed sits beneath the summary", async ({ page }) => {
  await page.goto("/");
  const summaryBox = await page.getByTestId("outcome-summary").boundingBox();
  const feedBox = await page.getByTestId("decision-feed").boundingBox();
  expect(feedBox!.y).toBeGreaterThan(summaryBox!.y);
});

test("the empty state is an invitation", async ({ page }) => {
  await page.route("**/dashboard/outcomes*", (route) =>
    route.fulfill({ json: { window: "7d", workflows: [] } }),
  );
  await page.goto("/");
  await expect(page.getByTestId("outcome-summary")).toContainText(/No governed activity yet/i);
});

test("the decision feed scrolls rather than clipping", async ({ page }) => {
  await page.goto("/");
  const overflow = await page.getByTestId("decision-feed")
    .evaluate((el) => getComputedStyle(el).overflowY);
  expect(overflow).toBe("auto");
});

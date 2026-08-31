import { expect, test } from "@playwright/test";

const EVENTS = [
  { id: "e1", tool_name: "release_payment", decision: "review", workflow: "claims_intake",
    agent_name: "claims-adjuster", session_id: "s1", created_at: "2026-08-20T10:00:00Z",
    policy: { id: "p1", principalType: "agent", principalId: "claims-adjuster",
              actionTool: "release_payment", resourceSystem: "guidewire",
              effect: "review", condition: { numeric_conditions: { amount: { gt: 50000 } } } } },
  { id: "e2", tool_name: "read_record", decision: "allow", workflow: "claims_intake",
    agent_name: "claims-adjuster", session_id: "s1", created_at: "2026-08-20T10:01:00Z",
    policy: null },
];

test.beforeEach(async ({ page }) => {
  await page.route("**/audit-events*", (route) => route.fulfill({ json: { events: EVENTS, total: 2 } }));
  await page.goto("/login");
  await page.evaluate(() => {
    sessionStorage.setItem(
      "ac_auth",
      JSON.stringify({ email: "admin@aicontrol.dev", role: "admin", token: "test-token" }),
    );
  });
});

test("an event that fired a policy shows that policy's sentence", async ({ page }) => {
  await page.goto("/audit");
  await expect(page.getByTestId("audit-row-e1")).toContainText("release a payment");
});

test("an allowed event with no policy shows no sentence", async ({ page }) => {
  await page.goto("/audit");
  await expect(page.getByTestId("audit-row-e2")).not.toContainText("may not");
});

test("events can be grouped by workflow", async ({ page }) => {
  await page.goto("/audit");
  await page.getByTestId("group-by-workflow").click();
  await expect(page.getByTestId("workflow-group-claims_intake")).toBeVisible();
});

test("events can be grouped by session", async ({ page }) => {
  await page.goto("/audit");
  await page.getByTestId("group-by-session").click();
  await expect(page.getByTestId("session-group-s1")).toBeVisible();
});

test("an event with no workflow groups under a clear label, not the literal 'unassigned'", async ({ page }) => {
  await page.route("**/audit-events*", (route) =>
    route.fulfill({
      json: {
        events: [
          { id: "e3", tool_name: "export_records", decision: "deny", workflow: null,
            agent_name: "risk-assessor", session_id: "s2", created_at: "2026-08-20T10:02:00Z", policy: null },
        ],
        total: 1,
      },
    }),
  );
  await page.goto("/audit");
  await page.getByTestId("group-by-workflow").click();
  const group = page.getByTestId("workflow-group-unassigned");
  await expect(group).toBeVisible();
  await expect(group).toContainText("No workflow specified");
  await expect(group).not.toContainText(/^unassigned$/);
});

test("the audit table scrolls rather than clipping", async ({ page }) => {
  await page.goto("/audit");
  const overflow = await page.getByTestId("audit-table")
    .evaluate((el) => getComputedStyle(el).overflowY);
  expect(overflow).toBe("auto");
});

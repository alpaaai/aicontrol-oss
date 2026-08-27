import { expect, test } from "@playwright/test";

test.beforeEach(async ({ page }) => {
  await page.route("**/license/features", (route) =>
    route.fulfill({
      json: { tier: "enterprise", features: { nl_authoring: true, simulation: true, hitl: true, compliance_reports: true } },
    }),
  );
  await page.route("http://localhost:8001/dashboard/outcomes*", (route) =>
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
        agents: [
          {
            agent_name: "claims-processor",
            calls: 142,
            held_for_approval: 2,
            denied: 3,
          },
          {
            agent_name: "document-extractor",
            calls: 98,
            held_for_approval: 1,
            denied: 1,
          },
          {
            agent_name: "risk-assessor",
            calls: 87,
            held_for_approval: 0,
            denied: 1,
          },
          {
            agent_name: "payment-initiator",
            calls: 85,
            held_for_approval: 0,
            denied: 0,
          },
        ],
      },
    }),
  );
  await page.route("http://localhost:8001/audit-events*", (route) =>
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

test("the overview shows stat rail with totals", async ({ page }) => {
  await page.goto("/");
  await expect(page.getByText("Tool calls", { exact: true })).toBeVisible();
  await expect(page.getByText("Active agents", { exact: true })).toBeVisible();
  await expect(page.getByText("Approval Needed", { exact: true })).toBeVisible();
  await expect(page.getByText("Denied", { exact: true })).toBeVisible();
});

test("stat rail computes totals from agent data", async ({ page }) => {
  await page.goto("/");
  // Total calls: 142+98+87+85=412
  await expect(page.getByRole("heading", { level: 1, name: /412/ })).toBeVisible();
  // Active agents: 4
  await expect(page.getByText("4", { exact: true })).toBeVisible();
  // Approval needed: 2+1+0+0=3
  await expect(page.getByText("3", { exact: true })).toBeVisible();
  // Denied: 3+1+1+0=5
  await expect(page.getByText("5", { exact: true })).toBeVisible();
});

test("agent outcome table shows agent names not counts", async ({ page }) => {
  await page.goto("/");
  await expect(page.getByText("claims-processor")).toBeVisible();
  await expect(page.getByText("document-extractor")).toBeVisible();
  await expect(page.getByText("risk-assessor")).toBeVisible();
});

test("agent outcome table shows calls approval-needed and denied columns", async ({ page }) => {
  await page.goto("/");
  await expect(page.getByText("Approval Needed", { exact: true })).toBeVisible();
  // Each agent row should have its counts
  await expect(page.getByText("142")).toBeVisible(); // claims-processor calls
  await expect(page.getByText("98")).toBeVisible(); // document-extractor calls
});

test("the decision feed sits beneath the agent table", async ({ page }) => {
  await page.goto("/");
  const tableBox = await page.getByText("claims-processor").boundingBox();
  const feedBox = await page.getByTestId("decision-feed").boundingBox();
  expect(feedBox!.y).toBeGreaterThan(tableBox!.y);
});

test("the empty state is an invitation", async ({ page }) => {
  await page.route("http://localhost:8001/dashboard/outcomes*", (route) =>
    route.fulfill({ json: { window: "7d", workflows: [], agents: [] } }),
  );
  await page.goto("/");
  await expect(page.getByText(/No governed activity yet/i)).toBeVisible();
});

test("the decision feed scrolls rather than clipping", async ({ page }) => {
  await page.goto("/");
  const overflow = await page.getByTestId("decision-feed")
    .evaluate((el) => getComputedStyle(el).overflowY);
  expect(overflow).toBe("auto");
});

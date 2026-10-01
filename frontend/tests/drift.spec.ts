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

test("drift page shows enterprise lock for community", async ({ page }) => {
  await page.route("**/license-info", (route) =>
    route.fulfill({
      json: { plan: "community", company: null, is_enterprise: false, is_business: false, expires_at: null },
    }),
  );
  await page.goto("/drift");
  await expect(page.getByRole("heading", { name: "Policy drift" })).toBeVisible();
  await expect(page.getByText("Policy Drift — Enterprise Feature")).toBeVisible();
});

test("drift page shows a reactivate prompt for a canceled enterprise org, not the lock or content", async ({ page }) => {
  await page.route("**/license-info", (route) =>
    route.fulfill({
      json: { plan: "enterprise", company: "Acme", is_enterprise: true, is_business: true, expires_at: null },
    }),
  );
  await page.route("**/license/features", (route) =>
    route.fulfill({
      json: { tier: "enterprise", features: { nl_authoring: true, simulation: true, hitl: true, compliance_reports: true }, license_status: "canceled" },
    }),
  );
  await page.goto("/drift");
  await expect(page.getByText(/Reactivate your plan/i)).toBeVisible();
  await expect(page.getByText("Policy Drift — Enterprise Feature")).not.toBeVisible();
});

test("drift page lists active warnings and resolves one", async ({ page }) => {
  await page.route("**/license-info", (route) =>
    route.fulfill({
      json: { plan: "enterprise", company: "Acme", is_enterprise: true, is_business: true, expires_at: null },
    }),
  );

  let resolved = false;
  const handler = (route: import("@playwright/test").Route) => {
    const url = new URL(route.request().url());
    if (route.request().method() === "PATCH") {
      resolved = true;
      return route.fulfill({ json: { id: "w1", is_active: false } });
    }
    const isActive = url.searchParams.get("is_active") !== "false";
    if (isActive && !resolved) {
      return route.fulfill({
        json: [{
          id: "w1",
          warning_type: "UNGOVERNED_TOOL",
          agent_id: "a1",
          agent_name: "billing-agent",
          policy_id: null,
          policy_name: null,
          tool_name: "send_wire_transfer",
          message: "Agent 'billing-agent' declares tool 'send_wire_transfer' in approved_tools but no active policy references this tool name or its aliases.",
          is_active: true,
          created_at: new Date().toISOString(),
          resolved_at: null,
        }],
      });
    }
    return route.fulfill({ json: [] });
  };
  await page.route(/\/warnings\?/, handler);
  await page.route(/\/warnings\/[^/]+\/resolve$/, handler);

  await page.goto("/drift");
  await expect(page.getByText("send_wire_transfer").first()).toBeVisible();
  await expect(page.getByText("Ungoverned tool", { exact: true })).toBeVisible();
  await page.getByRole("button", { name: "Resolve", exact: true }).click();
  await expect(page.getByText("No active drift warnings")).toBeVisible();
});

test("drift page labels an unseen-tool warning distinctly from an orphaned policy", async ({ page }) => {
  await page.route("**/license-info", (route) =>
    route.fulfill({
      json: { plan: "enterprise", company: "Acme", is_enterprise: true, is_business: true, expires_at: null },
    }),
  );
  await page.route(/\/warnings\?/, (route) =>
    route.fulfill({
      json: [{
        id: "w2",
        warning_type: "UNSEEN_TOOL_NO_POLICY",
        agent_id: "a2",
        agent_name: "loan-underwriting-agent",
        policy_id: null,
        policy_name: null,
        tool_name: "fetch_credit_data_v2",
        message: "Agent 'loan-underwriting-agent' called tool 'fetch_credit_data_v2' in the last 30 days but no active policy matches it.",
        is_active: true,
        created_at: new Date().toISOString(),
        resolved_at: null,
      }],
    }),
  );

  await page.goto("/drift");
  await expect(page.getByText("fetch_credit_data_v2").first()).toBeVisible();
  await expect(page.getByText("Unseen tool", { exact: true })).toBeVisible();
  await expect(page.getByText("Orphaned policy", { exact: true })).not.toBeVisible();
});

test("drift page shows empty state with no warnings", async ({ page }) => {
  await page.route("**/license-info", (route) =>
    route.fulfill({
      json: { plan: "enterprise", company: "Acme", is_enterprise: true, is_business: true, expires_at: null },
    }),
  );
  await page.route(/\/warnings\?/, (route) => route.fulfill({ json: [] }));
  await page.goto("/drift");
  await expect(page.getByText("No active drift warnings")).toBeVisible();
});

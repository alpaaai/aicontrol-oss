import { test, expect } from "@playwright/test";

// Mirrors the 10 scenarios app/services/demo_scenario_service.py actually
// serves (see scripts/demos/scenarios or GET /demo/scenarios for the
// authoritative list) -- kept here, like every other mocked endpoint in
// this file, so the test doesn't depend on a live backend's CORS config
// matching Playwright's test port.
const SCENARIOS = [
  { id: "automotive_mcp_orchestration", industry: "Automotive — Multi-Agent MCP Orchestration (Europe)", name: "Automotive — Multi-Agent MCP Orchestration", description: "", incident_headline: "" },
  { id: "automotive_product_planning", industry: "Automotive — Product Planning (Europe)", name: "Automotive — Product Planning Intelligence Agent (Europe)", description: "", incident_headline: "" },
  { id: "ev_manufacturing", industry: "Automotive — EV Manufacturing", name: "Automotive — EV Demand Forecasting & Finance Ops Agent", description: "", incident_headline: "" },
  { id: "manufacturing_field_quality", industry: "Manufacturing — Field Quality", name: "Manufacturing — Field Quality Investigation Agent", description: "", incident_headline: "" },
  { id: "healthcare", industry: "Healthcare", name: "Healthcare — Care Coordination", description: "", incident_headline: "" },
  { id: "insurance", industry: "Insurance", name: "Insurance — Claims Settlement", description: "", incident_headline: "In 2024, an attacker embedded a hidden instruction in the loss description field of a commercial property claim." },
  { id: "itsm", industry: "ITSM", name: "ITSM — Incident Response", description: "", incident_headline: "" },
  { id: "lending", industry: "Banking / Lending", name: "Banking / Lending — Loan Underwriting", description: "", incident_headline: "" },
  { id: "revops", industry: "RevOps", name: "RevOps — CRM Automation", description: "", incident_headline: "" },
  { id: "support", industry: "Customer Support", name: "Customer Support — Ticket Resolution", description: "", incident_headline: "" },
];

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
  await page.route("**/demo/scenarios", (route) =>
    route.fulfill({ status: 200, body: JSON.stringify(SCENARIOS) })
  );
  await page.route("**/demo/scenarios/*", (route) => {
    const id = route.request().url().split("/").pop();
    const summary = SCENARIOS.find((s) => s.id === id)!;
    route.fulfill({
      status: 200,
      body: JSON.stringify({
        ...summary,
        agent_id: "a1",
        agent_name: `${id}-agent`,
        owner: "demo-team",
        workflow: id,
        approved_tools: [],
        closing_line: "",
        steps: [],
      }),
    });
  });
  await page.goto("/login");
  await page.evaluate(() => {
    sessionStorage.setItem(
      "ac_auth",
      JSON.stringify({ email: "admin@aicontrol.dev", role: "admin", token: "demo-token" })
    );
  });
});

test("demo page lists all 10 approved scenarios fetched from the API", async ({ page }) => {
  await page.goto("/demo");
  const select = page.locator("select").first();
  await expect(select.locator("option")).toHaveCount(11);
  const options = await select.locator("option").allTextContents();
  const scenarioNames = options.filter((o) => o !== "Select scenario…");
  expect(scenarioNames.sort()).toEqual(
    [
      "Automotive — EV Demand Forecasting & Finance Ops Agent",
      "Automotive — Multi-Agent MCP Orchestration",
      "Automotive — Product Planning Intelligence Agent (Europe)",
      "Banking / Lending — Loan Underwriting",
      "Customer Support — Ticket Resolution",
      "Healthcare — Care Coordination",
      "ITSM — Incident Response",
      "Insurance — Claims Settlement",
      "Manufacturing — Field Quality Investigation Agent",
      "RevOps — CRM Automation",
    ].sort()
  );
});

test("selecting a scenario shows its incident headline fetched from the API detail endpoint", async ({ page }) => {
  await page.goto("/demo");
  const select = page.locator("select").first();
  await expect(select.locator("option")).toHaveCount(11);
  await select.selectOption({ label: "Insurance — Claims Settlement" });
  await expect(page.getByText(/commercial property claim/i)).toBeVisible();
});

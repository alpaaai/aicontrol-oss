import { expect, test } from "@playwright/test";

const AGENTS = [
  { id: "a1", name: "claims-adjuster", framework: "openai_agents_sdk",
    hook: "RunHooks.on_tool_start", sdk_version: "0.2.3", workflow: "claims_intake",
    coverage_state: "governed", silent_noop_warnings: [], unresolved_systems: [] },
  { id: "a2", name: "care-coordinator", framework: "langgraph",
    hook: "BaseCallbackHandler.on_tool_start", sdk_version: "0.4.1", workflow: "care_coordination",
    coverage_state: "installed_not_firing",
    silent_noop_warnings: ["sync_tool_denial_swallowed:refund_payment"],
    unresolved_systems: ["internal_lookup"] },
];

test.beforeEach(async ({ page }) => {
  // Scoped to the API call, not the SPA route of the same name: the glob
  // "**/agents" also matches the browser's document navigation to /agents.
  await page.route("**/agents", (route) =>
    route.request().resourceType() === "document"
      ? route.continue()
      : route.fulfill({ json: AGENTS }),
  );
  await page.goto("/login");
  await page.evaluate(() => {
    sessionStorage.setItem(
      "ac_auth",
      JSON.stringify({ email: "admin@aicontrol.dev", role: "admin", token: "test-token" }),
    );
  });
});

test("each agent shows its framework and hook", async ({ page }) => {
  await page.goto("/agents");
  const row = page.getByTestId("agent-row-claims-adjuster");
  await expect(row).toContainText("openai_agents_sdk");
  await expect(row).toContainText("RunHooks.on_tool_start");
});

test("installed_not_firing is visually distinct from governed", async ({ page }) => {
  await page.goto("/agents");
  await expect(page.getByTestId("coverage-a2")).toContainText(/not firing|no calls/i);
  await expect(page.getByTestId("coverage-a1")).toContainText(/governed/i);
});

test("a silent-noop warning is disclosed by name", async ({ page }) => {
  await page.goto("/agents");
  await expect(page.getByTestId("agent-row-care-coordinator"))
    .toContainText("refund_payment");
});

test("unresolved systems are flagged", async ({ page }) => {
  await page.goto("/agents");
  await expect(page.getByTestId("agent-row-care-coordinator"))
    .toContainText("internal_lookup");
});

test("no engine vocabulary appears on the page", async ({ page }) => {
  await page.goto("/agents");
  const text = (await page.locator("main").textContent()) ?? "";
  for (const word of ["principal", "resource_system", "Cedar", "JSONB"]) {
    expect(text).not.toContain(word);
  }
});

test("agent detail lists the policies governing that agent as sentences", async ({ page }) => {
  await page.route("**/agents/a1/policies", (route) =>
    route.fulfill({
      json: [{ id: "p1", principalType: "agent", principalId: "claims-adjuster",
               actionTool: "release_payment", resourceSystem: "guidewire",
               effect: "review", condition: { numeric_conditions: { amount: { gt: 50000 } } } }],
    }),
  );
  await page.goto("/agents/a1");
  await expect(page.getByTestId("governing-policies")).toContainText("release a payment");
  await expect(page.getByTestId("governing-policies")).toContainText("Guidewire");
});

test("an agent with no policies gets an invitation, not a blank", async ({ page }) => {
  await page.route("**/agents/a2/policies", (route) => route.fulfill({ json: [] }));
  await page.goto("/agents/a2");
  await expect(page.getByTestId("governing-policies"))
    .toContainText(/No policies govern this agent yet/i);
});

test("the agents table scrolls rather than clipping", async ({ page }) => {
  await page.goto("/agents");
  const overflow = await page.getByTestId("agents-table")
    .evaluate((el) => getComputedStyle(el).overflowY);
  expect(overflow).toBe("auto");
});

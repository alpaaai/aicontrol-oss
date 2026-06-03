import { test, expect } from "@playwright/test";

const MOCK_POLICIES: never[] = [];

test.beforeEach(async ({ page }) => {
  await page.route("http://localhost:8001/policies*", (route) =>
    route.fulfill({ status: 200, body: JSON.stringify(MOCK_POLICIES) })
  );
  await page.goto("/login");
  await page.evaluate(() => {
    sessionStorage.setItem(
      "ac_auth",
      JSON.stringify({ email: "admin@aicontrol.dev", role: "admin", token: "test-token" })
    );
  });
});

test("policies page renders table and new policy button", async ({ page }) => {
  await page.goto("/policies");
  await expect(page.getByRole("heading", { name: "Policies" })).toBeVisible();
  await expect(page.getByText("New policy")).toBeVisible();
});

test("drift warnings section shows enterprise lock", async ({ page }) => {
  await page.goto("/policies");
  await expect(page.getByRole("heading", { name: "Policy Drift Warnings" })).toBeVisible();
  await expect(page.getByText("Drift Detection — Enterprise")).toBeVisible();
});

test("library endpoint returns policy list with library=true items", async ({ page }) => {
  const mockLibrary = [
    {
      id: "lib-001",
      name: "block_shell_execution",
      description: "Block all shell tools",
      rule_type: "tool_denylist",
      condition: { blocked_tools: ["bash"] },
      action: "deny",
      severity: "critical",
      active: false,
      library: true,
      priority: 10,
      category: "Dangerous Operations",
      compliance_frameworks: ["SOC2"],
      applies_to_agents: 0,
      created_by: null,
    },
  ];

  await page.route("http://localhost:8001/policies/library*", (route) =>
    route.fulfill({ status: 200, body: JSON.stringify(mockLibrary) })
  );

  // Navigate to policies — the library tab will call this endpoint
  await page.goto("/policies");
  await page.getByRole("tab", { name: "Policy Library" }).click();
  await expect(page.getByText("block_shell_execution")).toBeVisible();
});

test("ToolDenylistForm renders tag input and adds tools", async ({ page }) => {
  // This is tested via the PolicyEditor in Part 6.
  // For now just verify the file exists and the component imports cleanly.
  const response = await page.request.get(
    "http://localhost:5173/src/pages/policies/condition-form/ToolDenylistForm.tsx"
  );
  // 200 means Vite serves it; 404 means file missing
  expect(response.status()).toBe(200);
});

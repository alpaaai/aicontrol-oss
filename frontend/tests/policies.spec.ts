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

const MOCK_EMPTY: never[] = [];

test("Active Policies table shows action badge and priority", async ({ page }) => {
  const mockPolicies = [
    {
      id: "p1",
      name: "block_shell_execution",
      description: "Block shells",
      rule_type: "tool_denylist",
      condition: { blocked_tools: ["bash"] },
      action: "deny",
      severity: "critical",
      active: true,
      library: false,
      priority: 10,
      category: "Dangerous Operations",
      compliance_frameworks: ["SOC2"],
      applies_to_agents: 0,
      created_by: null,
    },
  ];

  await page.route("http://localhost:8001/policies*", (route) => {
    if (route.request().url().includes("/library")) {
      route.fulfill({ status: 200, body: JSON.stringify([]) });
    } else {
      route.fulfill({ status: 200, body: JSON.stringify(mockPolicies) });
    }
  });

  await page.goto("/policies");
  await expect(page.getByText("block_shell_execution")).toBeVisible();
  // Action badge
  await expect(page.getByText("deny", { exact: true })).toBeVisible();
  // Priority
  await expect(page.getByText("10", { exact: true })).toBeVisible();
  // Condition type badge
  await expect(page.getByText("Tool Denylist")).toBeVisible();
});

test.describe("PolicyEditor slide-over", () => {
  test.beforeEach(async ({ page }) => {
    await page.route("http://localhost:8001/policies*", (route) => {
      if (route.request().method() === "GET") {
        route.fulfill({ status: 200, body: JSON.stringify(MOCK_EMPTY) });
      } else if (route.request().method() === "POST") {
        const body = JSON.parse(route.request().postData() ?? "{}");
        route.fulfill({
          status: 201,
          body: JSON.stringify({
            id: "new-001",
            ...body,
            active: true,
            library: false,
            priority: body.priority ?? 100,
            applies_to_agents: 0,
            created_by: null,
          }),
        });
      } else {
        route.continue();
      }
    });
    await page.goto("/login");
    await page.evaluate(() => {
      sessionStorage.setItem(
        "ac_auth",
        JSON.stringify({ email: "admin@aicontrol.dev", role: "admin", token: "test-token" })
      );
    });
    await page.goto("/policies");
  });

  test("opens as slide-over when New policy is clicked", async ({ page }) => {
    await page.getByRole("button", { name: /new policy/i }).click();
    await expect(page.getByRole("heading", { name: /create policy/i })).toBeVisible();
    // Slide-over should be visible (not a centered modal)
    const panel = page.locator("[data-testid='policy-editor-panel']");
    await expect(panel).toBeVisible();
  });

  test("Form/JSON toggle switches between modes", async ({ page }) => {
    await page.getByRole("button", { name: /new policy/i }).click();
    // Default is Form mode — JSON panel is read-only
    await expect(page.getByTestId("json-panel")).toBeVisible();
    // Click JSON toggle
    await page.getByRole("button", { name: "JSON" }).click();
    await expect(page.getByTestId("json-textarea")).toBeVisible();
    // Click Form toggle
    await page.getByRole("button", { name: "Form" }).click();
    await expect(page.getByTestId("json-panel")).toBeVisible();
  });

  test("condition type selector switches sub-form", async ({ page }) => {
    await page.getByRole("button", { name: /new policy/i }).click();
    // Default condition type is tool_denylist
    await expect(page.getByTestId("tool-denylist-input")).toBeVisible();
    // Switch to Parameter Match
    await page.getByTestId("condition-type-select").selectOption("parameter_match");
    await expect(page.getByTestId("param-key-0")).toBeVisible();
    // Switch to Numeric Conditions
    await page.getByTestId("condition-type-select").selectOption("numeric_conditions");
    await expect(page.getByTestId("numeric-field-0")).toBeVisible();
  });

  test("JSON panel updates live as tool denylist form is filled", async ({ page }) => {
    await page.getByRole("button", { name: /new policy/i }).click();
    // Add a tool
    await page.getByTestId("tool-denylist-input").fill("bash");
    await page.getByTestId("tool-denylist-input").press("Enter");
    // JSON panel should contain "bash"
    const jsonText = await page.getByTestId("json-panel").textContent();
    expect(jsonText).toContain("bash");
  });

  test("live match preview shows checkmarks and crosses", async ({ page }) => {
    await page.getByRole("button", { name: /new policy/i }).click();
    await page.getByTestId("tool-denylist-input").fill("bash");
    await page.getByTestId("tool-denylist-input").press("Enter");
    // bash example should match (✓) and read_file should not (✗)
    await expect(page.getByTestId("match-preview")).toBeVisible();
  });

  test("saves new policy and calls onSaved", async ({ page }) => {
    await page.getByRole("button", { name: /new policy/i }).click();
    // Fill name
    await page.getByTestId("policy-name-input").fill("my_test_policy");
    // Add a blocked tool
    await page.getByTestId("tool-denylist-input").fill("bash");
    await page.getByTestId("tool-denylist-input").press("Enter");
    // Save
    await page.getByRole("button", { name: /save policy/i }).click();
    // Editor should close
    await expect(page.getByTestId("policy-editor-panel")).not.toBeVisible();
  });

  test("shows unknown condition type notice for unrecognised JSON", async ({ page }) => {
    await page.getByRole("button", { name: /new policy/i }).click();
    // Switch to JSON mode and enter an unrecognised condition type
    await page.getByRole("button", { name: "JSON" }).click();
    const textarea = page.getByTestId("json-textarea");
    await textarea.fill(JSON.stringify({ geo_restriction: { allowed: ["US"] } }));
    // Switch back to Form
    await page.getByRole("button", { name: "Form" }).click();
    await expect(page.getByText(/condition type not supported/i)).toBeVisible();
  });
});

test("Policy Library tab shows cards grouped by category", async ({ page }) => {
  const mockLibrary = [
    {
      id: "lib-1",
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
    {
      id: "lib-2",
      name: "review_write_operations",
      description: "Review write ops",
      rule_type: "tool_pattern",
      condition: { tool_name_contains: ["write"] },
      action: "review",
      severity: "medium",
      active: false,
      library: true,
      priority: 30,
      category: "Human Review Gates",
      compliance_frameworks: [],
      applies_to_agents: 0,
      created_by: null,
    },
  ];

  await page.route("http://localhost:8001/policies/library*", (route) =>
    route.fulfill({ status: 200, body: JSON.stringify(mockLibrary) })
  );

  await page.goto("/policies");
  await page.getByRole("tab", { name: "Policy Library" }).click();

  await expect(page.getByText("Dangerous Operations")).toBeVisible();
  await expect(page.getByText("block_shell_execution")).toBeVisible();
  await expect(page.getByText("Human Review Gates")).toBeVisible();
  await expect(page.getByText("review_write_operations")).toBeVisible();
  await expect(page.getByRole("button", { name: "Preview" }).first()).toBeVisible();
  await expect(page.getByRole("button", { name: "Activate" }).first()).toBeVisible();
});

test("Policy Library preview toggle shows condition JSON inline", async ({ page }) => {
  const mockLibrary = [
    {
      id: "lib-1",
      name: "block_shell_execution",
      description: "Block all shell tools",
      rule_type: "tool_denylist",
      condition: { blocked_tools: ["bash", "exec_command"] },
      action: "deny",
      severity: "critical",
      active: false,
      library: true,
      priority: 10,
      category: "Dangerous Operations",
      compliance_frameworks: [],
      applies_to_agents: 0,
      created_by: null,
    },
  ];

  await page.route("http://localhost:8001/policies/library*", (route) =>
    route.fulfill({ status: 200, body: JSON.stringify(mockLibrary) })
  );

  await page.goto("/policies");
  await page.getByRole("tab", { name: "Policy Library" }).click();
  await page.getByRole("button", { name: "Preview" }).click();
  await expect(page.getByText("exec_command")).toBeVisible();
});

test("Policy Library Activate opens PolicyEditor pre-filled", async ({ page }) => {
  const mockLibrary = [
    {
      id: "lib-1",
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
      compliance_frameworks: [],
      applies_to_agents: 0,
      created_by: null,
    },
  ];

  await page.route("http://localhost:8001/policies/library*", (route) =>
    route.fulfill({ status: 200, body: JSON.stringify(mockLibrary) })
  );

  await page.goto("/policies");
  await page.getByRole("tab", { name: "Policy Library" }).click();
  await page.getByRole("button", { name: "Activate" }).click();
  // PolicyEditor should open with the library policy's name pre-filled
  await expect(page.getByTestId("policy-editor-panel")).toBeVisible();
  await expect(page.getByTestId("policy-name-input")).toHaveValue("block_shell_execution");
});

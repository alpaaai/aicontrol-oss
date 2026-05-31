import { test, expect } from "@playwright/test";

const MOCK_AGENTS: never[] = [];
const MOCK_POLICIES: never[] = [];

const TWO_AGENTS = [
  {
    id: "00000000-0000-0000-0000-000000000001",
    name: "empty-tools-agent",
    owner: "team@example.com",
    status: "active",
    framework: null,
    model_version: null,
    approved_tools: [],
    approved_by: null,
  },
  {
    id: "00000000-0000-0000-0000-000000000002",
    name: "rich-tools-agent",
    owner: "team@example.com",
    status: "active",
    framework: null,
    model_version: null,
    approved_tools: ["tool_a", "tool_b", "tool_c"],
    approved_by: null,
  },
];

test.beforeEach(async ({ page }) => {
  await page.route("http://localhost:8001/agents*", (route) =>
    route.fulfill({ status: 200, body: JSON.stringify(MOCK_AGENTS) })
  );
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

test("agents page renders and detail panel is hidden by default", async ({
  page,
}) => {
  await page.goto("/agents");
  await expect(page.getByRole("heading", { name: "Agents" })).toBeVisible();
  await expect(page.getByText("Approved tools")).not.toBeVisible();
});

test("Save button does not appear when switching between agents without edits", async ({
  page,
}) => {
  await page.route("http://localhost:8001/agents*", (route) =>
    route.fulfill({ status: 200, body: JSON.stringify(TWO_AGENTS) })
  );

  await page.goto("/agents");

  // Open the empty-tools agent first
  await page.getByText("empty-tools-agent").click();
  await expect(page.getByText("Approved tools", { exact: true })).toBeVisible();
  await expect(page.getByRole("button", { name: "Save" })).not.toBeVisible();

  // Switch to rich-tools agent — Save must NOT appear (no edits were made)
  await page.getByText("rich-tools-agent").click();
  await expect(page.getByText("Approved tools", { exact: true })).toBeVisible();
  await expect(page.getByRole("button", { name: "Save" })).not.toBeVisible();
});

import { test, expect } from "@playwright/test";

const MOCK_AGENTS: never[] = [];
const MOCK_POLICIES: never[] = [];

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

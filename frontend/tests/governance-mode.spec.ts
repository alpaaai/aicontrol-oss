import { expect, test } from "@playwright/test";

test.beforeEach(async ({ page }) => {
  await page.goto("/login");
  await page.evaluate(() => {
    sessionStorage.setItem(
      "ac_auth",
      JSON.stringify({ email: "admin@aicontrol.dev", role: "admin", token: "test-token" }),
    );
  });
});

test("the agent list flags an observe-mode agent as not enforcing", async ({ page }) => {
  await page.route("**/agents", (route) =>
    route.request().resourceType() === "document"
      ? route.continue()
      : route.fulfill({
          json: [
            { id: "a1", name: "observe-agent", framework: null, hook: null, sdk_version: null,
              workflow: null, coverage_state: "unknown", silent_noop_warnings: [], unresolved_systems: [],
              governance_mode: "observe" },
            { id: "a2", name: "govern-agent", framework: null, hook: null, sdk_version: null,
              workflow: null, coverage_state: "unknown", silent_noop_warnings: [], unresolved_systems: [],
              governance_mode: "govern" },
          ],
        }),
  );
  await page.goto("/agents");
  await expect(page.getByTestId("governance-mode-a1")).toContainText(/not enforcing|observe/i);
  await expect(page.getByTestId("governance-mode-a2")).toContainText(/enforcing|govern/i);
});

test("agent detail shows governance mode and lets an admin switch it", async ({ page }) => {
  let putBody: unknown = null;
  await page.route("**/agents/a1", (route) => {
    if (route.request().resourceType() === "document") {
      return route.continue();
    }
    if (route.request().method() === "PUT") {
      putBody = route.request().postDataJSON();
      return route.fulfill({
        json: { id: "a1", name: "observe-agent", owner: "team", status: "active",
                framework: null, model_version: null, approved_tools: [], approved_by: null,
                governance_mode: "govern", hook: null, sdk_version: null, workflow: null,
                coverage_state: "unknown", silent_noop_warnings: [], unresolved_systems: [] },
      });
    }
    return route.fulfill({
      json: { id: "a1", name: "observe-agent", owner: "team", status: "active",
              framework: null, model_version: null, approved_tools: [], approved_by: null,
              governance_mode: "observe", hook: null, sdk_version: null, workflow: null,
              coverage_state: "unknown", silent_noop_warnings: [], unresolved_systems: [] },
    });
  });
  await page.route("**/agents/a1/policies", (route) => route.fulfill({ json: [] }));

  await page.goto("/agents/a1");
  await expect(page.getByText("Observe only — not enforcing")).toBeVisible();
  await page.getByRole("button", { name: /switch to govern/i }).click();
  expect(putBody).toEqual({ governance_mode: "govern" });
  await expect(page.getByRole("button", { name: /switch to observe/i })).toBeVisible();
});

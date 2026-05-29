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

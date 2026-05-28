import { test, expect } from "@playwright/test";

const MOCK_AUDIT = {
  events: [],
  total: 0,
  limit: 50,
  offset: 0,
};

test.beforeEach(async ({ page }) => {
  await page.route("**/audit-events**", (route) =>
    route.fulfill({ status: 200, body: JSON.stringify(MOCK_AUDIT) })
  );
  await page.goto("/login");
  await page.evaluate(() => {
    sessionStorage.setItem(
      "ac_auth",
      JSON.stringify({ email: "admin@aicontrol.dev", role: "admin", token: "test-token" })
    );
  });
});

test("audit log renders filter bar and table", async ({ page }) => {
  await page.goto("/audit-log");
  await expect(page.getByRole("heading", { name: "Audit Log" })).toBeVisible();
  await expect(page.locator("select")).toBeVisible();
});

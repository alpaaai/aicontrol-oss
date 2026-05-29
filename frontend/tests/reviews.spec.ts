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

test("reviews page shows enterprise lock for community", async ({ page }) => {
  await page.goto("/reviews");
  await expect(page.getByRole("heading", { name: "Review Queue" })).toBeVisible();
  await expect(page.getByText("Review Queue — Enterprise Feature")).toBeVisible();
});

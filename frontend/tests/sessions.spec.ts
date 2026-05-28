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

test("sessions page shows enterprise lock when not licensed", async ({ page }) => {
  await page.goto("/sessions");
  await expect(page.getByText("Sessions — Enterprise Feature")).toBeVisible();
});

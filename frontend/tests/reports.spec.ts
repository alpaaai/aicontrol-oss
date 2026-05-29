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

test("reports page shows enterprise lock for community", async ({ page }) => {
  await page.goto("/reports");
  await expect(page.getByRole("heading", { name: "Compliance Reports" })).toBeVisible();
  await expect(page.getByText("Compliance Reports — Enterprise")).toBeVisible();
});

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

test("tokens page renders with new token button and notice", async ({
  page,
}) => {
  await page.goto("/tokens");
  await expect(page.getByRole("heading", { name: "API Tokens" })).toBeVisible();
  await expect(page.getByText("New token")).toBeVisible();
  await expect(page.getByText("Tokens are shown once")).toBeVisible();
});

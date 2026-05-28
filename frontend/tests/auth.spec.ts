import { test, expect } from "@playwright/test";

test("redirects unauthenticated users to login", async ({ page }) => {
  await page.goto("/overview");
  await expect(page).toHaveURL(/\/login/);
});

test("login page shows email step by default", async ({ page }) => {
  await page.goto("/login");
  await expect(page.getByRole("heading", { name: "Sign in" })).toBeVisible();
  await expect(page.locator('input[type="email"]')).toBeVisible();
});

test("email step transitions to code step on success", async ({ page }) => {
  // Mock the API so the test doesn't need a live backend
  await page.route("**/auth/request-code", (route) => {
    route.fulfill({ status: 200, body: JSON.stringify({ message: "Code sent" }) });
  });
  await page.goto("/login");
  await page.fill('input[type="email"]', "admin@aicontrol.dev");
  await page.click('button[type="submit"]');
  await expect(page.getByText("Check your email")).toBeVisible({ timeout: 10000 });
});

test("root redirect sends to login when unauthenticated", async ({ page }) => {
  await page.goto("/");
  await expect(page).toHaveURL(/\/login/);
});

import { test, expect } from "@playwright/test";

test("redirects unauthenticated users to login", async ({ page }) => {
  await page.route("**/setup/status", (route) =>
    route.fulfill({ status: 200, body: JSON.stringify({ setup_required: false }) })
  );
  await page.goto("/overview");
  await expect(page).toHaveURL(/\/login/);
});

test("login page shows email and password fields", async ({ page }) => {
  await page.goto("/login");
  await expect(page.getByRole("heading", { name: "Sign in" })).toBeVisible();
  await expect(page.locator('input[type="email"]')).toBeVisible();
  await expect(page.locator('input[type="password"]')).toBeVisible();
});

test("login page has no OTP code step", async ({ page }) => {
  await page.goto("/login");
  await expect(page.getByText("Check your email")).not.toBeVisible();
  await expect(page.getByText("one-time code", { exact: false })).not.toBeVisible();
});

test("successful login stores token and redirects to overview", async ({ page }) => {
  await page.route("**/auth/login", (route) =>
    route.fulfill({
      status: 200,
      body: JSON.stringify({
        token: "fake-jwt",
        user: { id: "1", email: "admin@aicontrol.dev", full_name: "Admin", role: "admin" },
        first_login: false,
      }),
    })
  );
  await page.goto("/login");
  await page.fill('input[type="email"]', "admin@aicontrol.dev");
  await page.fill('input[type="password"]', "correctpassword");
  await page.click('button[type="submit"]');
  await expect(page).toHaveURL(/\/overview/, { timeout: 10000 });
});

test("failed login shows error message", async ({ page }) => {
  await page.route("**/auth/login", (route) =>
    route.fulfill({ status: 401, body: JSON.stringify({ detail: "Invalid email or password" }) })
  );
  await page.goto("/login");
  await page.fill('input[type="email"]', "admin@aicontrol.dev");
  await page.fill('input[type="password"]', "wrongpassword");
  await page.click('button[type="submit"]');
  await expect(page.getByText("Invalid email or password")).toBeVisible({ timeout: 5000 });
});

test("root redirect sends to login when unauthenticated", async ({ page }) => {
  await page.route("**/setup/status", (route) =>
    route.fulfill({ status: 200, body: JSON.stringify({ setup_required: false }) })
  );
  await page.goto("/");
  await expect(page).toHaveURL(/\/login/);
});

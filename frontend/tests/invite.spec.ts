import { test, expect } from "@playwright/test";

test("invite page validates token and shows set-password form", async ({ page }) => {
  await page.route("**/auth/magic-link/validate", (route) =>
    route.fulfill({
      status: 200,
      body: JSON.stringify({ valid: true, email: "alice@acme.com", full_name: "Alice" }),
    })
  );
  await page.goto("/invite?token=validtoken123");
  await expect(page.getByText("Set your password")).toBeVisible({ timeout: 10000 });
  await expect(page.getByText("alice@acme.com")).toBeVisible();
  await expect(page.getByLabel("Password", { exact: true })).toBeVisible();
  await expect(page.getByLabel("Confirm password", { exact: true })).toBeVisible();
});

test("invite page shows error for invalid token", async ({ page }) => {
  await page.route("**/auth/magic-link/validate", (route) =>
    route.fulfill({ status: 401, body: JSON.stringify({ detail: "Invalid or expired invite link" }) })
  );
  await page.goto("/invite?token=badtoken");
  await expect(page.getByText("Invalid or expired invite link")).toBeVisible({ timeout: 10000 });
});

test("invite page shows error when no token in URL", async ({ page }) => {
  await page.goto("/invite");
  await expect(page.getByText("Invalid or expired invite link")).toBeVisible({ timeout: 10000 });
});

test("set password submits and redirects to overview", async ({ page }) => {
  await page.route("**/auth/magic-link/validate", (route) =>
    route.fulfill({
      status: 200,
      body: JSON.stringify({ valid: true, email: "alice@acme.com", full_name: "Alice" }),
    })
  );
  await page.route("**/auth/set-password", (route) =>
    route.fulfill({
      status: 200,
      body: JSON.stringify({
        token: "fake-jwt",
        user: { id: "1", email: "alice@acme.com", full_name: "Alice", role: "analyst" },
      }),
    })
  );
  await page.goto("/invite?token=validtoken123");
  await page.getByLabel("Password", { exact: true }).fill("newpassword1");
  await page.getByLabel("Confirm password", { exact: true }).fill("newpassword1");
  await page.getByRole("button", { name: "Set password" }).click();
  await expect(page).toHaveURL(/\/overview/, { timeout: 10000 });
});

test("set password shows error if passwords do not match", async ({ page }) => {
  await page.route("**/auth/magic-link/validate", (route) =>
    route.fulfill({
      status: 200,
      body: JSON.stringify({ valid: true, email: "alice@acme.com", full_name: "Alice" }),
    })
  );
  await page.goto("/invite?token=validtoken123");
  await page.getByLabel("Password", { exact: true }).fill("password1234");
  await page.getByLabel("Confirm password", { exact: true }).fill("different1234");
  await page.getByRole("button", { name: "Set password" }).click();
  await expect(page.getByText("Passwords do not match")).toBeVisible();
});

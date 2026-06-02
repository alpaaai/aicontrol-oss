import { test, expect } from "@playwright/test";

test("setup page renders step 1 with org fields", async ({ page }) => {
  await page.route("**/setup/status", (route) =>
    route.fulfill({ status: 200, body: JSON.stringify({ setup_required: true }) })
  );
  await page.goto("/setup");
  await expect(page.getByText("Set up your organization")).toBeVisible();
  await expect(page.getByLabel("Organization name")).toBeVisible();
  await expect(page.getByLabel("Timezone")).toBeVisible();
});

test("setup wizard advances to step 2 after org details", async ({ page }) => {
  await page.route("**/setup/status", (route) =>
    route.fulfill({ status: 200, body: JSON.stringify({ setup_required: true }) })
  );
  await page.goto("/setup");
  await page.getByLabel("Organization name").fill("Acme Corp");
  await page.getByLabel("Timezone").selectOption("America/New_York");
  await page.getByRole("button", { name: "Continue" }).click();
  await expect(page.getByText("Create your admin account")).toBeVisible();
  await expect(page.getByLabel("Full name")).toBeVisible();
  await expect(page.getByLabel("Work email")).toBeVisible();
  await expect(page.getByLabel("Password")).toBeVisible();
});

test("setup complete submits and redirects to overview", async ({ page }) => {
  await page.route("**/setup/status", (route) =>
    route.fulfill({ status: 200, body: JSON.stringify({ setup_required: true }) })
  );
  await page.route("**/setup/complete", (route) =>
    route.fulfill({
      status: 200,
      body: JSON.stringify({
        token: "fake-jwt",
        user: { id: "1", email: "admin@acme.com", full_name: "Admin", role: "admin" },
      }),
    })
  );
  await page.goto("/setup");
  await page.getByLabel("Organization name").fill("Acme Corp");
  await page.getByLabel("Timezone").selectOption("America/New_York");
  await page.getByRole("button", { name: "Continue" }).click();
  await page.getByLabel("Full name").fill("Admin User");
  await page.getByLabel("Work email").fill("admin@acme.com");
  await page.getByLabel("Password").fill("securepassword");
  await page.getByRole("button", { name: "Finish setup" }).click();
  await expect(page).toHaveURL(/\/overview/, { timeout: 10000 });
});

test("unauthenticated visit to / redirects to /setup when setup required", async ({ page }) => {
  await page.route("**/setup/status", (route) =>
    route.fulfill({ status: 200, body: JSON.stringify({ setup_required: true }) })
  );
  await page.goto("/");
  await expect(page).toHaveURL(/\/setup/, { timeout: 10000 });
});

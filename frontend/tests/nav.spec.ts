import { test, expect } from "@playwright/test";

test.beforeEach(async ({ page }) => {
  await page.goto("/login");
  await page.evaluate(() => {
    sessionStorage.setItem(
      "ac_auth",
      JSON.stringify({
        email: "admin@aicontrol.dev",
        role: "admin",
        token: "test-token",
      })
    );
  });
});

test("sidebar renders all section labels", async ({ page }) => {
  await page.goto("/overview");
  await expect(page.getByText("Activity", { exact: true })).toBeVisible();
  await expect(page.getByText("Governance", { exact: true })).toBeVisible();
  await expect(page.getByText("Intelligence", { exact: true })).toBeVisible();
  await expect(page.getByText("Reports", { exact: true })).toBeVisible();
  await expect(page.getByText("Manual Reviews", { exact: true })).toBeVisible();
});

test("activity section auto-opens on /overview and shows sub-items", async ({ page }) => {
  await page.goto("/overview");
  await expect(page.getByRole("link", { name: "Dashboard" })).toBeVisible();
  await expect(page.getByRole("link", { name: "Agent activity" })).toBeVisible();
  await expect(page.getByRole("link", { name: "Decision metrics" })).toBeVisible();
  await expect(page.getByRole("link", { name: "Activity audit" })).toBeVisible();
});

test("clicking a section header expands it and collapses others", async ({ page }) => {
  await page.goto("/overview");
  // Activity is open; Governance is closed — its sub-items should not be visible
  await expect(page.getByRole("link", { name: "Policies" })).not.toBeVisible();
  // Click Governance to open it
  await page.getByText("Governance", { exact: true }).click();
  await expect(page.getByRole("link", { name: "Policies" })).toBeVisible();
  await expect(page.getByRole("link", { name: "Agents" })).toBeVisible();
  await expect(page.getByRole("link", { name: "API tokens" })).toBeVisible();
  // Activity sub-items should now be collapsed
  await expect(page.getByRole("link", { name: "Dashboard" })).not.toBeVisible();
});

test("user panel opens on user row click and shows Settings, Subscription, Logout", async ({ page }) => {
  await page.goto("/overview");
  await page.getByText("admin@aicontrol.dev").click();
  await expect(page.getByRole("link", { name: "Settings" })).toBeVisible();
  await expect(page.getByRole("link", { name: "Subscription" })).toBeVisible();
  await expect(page.getByRole("button", { name: "Logout" })).toBeVisible();
});

test("user panel closes after selecting an item", async ({ page }) => {
  await page.goto("/overview");
  await page.getByText("admin@aicontrol.dev").click();
  await expect(page.getByRole("link", { name: "Settings" })).toBeVisible();
  await page.getByRole("link", { name: "Settings" }).click();
  await expect(page.getByRole("link", { name: "Settings" })).not.toBeVisible();
});

test("authenticated user sees overview page content", async ({ page }) => {
  await page.goto("/overview");
  await expect(page).not.toHaveURL(/\/login/);
  await expect(page.getByRole("heading", { name: "Dashboard" })).toBeVisible();
});

test("navigating to policies shows policies page", async ({ page }) => {
  await page.goto("/policies");
  await expect(page.getByRole("heading", { name: "Policies" })).toBeVisible();
});

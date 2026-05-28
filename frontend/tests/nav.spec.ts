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
  // Use exact: true to avoid matching "Activity Log"
  await expect(page.getByText("Activity", { exact: true })).toBeVisible();
  await expect(page.getByText("Governance", { exact: true })).toBeVisible();
  await expect(page.getByText("Intelligence", { exact: true })).toBeVisible();
  await expect(page.getByText("Reports", { exact: true })).toBeVisible();
});

test("sidebar renders all nav items", async ({ page }) => {
  await page.goto("/overview");
  // Use role-based locators to be specific about sidebar links
  await expect(page.getByRole("link", { name: "Overview" })).toBeVisible();
  await expect(page.getByRole("link", { name: "Audit Log" })).toBeVisible();
  await expect(page.getByRole("link", { name: "Policies" })).toBeVisible();
  await expect(page.getByRole("link", { name: "Agents" })).toBeVisible();
  await expect(page.getByRole("link", { name: "Activity Log" })).toBeVisible();
});

test("authenticated user sees overview page content", async ({ page }) => {
  await page.goto("/overview");
  await expect(page).not.toHaveURL(/\/login/);
  await expect(page.getByRole("heading", { name: "Overview" })).toBeVisible();
});

test("navigating to policies shows policies page", async ({ page }) => {
  await page.goto("/policies");
  await expect(page.getByRole("heading", { name: "Policies" })).toBeVisible();
});

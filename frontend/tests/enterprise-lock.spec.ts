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

test("locked nav items are visible in sidebar", async ({ page }) => {
  await page.goto("/overview");
  await expect(page.getByText("Sessions")).toBeVisible();
  await expect(page.getByText("Review Queue")).toBeVisible();
  await expect(page.getByText("Health")).toBeVisible();
  await expect(page.getByText("Compliance")).toBeVisible();
});

test("sessions page shows enterprise lock overlay", async ({ page }) => {
  await page.goto("/sessions");
  await expect(page.getByText("Requires Enterprise License")).toBeVisible();
});

test("review queue page shows enterprise lock overlay", async ({ page }) => {
  await page.goto("/reviews");
  await expect(page.getByText("Requires Enterprise License")).toBeVisible();
});

test("enterprise locked pages are not hidden from DOM", async ({ page }) => {
  await page.goto("/sessions");
  const lockText = page.getByText("Requires Enterprise License");
  await expect(lockText).toBeVisible();
  // Verify it's in the DOM (not hidden via display:none)
  const isHidden = await lockText.evaluate((el) =>
    window.getComputedStyle(el).display === "none"
  );
  expect(isHidden).toBe(false);
});

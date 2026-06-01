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

test("locked nav items are visible in their sections", async ({ page }) => {
  await page.goto("/overview");
  // Activity section auto-opens — Sessions (locked) should be visible
  await expect(page.getByText("Sessions", { exact: true })).toBeVisible();

  // Open Manual Reviews — Review queue (locked) should appear
  await page.getByText("Manual Reviews", { exact: true }).click();
  await expect(page.getByText("Review queue", { exact: true })).toBeVisible();

  // Open Reports — Compliance (locked) should appear
  await page.getByText("Reports", { exact: true }).click();
  await expect(page.getByText("Compliance", { exact: true })).toBeVisible();
});

test("sessions page shows enterprise lock overlay", async ({ page }) => {
  await page.goto("/sessions");
  await expect(page.getByText("Sessions — Enterprise Feature")).toBeVisible();
});

test("review queue page shows enterprise lock overlay", async ({ page }) => {
  await page.goto("/reviews");
  await expect(page.getByText("Review Queue — Enterprise Feature")).toBeVisible();
});

test("enterprise locked pages are not hidden from DOM", async ({ page }) => {
  await page.goto("/sessions");
  const lockText = page.getByText("Sessions — Enterprise Feature");
  await expect(lockText).toBeVisible();
  // Verify it's in the DOM (not hidden via display:none)
  const isHidden = await lockText.evaluate((el) =>
    window.getComputedStyle(el).display === "none"
  );
  expect(isHidden).toBe(false);
});

import { expect, test } from "@playwright/test";

const COMMUNITY_USAGE = {
  plan: "community",
  company: null,
  annual_price_usd: 0,
  retention_days: 7,
  features: ["Policy engine enforcement"],
  this_month: { period: "2026-09", intercepts: 1234 },
  last_month: { period: "2026-08", intercepts: 987 },
  manage_subscription_url: null,
  upgrade_url: null,
  license_status: null,
  license_synced_at: null,
};

const ENTERPRISE_USAGE = {
  plan: "enterprise",
  company: "Acme Insurance",
  annual_price_usd: 1999,
  retention_days: 365,
  features: [
    "Policy engine enforcement",
    "Compliance report export (SOC 2, EU AI Act, NIST AI RMF, ISO 42001)",
  ],
  this_month: { period: "2026-09", intercepts: 2_400_000 },
  last_month: { period: "2026-08", intercepts: 1_800_000 },
  manage_subscription_url: "https://billing.stripe.com/session/abc",
  upgrade_url: null,
  license_status: "active",
  license_synced_at: "2026-09-16T08:00:00Z",
};

const PAST_DUE_USAGE = {
  ...ENTERPRISE_USAGE,
  license_status: "past_due",
};

const TRIAL_USAGE = {
  ...ENTERPRISE_USAGE,
  plan: "trial",
  company: "Acme Insurance",
  annual_price_usd: 0,
};

const EXPIRED_TRIAL_USAGE = {
  ...COMMUNITY_USAGE,
  company: "Acme Insurance",
  license_status: "expired",
};

test.beforeEach(async ({ page }) => {
  await page.goto("/login");
  await page.evaluate(() => {
    sessionStorage.setItem(
      "ac_auth",
      JSON.stringify({ email: "admin@aicontrol.dev", role: "admin", token: "test-token" }),
    );
  });
});

function mockUsage(page: import("@playwright/test").Page, usage: unknown, status = 200) {
  return page.route("**/billing/usage", (route) =>
    route.request().resourceType() === "document"
      ? route.continue()
      : route.fulfill({ status, json: usage }),
  );
}

test("community plan shows the retention warning and a live upgrade link", async ({ page }) => {
  await mockUsage(page, COMMUNITY_USAGE);
  await page.goto("/billing");
  await expect(page.getByText("COMMUNITY")).toBeVisible();
  await expect(page.getByText("Audit log retention: 7 days.")).toBeVisible();
  const upgradeLink = page.getByRole("link", { name: "Upgrade" });
  await expect(upgradeLink).toBeVisible();
  await expect(upgradeLink).toHaveAttribute("href", "https://aictl.io/pricing");
  await expect(upgradeLink).toHaveAttribute("target", "_blank");
  await expect(page.getByRole("link", { name: "Manage Subscription" })).not.toBeVisible();
});

test("enterprise plan lists its features and links to real subscription management", async ({ page }) => {
  await mockUsage(page, ENTERPRISE_USAGE);
  await page.goto("/billing");
  await expect(page.getByText("ENTERPRISE")).toBeVisible();
  await expect(page.getByText("Acme Insurance")).toBeVisible();
  await expect(
    page.getByText("Compliance report export (SOC 2, EU AI Act, NIST AI RMF, ISO 42001)"),
  ).toBeVisible();
  const manageLink = page.getByRole("link", { name: "Manage Subscription" });
  await expect(manageLink).toBeVisible();
  await expect(manageLink).toHaveAttribute("href", "https://billing.stripe.com/session/abc");
});

test("enterprise plan shows exactly one retention line sourced from retention_days", async ({ page }) => {
  await mockUsage(page, ENTERPRISE_USAGE);
  await page.goto("/billing");
  await expect(page.getByText("Audit log retention: 365 days.")).toBeVisible();
  await expect(page.getByText(/7-day retention|30-day retention|90-day retention|1-year retention/i)).toHaveCount(0);
});

test("license status and last sync time are shown for a synced plan", async ({ page }) => {
  await mockUsage(page, ENTERPRISE_USAGE);
  await page.goto("/billing");
  await expect(page.getByText(/Active/i)).toBeVisible();
  await expect(page.getByText(/Last synced/i)).toBeVisible();
});

test("activation code entry saves the code and refreshes status", async ({ page }) => {
  await mockUsage(page, COMMUNITY_USAGE);
  await page.route("**/settings/license-activation", (route) =>
    route.fulfill({
      status: 200,
      json: { license_status: "active", license_plan: "business", license_synced_at: "2026-09-16T09:00:00Z" },
    }),
  );
  await page.goto("/billing");
  await page.getByPlaceholder("Activation code").fill("ac-test-code-123");
  await page.getByRole("button", { name: "Activate" }).click();
  await expect(page.getByText(/activated/i)).toBeVisible();
});

test("an invalid activation code shows an error and does not clear the field", async ({ page }) => {
  await mockUsage(page, COMMUNITY_USAGE);
  await page.route("**/settings/license-activation", (route) =>
    route.fulfill({ status: 400, json: { detail: "Invalid activation code" } }),
  );
  await page.goto("/billing");
  await page.getByPlaceholder("Activation code").fill("bad-code");
  await page.getByRole("button", { name: "Activate" }).click();
  await expect(page.getByText("Invalid activation code")).toBeVisible();
  await expect(page.getByPlaceholder("Activation code")).toHaveValue("bad-code");
});

test("past_due status shows a reactivate prompt instead of the usage chart", async ({ page }) => {
  await mockUsage(page, PAST_DUE_USAGE);
  await page.goto("/billing");
  await expect(page.getByText(/Reactivate your plan/i)).toBeVisible();
  const reactivateLink = page.getByRole("link", { name: /Reactivate/i });
  await expect(reactivateLink).toHaveAttribute("href", "https://billing.stripe.com/session/abc");
  await expect(page.getByText("Intercept Usage")).not.toBeVisible();
});

test("usage numbers are shown for this month and last month", async ({ page }) => {
  await mockUsage(page, ENTERPRISE_USAGE);
  await page.goto("/billing");
  await expect(page.locator("p.text-2xl", { hasText: "2.40M" })).toBeVisible();
  await expect(page.locator("p.text-2xl", { hasText: "1.80M" })).toBeVisible();
});

test("a failed usage fetch shows an error, not a blank page", async ({ page }) => {
  await mockUsage(page, { detail: "error" }, 500);
  await page.goto("/billing");
  await expect(page.getByText("Failed to load billing data.")).toBeVisible();
});

test("trial plan shows the TRIAL pill and enterprise-tier features", async ({ page }) => {
  await mockUsage(page, TRIAL_USAGE);
  await page.goto("/billing");
  await expect(page.getByText("TRIAL")).toBeVisible();
  await expect(
    page.getByText("Compliance report export (SOC 2, EU AI Act, NIST AI RMF, ISO 42001)"),
  ).toBeVisible();
});

test("an expired trial shows the Trial expired label and a live upgrade link", async ({ page }) => {
  await mockUsage(page, EXPIRED_TRIAL_USAGE);
  await page.goto("/billing");
  await expect(page.getByText("COMMUNITY")).toBeVisible();
  await expect(page.getByText("Trial expired")).toBeVisible();
  await expect(page.getByRole("link", { name: "Upgrade" })).toBeVisible();
});

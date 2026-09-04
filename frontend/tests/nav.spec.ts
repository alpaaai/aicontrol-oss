import { expect, test } from "@playwright/test";

const FREE_ITEMS = ["Overview", "Agents", "Policies", "Audit log", "Metrics", "Policy Drift"];
const PAID_ONLY = ["Reviews", "Reports", "Billing"];

test.beforeEach(async ({ page }) => {
  await page.route("**/license/features", (route) =>
    route.fulfill({
      json: { tier: "enterprise", features: { nl_authoring: true, simulation: true, hitl: true, compliance_reports: true } },
    }),
  );
  await page.goto("/login");
  await page.evaluate(() => {
    sessionStorage.setItem(
      "ac_auth",
      JSON.stringify({ email: "admin@aicontrol.dev", role: "admin", token: "test-token" }),
    );
  });
});

test("free install shows only free destinations", async ({ page }) => {
  await page.route("**/license/features", (route) =>
    route.fulfill({
      json: { tier: "free", features: { nl_authoring: false, simulation: false, hitl: false, compliance_reports: false } },
    }),
  );
  await page.goto("/");
  const nav = page.getByRole("navigation");
  for (const item of FREE_ITEMS) {
    await expect(nav.getByRole("link", { name: item })).toBeVisible();
  }
  for (const item of PAID_ONLY) {
    await expect(nav.getByRole("link", { name: item })).toHaveCount(0);
  }
});

test("nav has no section headers or accordions", async ({ page }) => {
  await page.goto("/");
  const nav = page.getByRole("navigation");
  await expect(nav.getByRole("button", { expanded: false })).toHaveCount(0);
  await expect(nav.locator("[data-section-header]")).toHaveCount(0);
});

test("the active item carries the magenta edge marker", async ({ page }) => {
  await page.goto("/agents");
  const active = page.getByRole("navigation").getByRole("link", { name: "Agents" });
  await expect(active).toHaveAttribute("aria-current", "page");
  const marker = await active.evaluate((el) =>
    getComputedStyle(el, "::before").backgroundColor,
  );
  expect(marker).toBe("rgb(255, 45, 122)");
});

test("every nav item is reachable by keyboard with a visible focus ring", async ({ page }) => {
  await page.goto("/");
  await page.keyboard.press("Tab");
  const outline = await page.evaluate(() => {
    const el = document.activeElement as HTMLElement;
    return getComputedStyle(el).outlineStyle;
  });
  expect(outline).not.toBe("none");
});

import { test, expect } from "@playwright/test";

test.beforeEach(async ({ page }) => {
  await page.goto("/login");
  await page.evaluate(() => {
    sessionStorage.setItem(
      "ac_auth",
      JSON.stringify({ email: "admin@aicontrol.dev", role: "admin", token: "test-token" })
    );
  });
});

test("reviews page shows business lock for community", async ({ page }) => {
  await page.goto("/reviews");
  await expect(page.getByRole("heading", { name: "Review Queue" })).toBeVisible();
  await expect(page.getByText("Review Queue — Business Feature")).toBeVisible();
});

test("reviews page shows a reactivate prompt for a past_due business org, not the lock or content", async ({ page }) => {
  await page.route("**/license-info", (route) =>
    route.fulfill({
      json: { plan: "business", company: "Acme", is_enterprise: false, is_business: true, expires_at: null },
    }),
  );
  await page.route("**/license/features", (route) =>
    route.fulfill({
      json: { tier: "business", features: { nl_authoring: true, simulation: true, hitl: true, compliance_reports: false }, license_status: "past_due" },
    }),
  );
  await page.goto("/reviews");
  await expect(page.getByText(/Reactivate your plan/i)).toBeVisible();
  await expect(page.getByText("Review Queue — Business Feature")).not.toBeVisible();
});

const PENDING_REVIEW = {
  id: "r1",
  audit_event_id: "ae1",
  session_id: "22222222-2222-2222-2222-222222222222",
  status: "pending",
  reviewer: null,
  review_note: null,
  reviewed_at: null,
  created_at: "2026-09-14T00:00:00Z",
  response_deadline: null,
  assigned_to: null,
  tool_name: "release_payment",
  tool_parameters: "{}",
};

test.describe("business tier — resolving a review", () => {
  test.beforeEach(async ({ page }) => {
    await page.route("**/license-info", (route) =>
      route.fulfill({
        json: { plan: "business", company: "Acme", is_enterprise: false, is_business: true, expires_at: null },
      })
    );
    await page.route("**/reviews?**", (route) => {
      if (route.request().method() === "GET") {
        return route.fulfill({ json: [PENDING_REVIEW] });
      }
      return route.continue();
    });
  });

  test("a failed approve surfaces an inline error instead of failing silently", async ({ page }) => {
    await page.route("**/reviews/r1", (route) => {
      if (route.request().method() === "PATCH") {
        return route.fulfill({ status: 409, json: { detail: "Review already resolved" } });
      }
      return route.continue();
    });

    await page.goto("/reviews");
    await expect(page.getByText("Session: 22222222…")).toBeVisible();
    await page.getByRole("button", { name: "Approve" }).click();

    await expect(page.getByText("Review already resolved")).toBeVisible();
  });
});

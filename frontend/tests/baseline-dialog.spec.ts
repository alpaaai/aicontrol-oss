import { expect, test } from "@playwright/test";

test.beforeEach(async ({ page }) => {
  await page.route("**/license/features", (route) =>
    route.fulfill({
      json: { tier: "enterprise", features: { nl_authoring: true, simulation: true, hitl: true, compliance_reports: true } },
    }),
  );
  await page.route("http://localhost:8001/dashboard/outcomes*", (route) =>
    route.fulfill({ json: { window: "7d", workflows: [], agents: [] } }),
  );
  await page.route("http://localhost:8001/audit-events*", (route) =>
    route.fulfill({ json: { events: [], total: 0 } }),
  );
  await page.goto("/login");
  await page.evaluate(() => {
    sessionStorage.setItem(
      "ac_auth",
      JSON.stringify({ email: "admin@aicontrol.dev", role: "admin", token: "test-token" }),
    );
  });
});

test("baseline dialog appears on overview after setup flags it", async ({ page }) => {
  await page.evaluate(() => sessionStorage.setItem("show_baseline_dialog", "true"));
  await page.goto("/");
  await expect(page.getByText("Activate a starting policy set")).toBeVisible();
  await expect(page.getByRole("button", { name: "Standard", exact: true })).toBeVisible();
  await expect(page.getByRole("button", { name: "Strict", exact: true })).toBeVisible();
});

test("baseline dialog does not appear without the flag", async ({ page }) => {
  await page.goto("/");
  await expect(page.getByText("Activate a starting policy set")).toHaveCount(0);
});

test("choosing standard activates baseline and closes dialog", async ({ page }) => {
  await page.evaluate(() => sessionStorage.setItem("show_baseline_dialog", "true"));
  let requestBody: unknown = null;
  await page.route("http://localhost:8001/policies/activate-baseline", (route) => {
    requestBody = route.request().postDataJSON();
    route.fulfill({
      json: {
        mode: "standard",
        activated: ["block_shell_execution", "block_file_deletion", "block_cloud_metadata_access", "block_sensitive_file_reads"],
      },
    });
  });
  await page.goto("/");
  await page.getByRole("button", { name: "Standard", exact: true }).click();
  await expect(page.getByText(/4 policies activated/i)).toBeVisible();
  expect(requestBody).toEqual({ mode: "standard" });
  await page.getByRole("button", { name: "Done" }).click();
  await expect(page.getByText("Activate a starting policy set")).toHaveCount(0);
});

test("skipping the dialog closes it without activating anything", async ({ page }) => {
  await page.evaluate(() => sessionStorage.setItem("show_baseline_dialog", "true"));
  await page.goto("/");
  await page.getByRole("button", { name: /Skip/i }).click();
  await expect(page.getByText("Activate a starting policy set")).toHaveCount(0);
});

test("reloading overview does not re-show the dialog after it was handled", async ({ page }) => {
  await page.evaluate(() => sessionStorage.setItem("show_baseline_dialog", "true"));
  await page.goto("/");
  await page.getByRole("button", { name: /Skip/i }).click();
  await page.reload();
  await expect(page.getByText("Activate a starting policy set")).toHaveCount(0);
});

import { expect, test } from "@playwright/test";

const POLICIES = [
  { id: "p1", name: "review_high_value_payment", active: true,
    principalType: "agent", principalId: "claims-adjuster",
    actionTool: "release_payment", resourceSystem: "guidewire",
    effect: "review", condition: { numeric_conditions: { amount: { gt: 50000 } } } },
  { id: "p2", name: "deny_bulk_claims_query", active: true,
    principalType: "agent", principalId: "claims-adjuster",
    actionTool: "db_query", resourceSystem: "guidewire",
    effect: "deny", condition: { numeric_conditions: { row_limit: { gt: 100 } } } },
];

test.beforeEach(async ({ page }) => {
  // Scoped to the API call, not the SPA route of the same name: the glob
  // "**/policies" also matches the browser's document navigation to /policies.
  await page.route("**/policies", (route) =>
    route.request().resourceType() === "document"
      ? route.continue()
      : route.fulfill({ json: POLICIES }),
  );
  await page.goto("/login");
  await page.evaluate(() => {
    sessionStorage.setItem(
      "ac_auth",
      JSON.stringify({ email: "admin@aicontrol.dev", role: "admin", token: "test-token" }),
    );
  });
});

test("each list row is the policy sentence, not a name and a rule type", async ({ page }) => {
  await page.goto("/policies");
  const row = page.getByTestId("policy-row-p1");
  await expect(row).toContainText("claims-adjuster");
  await expect(row).toContainText("release a payment");
  await expect(row).not.toContainText("tool_denylist");
});

test("no raw rule text is visible by default", async ({ page }) => {
  await page.goto("/policies/p1");
  await expect(page.getByTestId("raw-rule")).toBeHidden();
  await expect(page.getByRole("button", { name: /view rule/i })).toBeVisible();
});

test("view rule discloses the rule text", async ({ page }) => {
  await page.goto("/policies/p1");
  await page.getByRole("button", { name: /view rule/i }).click();
  await expect(page.getByTestId("raw-rule")).toBeVisible();
});

test("the composer is the primary input and the editor is its peer", async ({ page }) => {
  await page.route("**/license/features", (route) =>
    route.fulfill({ json: { tier: "enterprise", features: { nl_authoring: true, simulation: true, hitl: true, compliance_reports: true } } }),
  );
  await page.goto("/policies");
  await expect(page.getByTestId("nl-composer")).toBeVisible();
  await expect(page.getByTestId("structured-editor")).toBeVisible();
  const composerBox = await page.getByTestId("nl-composer").boundingBox();
  const editorBox = await page.getByTestId("structured-editor").boundingBox();
  expect(Math.abs(composerBox!.y - editorBox!.y)).toBeLessThan(200);
});

test("a free install shows the structured editor alone", async ({ page }) => {
  await page.route("**/license/features", (route) =>
    route.fulfill({ json: { tier: "free", features: { nl_authoring: false, simulation: false, hitl: false, compliance_reports: false } } }),
  );
  await page.goto("/policies");
  await expect(page.getByTestId("nl-composer")).toHaveCount(0);
  await expect(page.getByTestId("structured-editor")).toBeVisible();
});

test("the activate button keeps its word through the flow", async ({ page }) => {
  await page.goto("/policies/p1");
  const button = page.getByRole("button", { name: "Activate" });
  await button.click();
  await expect(page.getByRole("button", { name: "Activated" })).toBeVisible();
});

test("policy detail shows what the policy did last week", async ({ page }) => {
  await page.route("**/policies/p1/activity*", (route) =>
    route.fulfill({ json: { window: "7d", fired: 3, calls_evaluated: 412 } }),
  );
  await page.goto("/policies/p1");
  await expect(page.getByTestId("policy-activity")).toContainText("3");
  await expect(page.getByTestId("policy-activity")).toContainText("412");
});

test("the policy list scrolls rather than clipping", async ({ page }) => {
  await page.goto("/policies");
  const overflow = await page.getByTestId("policy-list")
    .evaluate((el) => getComputedStyle(el).overflowY);
  expect(overflow).toBe("auto");
});

import { expect, test, type Page } from "@playwright/test";

async function openComposer(page: Page) {
  await page.goto("/policies");
  await page.getByTestId("new-policy-button").click();
}

const DRAFT_RESPONSE = {
  draft: { principal_type: "agent", principal_id: "claims-adjuster",
           action_tool: "release_payment", resource_system: "guidewire",
           effect: "review", condition: { numeric_conditions: { amount: { gt: 50000 } } } },
  sentence: "claims-adjuster may not release a payment on Guidewire when amount > 50,000",
  status: "drafted", warnings: [],
};

test.beforeEach(async ({ page }) => {
  await page.route("**/license/features", (route) =>
    route.fulfill({ json: { tier: "enterprise", features: { nl_authoring: true, simulation: true, hitl: true, compliance_reports: true } } }),
  );
  await page.route("**/policies/nl-draft", (route) => route.fulfill({ json: DRAFT_RESPONSE }));
  await page.goto("/login");
  await page.evaluate(() => {
    sessionStorage.setItem(
      "ac_auth",
      JSON.stringify({ email: "admin@aicontrol.dev", role: "admin", token: "test-token" }),
    );
  });
});

test("the composer asks the product's question", async ({ page }) => {
  await openComposer(page);
  await expect(page.getByTestId("nl-composer"))
    .toContainText("What should this agent never be allowed to do?");
});

test("a description produces a sentence, never JSON or Cedar", async ({ page }) => {
  await openComposer(page);
  await page.getByTestId("nl-input").fill("no payments over 50000 on guidewire");
  await page.getByRole("button", { name: "Draft policy" }).click();
  const review = page.getByTestId("draft-review");
  await expect(review).toContainText("release a payment");
  await expect(review).not.toContainText("forbid");
  await expect(review).not.toContainText("principal_type");
});

test("the draft's chips are editable", async ({ page }) => {
  await openComposer(page);
  await page.getByTestId("nl-input").fill("no payments over 50000 on guidewire");
  await page.getByRole("button", { name: "Draft policy" }).click();
  await expect(page.getByTestId("draft-review").getByRole("button").first()).toBeEnabled();
});

test("simulation reports an outcome, not a diff", async ({ page }) => {
  await page.route("**/policies/simulate", (route) =>
    route.fulfill({ json: { eligible_events: 412, would_deny: 0, would_review: 3,
                            corpus_start: "2026-08-15T00:00:00Z", corpus_note: null,
                            matches: [] } }),
  );
  await openComposer(page);
  await page.getByTestId("nl-input").fill("no payments over 50000 on guidewire");
  await page.getByRole("button", { name: "Draft policy" }).click();
  await page.getByRole("button", { name: "Simulate" }).click();
  await expect(page.getByTestId("simulation-result"))
    .toContainText("Would have held 3 of 412 calls for approval");
});

test("an empty corpus says so instead of showing a confident zero", async ({ page }) => {
  await page.route("**/policies/simulate", (route) =>
    route.fulfill({ json: { eligible_events: 0, would_deny: null, would_review: null,
                            corpus_start: null,
                            corpus_note: "No traffic recorded since governance began capturing workflow and system.",
                            matches: [] } }),
  );
  await openComposer(page);
  await page.getByTestId("nl-input").fill("no payments over 50000 on guidewire");
  await page.getByRole("button", { name: "Draft policy" }).click();
  await page.getByRole("button", { name: "Simulate" }).click();
  const result = page.getByTestId("simulation-result");
  await expect(result).toContainText("No traffic recorded");
  await expect(result).not.toContainText("0 of 0");
});

test("nothing is saved until a human activates", async ({ page }) => {
  let activated = false;
  await page.route("**/policies", (route) => {
    if (route.request().resourceType() === "document") return route.continue();
    if (route.request().method() === "POST") { activated = true; }
    return route.fulfill({ json: [] });
  });
  await openComposer(page);
  await page.getByTestId("nl-input").fill("no payments over 50000 on guidewire");
  await page.getByRole("button", { name: "Draft policy" }).click();
  expect(activated).toBe(false);
  await page.getByRole("button", { name: "Activate" }).click();
  expect(activated).toBe(true);
});

test("activate keeps its word through the flow", async ({ page }) => {
  await page.route("**/policies", (route) =>
    route.request().resourceType() === "document"
      ? route.continue()
      : route.fulfill({ json: [] }),
  );
  await openComposer(page);
  await page.getByTestId("nl-input").fill("no payments over 50000 on guidewire");
  await page.getByRole("button", { name: "Draft policy" }).click();
  await page.getByRole("button", { name: "Activate" }).click();
  await expect(page.getByRole("button", { name: "Activated" })).toBeVisible();
});

test("a manual-authoring fallback explains itself", async ({ page }) => {
  await page.route("**/policies/nl-draft", (route) =>
    route.fulfill({ json: { draft: null, sentence: null, status: "requires_manual_authoring",
                            warnings: ["geofencing is not a supported condition"] } }),
  );
  await openComposer(page);
  await page.getByTestId("nl-input").fill("only allow calls from the US");
  await page.getByRole("button", { name: "Draft policy" }).click();
  await expect(page.getByTestId("draft-review")).toContainText("geofencing is not a supported condition");
});

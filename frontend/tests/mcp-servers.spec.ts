import { expect, test } from "@playwright/test";

const SERVERS = [
  {
    id: "s1",
    name: "lending-crm",
    base_url: "https://crm.internal.example.com/mcp",
    status: "active",
    approved_tools: ["get_account", "list_transactions"],
    created_at: "2026-01-15T00:00:00Z",
  },
  {
    id: "s2",
    name: "claims-itsm",
    base_url: "https://itsm.internal.example.com/mcp",
    status: "pending_review",
    approved_tools: [],
    created_at: "2026-02-01T00:00:00Z",
  },
];

async function loginAsAdmin(page: import("@playwright/test").Page) {
  await page.goto("/login");
  await page.evaluate(() => {
    sessionStorage.setItem(
      "ac_auth",
      JSON.stringify({ email: "admin@aicontrol.dev", role: "admin", token: "test-token" }),
    );
  });
}

test.beforeEach(async ({ page }) => {
  // Scoped to the API call, not the SPA route of the same name: the glob
  // "**/mcp-servers" also matches the browser's document navigation to
  // /mcp-servers.
  await page.route("**/mcp-servers", (route) =>
    route.request().resourceType() === "document"
      ? route.continue()
      : route.fulfill({ json: SERVERS }),
  );
});

test("each registered server shows its base URL, status, and approved tools", async ({ page }) => {
  await loginAsAdmin(page);
  await page.goto("/mcp-servers");
  const active = page.getByTestId("mcp-server-row-lending-crm");
  await expect(active).toContainText("https://crm.internal.example.com/mcp");
  await expect(active).toContainText("Active");
  await expect(active).toContainText("get_account, list_transactions");

  const pending = page.getByTestId("mcp-server-row-claims-itsm");
  await expect(pending).toContainText("Pending review");
  await expect(pending).toContainText("—");
});

test("a pending server can be approved", async ({ page }) => {
  let approved = false;
  await page.route("**/mcp-servers", (route) =>
    route.request().resourceType() === "document"
      ? route.continue()
      : route.fulfill({
          json: approved ? [SERVERS[0], { ...SERVERS[1], status: "active" }] : SERVERS,
        }),
  );
  await page.route("**/mcp-servers/s2", (route) => {
    approved = true;
    return route.fulfill({ json: { ...SERVERS[1], status: "active" } });
  });
  await loginAsAdmin(page);
  await page.goto("/mcp-servers");
  await page.getByTestId("mcp-server-row-claims-itsm").getByRole("button", { name: "Approve" }).click();
  await expect(page.getByTestId("mcp-server-row-claims-itsm")).toContainText("Active");
});

test("blocking a server requires confirmation", async ({ page }) => {
  let blocked = false;
  await page.route("**/mcp-servers", (route) =>
    route.request().resourceType() === "document"
      ? route.continue()
      : route.fulfill({
          json: blocked ? [{ ...SERVERS[0], status: "blocked" }, SERVERS[1]] : SERVERS,
        }),
  );
  await page.route("**/mcp-servers/s1", (route) => {
    blocked = true;
    return route.fulfill({ json: { ...SERVERS[0], status: "blocked" } });
  });
  await loginAsAdmin(page);
  await page.goto("/mcp-servers");
  const row = page.getByTestId("mcp-server-row-lending-crm");
  await row.getByRole("button", { name: "Block" }).click();
  await expect(row.getByText("Block this server?")).toBeVisible();
  await row.getByRole("button", { name: "Cancel" }).click();
  await expect(row.getByText("Block this server?")).not.toBeVisible();

  await row.getByRole("button", { name: "Block" }).click();
  await row.getByRole("button", { name: "Confirm" }).click();
  await expect(row).toContainText("Blocked");
});

test("register button is visible to admins and opens the dialog", async ({ page }) => {
  await loginAsAdmin(page);
  await page.goto("/mcp-servers");
  await page.getByRole("button", { name: "Register new MCP server" }).click();
  await expect(page.getByRole("heading", { name: "Register new MCP server" })).toBeVisible();
  await expect(page.getByPlaceholder("e.g. lending-crm")).toBeVisible();
});

test("register dialog rejects a non-http(s) base URL before submitting", async ({ page }) => {
  await loginAsAdmin(page);
  await page.goto("/mcp-servers");
  await page.getByRole("button", { name: "Register new MCP server" }).click();
  await page.getByPlaceholder("e.g. lending-crm").fill("bad-server");
  await page.getByPlaceholder("https://crm.internal.example.com/mcp").fill("not-a-url");
  await page.getByRole("button", { name: "Register server" }).click();
  await expect(page.getByText("Base URL must be a valid http(s) URL")).toBeVisible();
});

test("registering a server adds it to the table", async ({ page }) => {
  const created = {
    id: "s3",
    name: "new-server",
    base_url: "https://new.internal.example.com/mcp",
    status: "pending_review",
    approved_tools: [],
    created_at: "2026-03-01T00:00:00Z",
  };
  let listCalls = 0;
  await page.route("**/mcp-servers", (route) => {
    if (route.request().resourceType() === "document") return route.continue();
    const method = route.request().method();
    if (method === "POST") return route.fulfill({ json: created });
    if (method !== "GET") return route.fulfill({ json: {} });
    listCalls += 1;
    return route.fulfill({ json: listCalls === 1 ? SERVERS : [...SERVERS, created] });
  });
  await loginAsAdmin(page);
  await page.goto("/mcp-servers");
  await page.getByRole("button", { name: "Register new MCP server" }).click();
  await page.getByPlaceholder("e.g. lending-crm").fill("new-server");
  await page.getByPlaceholder("https://crm.internal.example.com/mcp").fill("https://new.internal.example.com/mcp");
  await page.getByRole("button", { name: "Register server" }).click();
  await expect(page.getByTestId("mcp-server-row-new-server")).toBeVisible();
});

test("register button is hidden for non-admin users", async ({ page }) => {
  await page.goto("/login");
  await page.evaluate(() => {
    sessionStorage.setItem(
      "ac_auth",
      JSON.stringify({ email: "analyst@aicontrol.dev", role: "analyst", token: "test-token" }),
    );
  });
  await page.goto("/mcp-servers");
  await expect(page.getByRole("button", { name: "Register new MCP server" })).not.toBeVisible();
});

test("an empty registry gets an invitation, not a blank page", async ({ page }) => {
  await page.route("**/mcp-servers", (route) =>
    route.request().resourceType() === "document" ? route.continue() : route.fulfill({ json: [] }),
  );
  await loginAsAdmin(page);
  await page.goto("/mcp-servers");
  await expect(page.getByText(/No MCP servers registered yet/i)).toBeVisible();
});

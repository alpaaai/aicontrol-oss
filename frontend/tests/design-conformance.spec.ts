import { expect, test } from "@playwright/test";

const ROUTES = ["/", "/agents", "/policies", "/audit", "/reviews", "/metrics", "/reports", "/billing"];

test.beforeEach(async ({ page }) => {
  await page.goto("/login");
  await page.evaluate(() => {
    sessionStorage.setItem(
      "ac_auth",
      JSON.stringify({ email: "admin@aicontrol.dev", role: "admin", token: "test-token" }),
    );
  });
});

for (const route of ROUTES) {
  test(`${route} paints the cream canvas`, async ({ page }) => {
    await page.goto(route);
    const bg = await page.evaluate(() => getComputedStyle(document.body).backgroundColor);
    expect(bg).toBe("rgb(251, 249, 243)");
  });

  test(`${route} uses no hard-coded legacy brand colour`, async ({ page }) => {
    await page.goto(route);
    const found = await page.evaluate(() => {
      const legacy = ["rgb(2, 132, 168)", "rgb(194, 46, 40)", "rgb(143, 87, 16)"];
      return [...document.querySelectorAll("*")].some((el) => {
        const s = getComputedStyle(el);
        return legacy.includes(s.color) || legacy.includes(s.backgroundColor);
      });
    });
    expect(found).toBe(false);
  });

  test(`${route} has no horizontal body scroll at 375px`, async ({ page }) => {
    await page.setViewportSize({ width: 375, height: 800 });
    await page.goto(route);
    const overflows = await page.evaluate(
      () => document.documentElement.scrollWidth > document.documentElement.clientWidth,
    );
    expect(overflows).toBe(false);
  });
}

import { expect, test } from "@playwright/test";

const REQUIRED_TOKENS = [
  "--ac-primary", "--ac-primary-active", "--ac-primary-soft",
  "--ac-ink", "--ac-body", "--ac-muted",
  "--ac-hairline", "--ac-hairline-soft", "--ac-hairline-strong",
  "--ac-canvas", "--ac-canvas-soft", "--ac-surface-card", "--ac-surface-sunk",
  "--ac-surface-ink", "--ac-on-ink",
  "--ac-decision-allow", "--ac-decision-review", "--ac-decision-deny",
];

test("every semantic token is defined on :root", async ({ page }) => {
  await page.goto("/");
  for (const token of REQUIRED_TOKENS) {
    const value = await page.evaluate(
      (t) => getComputedStyle(document.documentElement).getPropertyValue(t).trim(),
      token,
    );
    expect(value, `${token} is undefined`).not.toBe("");
  }
});

test("the canvas is warm cream, not white", async ({ page }) => {
  await page.goto("/");
  const canvas = await page.evaluate(() =>
    getComputedStyle(document.documentElement).getPropertyValue("--ac-canvas").trim(),
  );
  expect(canvas.toUpperCase()).toBe("#FBF9F3");
});

test("no dark-theme block survives", async ({ page }) => {
  await page.goto("/");
  const hasDarkAttr = await page.evaluate(() =>
    document.documentElement.hasAttribute("data-theme"),
  );
  expect(hasDarkAttr).toBe(false);
});

test("the display face is loaded", async ({ page }) => {
  await page.goto("/");
  const loaded = await page.evaluate(() =>
    document.fonts.check('400 32px "Bricolage Grotesque"'),
  );
  expect(loaded).toBe(true);
});

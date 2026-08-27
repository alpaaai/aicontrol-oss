import { expect, test } from "@playwright/test";

test.beforeEach(async ({ page }) => {
  await page.goto("/gallery");
});

test("renders scope as a readable English sentence", async ({ page }) => {
  const sentence = page.getByTestId("policy-sentence-review-payment");
  await expect(sentence).toContainText("claims-adjuster");
  await expect(sentence).toContainText("may not");
  await expect(sentence).toContainText("release a payment");
  await expect(sentence).toContainText("Guidewire");
  await expect(sentence).toContainText("amount > 50,000");
});

test("no engine vocabulary reaches the sentence", async ({ page }) => {
  const text = (await page.getByTestId("policy-sentence-review-payment").textContent()) ?? "";
  for (const word of ["principal", "action", "resource", "forbid", "Cedar", "context."]) {
    expect(text.toLowerCase()).not.toContain(word.toLowerCase());
  }
});

test("only variable parts are chips", async ({ page }) => {
  const sentence = page.getByTestId("policy-sentence-review-payment");
  const chips = sentence.getByRole("button");
  await expect(chips).toHaveCount(4); // agent, tool, system, condition
  for (const chip of await chips.all()) {
    const bg = await chip.evaluate((el) => getComputedStyle(el).backgroundColor);
    expect(bg).toBe("rgb(255, 231, 240)"); // --ac-primary-soft
  }
});

test("a review policy shows its consequence clause", async ({ page }) => {
  await expect(page.getByTestId("policy-sentence-review-payment"))
    .toContainText("instead: send for approval");
});

test("a deny policy has no consequence clause", async ({ page }) => {
  await expect(page.getByTestId("policy-sentence-deny-bulk"))
    .not.toContainText("instead:");
});

test("tool_name_in renders the actual tool names, not the raw condition key", async ({ page }) => {
  const sentence = page.getByTestId("policy-sentence-tool-denylist");
  await expect(sentence).toContainText("bash");
  await expect(sentence).toContainText("exec_command");
  const text = (await sentence.textContent()) ?? "";
  expect(text).not.toContain("tool_name_in matches");
});

test("parameter_match with a nested operator object renders readable text, not [object Object]", async ({ page }) => {
  const sentence = page.getByTestId("policy-sentence-parameter-match-nested");
  const text = (await sentence.textContent()) ?? "";
  expect(text).not.toContain("[object Object]");
  await expect(sentence).toContainText("169.254.169.254");
});

test("an unscoped system renders as everywhere, not as a chip", async ({ page }) => {
  const sentence = page.getByTestId("policy-sentence-any-system");
  await expect(sentence).toContainText("anywhere");
  await expect(sentence.getByRole("button", { name: /anywhere/ })).toHaveCount(0);
});

test("inline variant carries identical text at a smaller size", async ({ page }) => {
  const display = page.getByTestId("policy-sentence-review-payment");
  const inline = page.getByTestId("policy-sentence-review-payment-inline");
  const strip = (s: string | null) => (s ?? "").replace(/\s+/g, " ").trim();
  expect(strip(await inline.textContent())).toBe(strip(await display.textContent()));
  const displaySize = await display.evaluate((el) => getComputedStyle(el).fontSize);
  const inlineSize = await inline.evaluate((el) => getComputedStyle(el).fontSize);
  expect(parseFloat(displaySize)).toBeGreaterThan(parseFloat(inlineSize));
});

test("deny pill is the only filled decision pill", async ({ page }) => {
  const deny = page.getByTestId("decision-pill-deny");
  await expect(deny).toHaveCSS("background-color", "rgb(26, 24, 21)");
  await expect(deny).toHaveCSS("color", "rgb(251, 249, 243)");
});

test("chips are keyboard reachable with a visible focus ring", async ({ page }) => {
  const chip = page.getByTestId("policy-sentence-review-payment").getByRole("button").first();
  await chip.focus();
  const outline = await chip.evaluate((el) => getComputedStyle(el).outlineStyle);
  expect(outline).not.toBe("none");
});

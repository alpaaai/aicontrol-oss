import { test, expect } from "@playwright/test";

// We can't import TS modules directly in Playwright without a test harness.
// Instead we inject a script that exercises the logic in a browser context.
// The actual test loads the Vite dev server, which bundles the module.

test.beforeEach(async ({ page }) => {
  await page.goto("/login");
  await page.evaluate(() => {
    sessionStorage.setItem(
      "ac_auth",
      JSON.stringify({ email: "test@test.com", role: "admin", token: "tok" })
    );
  });
});

test("formStateToCondition produces correct JSON for tool_denylist", async ({ page }) => {
  const result = await page.evaluate(async () => {
    // Dynamically import the module from the Vite dev server
    const mod = await import("/src/pages/policies/condition-form/conditionUtils.ts");
    const state = {
      type: "tool_denylist" as const,
      data: { blocked_tools: ["bash", "exec_command"] },
    };
    return mod.formStateToCondition(state);
  });
  expect(result).toEqual({ blocked_tools: ["bash", "exec_command"] });
});

test("formStateToCondition produces correct JSON for parameter_match contains_any", async ({ page }) => {
  const result = await page.evaluate(async () => {
    const mod = await import("/src/pages/policies/condition-form/conditionUtils.ts");
    const state = {
      type: "parameter_match" as const,
      data: {
        rows: [
          { key: "path", operator: "contains" as const, values: ["/etc/passwd"] },
        ],
      },
    };
    return mod.formStateToCondition(state);
  });
  expect(result).toEqual({
    parameter_match: { path: { contains_any: ["/etc/passwd"] } },
  });
});

test("conditionToFormState round-trips tool_denylist", async ({ page }) => {
  const result = await page.evaluate(async () => {
    const mod = await import("/src/pages/policies/condition-form/conditionUtils.ts");
    const condition = { blocked_tools: ["bash", "run_shell"] };
    return mod.conditionToFormState("tool_denylist", condition);
  });
  expect(result).toEqual({
    type: "tool_denylist",
    data: { blocked_tools: ["bash", "run_shell"], numericConditions: [], parameterMatch: {}, _extra: {} },
  });
});

test("conditionToFormState parses numeric_conditions from tool_denylist", async ({ page }) => {
  const result = await page.evaluate(async () => {
    const mod = await import("/src/pages/policies/condition-form/conditionUtils.ts");
    const condition = {
      blocked_tools: ["approve_claim_payment"],
      numeric_conditions: [{ parameter: "amount", operator: "gt", value: 5000 }],
    };
    return mod.conditionToFormState("tool_denylist", condition);
  });
  expect(result).toEqual({
    type: "tool_denylist",
    data: {
      blocked_tools: ["approve_claim_payment"],
      numericConditions: [{ field: "amount", op: ">", value: 5000 }],
      parameterMatch: {},
      _extra: {},
    },
  });
});

test("conditionToFormState preserves parameter_match in tool_denylist", async ({ page }) => {
  const result = await page.evaluate(async () => {
    const mod = await import("/src/pages/policies/condition-form/conditionUtils.ts");
    const condition = {
      blocked_tools: ["query_credit_bureau"],
      parameter_match: { applicant_id: "*" },
    };
    return mod.conditionToFormState("tool_denylist", condition);
  });
  expect(result).toEqual({
    type: "tool_denylist",
    data: {
      blocked_tools: ["query_credit_bureau"],
      numericConditions: [],
      parameterMatch: { applicant_id: "*" },
      _extra: {},
    },
  });
});

test("formStateToCondition emits numeric_conditions for tool_denylist", async ({ page }) => {
  const result = await page.evaluate(async () => {
    const mod = await import("/src/pages/policies/condition-form/conditionUtils.ts");
    const state = {
      type: "tool_denylist" as const,
      data: {
        blocked_tools: ["approve_claim_payment"],
        numericConditions: [{ field: "amount", op: ">" as const, value: 5000 }],
        parameterMatch: {},
        _extra: {},
      },
    };
    return mod.formStateToCondition(state);
  });
  expect(result).toEqual({
    blocked_tools: ["approve_claim_payment"],
    numeric_conditions: [{ parameter: "amount", operator: "gt", value: 5000 }],
  });
});

test("formStateToCondition emits parameter_match for tool_denylist", async ({ page }) => {
  const result = await page.evaluate(async () => {
    const mod = await import("/src/pages/policies/condition-form/conditionUtils.ts");
    const state = {
      type: "tool_denylist" as const,
      data: {
        blocked_tools: ["query_credit_bureau"],
        numericConditions: [],
        parameterMatch: { applicant_id: "*" },
        _extra: {},
      },
    };
    return mod.formStateToCondition(state);
  });
  expect(result).toEqual({
    blocked_tools: ["query_credit_bureau"],
    parameter_match: { applicant_id: "*" },
  });
});

test("conditionToFormState returns null for unknown rule_type", async ({ page }) => {
  const result = await page.evaluate(async () => {
    const mod = await import("/src/pages/policies/condition-form/conditionUtils.ts");
    return mod.conditionToFormState("geo_restriction", { geo: { allowed: ["US"] } });
  });
  expect(result).toBeNull();
});

test("evaluateMatch correctly identifies tool_denylist match", async ({ page }) => {
  const result = await page.evaluate(async () => {
    const mod = await import("/src/pages/policies/condition-form/conditionUtils.ts");
    const state = {
      type: "tool_denylist" as const,
      data: { blocked_tools: ["bash", "exec_command"] },
    };
    const sample = { tool_name: "bash", tool_parameters: {}, label: "bash" };
    return mod.evaluateMatch(state, sample);
  });
  expect(result).toBe(true);
});

test("evaluateMatch correctly identifies parameter_match miss", async ({ page }) => {
  const result = await page.evaluate(async () => {
    const mod = await import("/src/pages/policies/condition-form/conditionUtils.ts");
    const state = {
      type: "parameter_match" as const,
      data: {
        rows: [{ key: "path", operator: "contains" as const, values: ["/etc"] }],
      },
    };
    const sample = { tool_name: "read_file", tool_parameters: { path: "/home/user" }, label: "safe path" };
    return mod.evaluateMatch(state, sample);
  });
  expect(result).toBe(false);
});

test("evaluateMatch wildcard key checks all parameter values", async ({ page }) => {
  const result = await page.evaluate(async () => {
    const mod = await import("/src/pages/policies/condition-form/conditionUtils.ts");
    const state = {
      type: "parameter_match" as const,
      data: {
        rows: [{ key: "*", operator: "contains" as const, values: ["jailbreak"] }],
      },
    };
    const sample = {
      tool_name: "call_tool",
      tool_parameters: { note: "please jailbreak this" },
      label: "injection",
    };
    return mod.evaluateMatch(state, sample);
  });
  expect(result).toBe(true);
});

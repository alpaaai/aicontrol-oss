import type { PolicyScope } from "../../api/policies";
import { PolicyChip } from "./PolicyChip";

// The signature element. A policy is one English sentence with its scope as
// editable chips -- the same object in the policy list, the agent's "what
// governs me" list, the NL draft review, the simulation result, and the audit
// event that fired it. One representation everywhere.
//
// Fixed words are ink. Every variable is a chip. A value that cannot be
// changed is set as plain ink, never as a chip -- that rule is what makes the
// magenta mean something.

const SYMBOL: Record<string, string> = { gt: ">", gte: "≥", lt: "<", lte: "≤", eq: "=" };

const CONDITION_PHRASES: Record<string, (v: any) => string> = {
  numeric_conditions: (v) =>
    Object.entries(v as Record<string, Record<string, number>>)
      .flatMap(([field, ops]) =>
        Object.entries(ops).map(([op, n]) => `${field} ${SYMBOL[op] ?? op} ${n.toLocaleString()}`),
      )
      .join(" and "),
  tool_name_contains: (v) => `the tool name contains ${(v as string[]).join(" or ")}`,
  rate_limit: (v) => `called more than ${(v as any).max_calls} times`,
  parameter_match: (v) =>
    Object.entries(v as Record<string, unknown>).map(([k, val]) => `${k} is ${val}`).join(" and "),
  time_conditions: (v) => `outside ${(v as any).hours[0]}:00-${(v as any).hours[1]}:00`,
  token_budget: (v) => `the budget of ${(v as any).max_tokens?.toLocaleString()} tokens is exceeded`,
};

function humanizeTool(tool: string): string {
  const words = tool.split("_").filter(Boolean);
  if (words.length < 2) return words.join(" ");
  const [verb, ...rest] = words;
  const object = rest.join(" ");
  const article = /^[aeiou]/i.test(object) ? "an" : "a";
  return `${verb} ${article} ${object}`;
}

function titleCase(s: string): string {
  return s.split(/[\s_-]+/).map((w) => w[0]?.toUpperCase() + w.slice(1)).join(" ");
}

function conditionPhrase(condition: Record<string, unknown>): string | null {
  const entries = Object.entries(condition);
  if (entries.length === 0) return null;
  return entries
    .map(([key, value]) => {
      const phrase = CONDITION_PHRASES[key];
      return phrase ? phrase(value) : `${key} matches`;
    })
    .join(" and ");
}

export function PolicySentence(props: {
  policy: PolicyScope;
  variant?: "display" | "inline";
  editable?: boolean;
  onChipEdit?: (field: keyof PolicyScope, value: string) => void;
  "data-testid"?: string;
}) {
  const { policy, editable, onChipEdit } = props;
  const variant = props.variant ?? "display";
  const typographyClass = variant === "display" ? "text-sentence" : "text-sentence-inline";
  const condition = conditionPhrase(policy.condition);

  return (
    <div
      data-testid={props["data-testid"]}
      className={`${typographyClass} text-ac-ink ${variant === "display" ? "max-w-[26ch]" : ""}`}
    >
      <span>
        {policy.principalId ? (
          <PolicyChip editable={editable} onClick={() => onChipEdit?.("principalId", policy.principalId ?? "")}>
            {policy.principalId}
          </PolicyChip>
        ) : (
          "Every agent"
        )}{" "}
        may not{" "}
        {policy.actionTool ? (
          <PolicyChip editable={editable} onClick={() => onChipEdit?.("actionTool", policy.actionTool ?? "")}>
            {humanizeTool(policy.actionTool)}
          </PolicyChip>
        ) : (
          "do anything"
        )}{" "}
        {policy.resourceSystem ? (
          <>
            on{" "}
            <PolicyChip editable={editable} onClick={() => onChipEdit?.("resourceSystem", policy.resourceSystem ?? "")}>
              {titleCase(policy.resourceSystem)}
            </PolicyChip>
          </>
        ) : (
          "anywhere"
        )}
        {condition && (
          <>
            {" "}when{" "}
            <PolicyChip editable={editable}>{condition}</PolicyChip>
          </>
        )}
        .
      </span>
      {policy.effect === "review" && (
        <div className="pl-6 text-ac-body">
          {"↳"} instead: send for approval
        </div>
      )}
    </div>
  );
}

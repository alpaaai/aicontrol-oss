import { useState } from "react";
import { PolicySentence } from "@/components/primitives/PolicySentence";
import type { PolicyScope } from "@/api/policies";

// The right-hand side card in the New Policy modal (both NL and manual
// modes): a live preview of the policy being authored, before it's created.
// Human-readable is the default view -- code is one click away, never the
// other way around.
function policyScopeToCreateBody(policy: PolicyScope) {
  return {
    condition: policy.condition,
    principal_type: policy.principalType,
    principal_id: policy.principalId,
    action_tool: policy.actionTool,
    resource_system: policy.resourceSystem,
    effect: policy.effect,
  };
}

export function PolicyPreviewCard(props: { policy: PolicyScope | null; placeholder?: string }) {
  const [view, setView] = useState<"human" | "code">("human");
  const { policy } = props;

  return (
    <div data-testid="policy-preview-card" className="bg-ac-canvas-soft border border-ac-hairline rounded-lg p-4 h-full">
      <div className="flex items-center gap-1 mb-3">
        <button
          type="button"
          aria-label="Human readable view"
          aria-pressed={view === "human"}
          onClick={() => setView("human")}
          className={`px-2.5 py-1 rounded-md text-caption font-medium transition-colors duration-micro ${
            view === "human" ? "bg-ac-surface-card text-ac-ink border border-ac-hairline-strong" : "text-ac-muted hover:text-ac-body"
          }`}
        >
          Human readable
        </button>
        <button
          type="button"
          aria-label="Code view"
          aria-pressed={view === "code"}
          onClick={() => setView("code")}
          className={`px-2.5 py-1 rounded-md text-caption font-mono transition-colors duration-micro ${
            view === "code" ? "bg-ac-surface-card text-ac-ink border border-ac-hairline-strong" : "text-ac-muted hover:text-ac-body"
          }`}
        >
          {"</>"}
        </button>
      </div>

      {!policy ? (
        <p className="text-body-sm text-ac-muted">{props.placeholder ?? "Nothing to preview yet."}</p>
      ) : view === "human" ? (
        <div data-testid="policy-preview-human">
          <PolicySentence policy={policy} variant="display" />
        </div>
      ) : (
        <pre data-testid="policy-preview-code" className="text-caption font-mono text-ac-ink whitespace-pre-wrap break-words">
          {JSON.stringify(policyScopeToCreateBody(policy), null, 2)}
        </pre>
      )}
    </div>
  );
}

import { useState } from "react";
import type { Policy } from "@/api/policies";
import { CONDITION_TYPE_LABELS } from "./condition-form/conditionUtils";
import type { ConditionType } from "./condition-form/conditionUtils";
import { Eye, EyeOff, Zap } from "lucide-react";

interface Props {
  policies: Policy[];
  loading: boolean;
  onActivate: (policy: Policy) => void;
}

const actionBadge: Record<string, string> = {
  deny:   "bg-ac-deny-bg text-ac-deny",
  review: "bg-ac-review-bg text-ac-review",
  allow:  "bg-ac-allow-bg text-ac-allow",
};

const CATEGORY_ORDER = [
  "Dangerous Operations",
  "Data Protection",
  "Human Review Gates",
  "Industry: Finance",
  "Industry: Healthcare",
  "Industry: Enterprise IT",
];

function PolicyCard({
  policy,
  onActivate,
}: {
  policy: Policy;
  onActivate: () => void;
}) {
  const [previewOpen, setPreviewOpen] = useState(false);

  return (
    <div className="bg-ac-card border border-ac-border rounded-lg p-4 space-y-3 hover:border-ac-primary/30 transition-colors">
      <div className="flex items-start justify-between gap-2">
        <div>
          <p className="font-medium text-[13px] text-ac-text-primary leading-snug">
            {policy.name}
          </p>
          {policy.description && (
            <p className="text-[12px] text-ac-text-muted mt-0.5 leading-snug">
              {policy.description}
            </p>
          )}
        </div>
      </div>

      <div className="flex items-center gap-1.5 flex-wrap">
        <span
          className={`text-[10px] font-medium px-1.5 py-0.5 rounded ${
            actionBadge[policy.action] ?? "bg-gray-100 text-gray-600"
          }`}
        >
          {policy.action}
        </span>
        <span className="text-[10px] font-mono bg-gray-100 text-ac-text-muted px-1.5 py-0.5 rounded">
          {CONDITION_TYPE_LABELS[policy.rule_type as ConditionType] ?? policy.rule_type}
        </span>
        {policy.compliance_frameworks?.map((fw) => (
          <span
            key={fw}
            className="text-[10px] bg-ac-enterprise-bg text-ac-enterprise px-1.5 py-0.5 rounded font-medium"
          >
            {fw}
          </span>
        ))}
      </div>

      {previewOpen && (
        <pre className="bg-ac-night text-green-400 text-[10px] font-mono rounded-lg p-3 overflow-x-auto whitespace-pre-wrap">
          {JSON.stringify(policy.condition, null, 2)}
        </pre>
      )}

      <div className="flex gap-2">
        <button
          type="button"
          onClick={() => setPreviewOpen((v) => !v)}
          className="flex items-center gap-1 text-[12px] text-ac-text-muted hover:text-ac-primary border border-ac-border rounded-lg px-3 py-1.5 transition-colors"
        >
          {previewOpen ? <EyeOff size={12} /> : <Eye size={12} />}
          {previewOpen ? "Hide" : "Preview"}
        </button>
        <button
          type="button"
          onClick={onActivate}
          className="flex items-center gap-1 text-[12px] bg-ac-primary text-white rounded-lg px-3 py-1.5 hover:bg-ac-primary/90 transition-colors font-medium"
        >
          <Zap size={12} />
          Activate
        </button>
      </div>
    </div>
  );
}

export function PolicyLibrary({ policies, loading, onActivate }: Props) {
  if (loading) {
    return (
      <div className="grid grid-cols-2 gap-3">
        {[1, 2, 3, 4].map((i) => (
          <div key={i} className="h-32 bg-gray-50 rounded-lg animate-pulse" />
        ))}
      </div>
    );
  }

  if (policies.length === 0) {
    return (
      <div className="text-center text-sm text-ac-text-muted py-16">
        No library policies found. Run <code className="font-mono text-xs bg-gray-100 px-1 rounded">scripts/seed_library_policies.py</code> to seed them.
      </div>
    );
  }

  const byCategory = new Map<string, Policy[]>();
  for (const order of CATEGORY_ORDER) {
    byCategory.set(order, []);
  }
  for (const policy of policies) {
    const cat = policy.category ?? "Other";
    if (!byCategory.has(cat)) byCategory.set(cat, []);
    byCategory.get(cat)!.push(policy);
  }

  return (
    <div className="space-y-8">
      {[...byCategory.entries()]
        .filter(([, ps]) => ps.length > 0)
        .map(([category, ps]) => (
          <div key={category}>
            <h3 className="text-[13px] font-semibold text-ac-text-primary mb-3">
              {category}
            </h3>
            <div className="grid grid-cols-2 gap-3">
              {ps.map((policy) => (
                <PolicyCard
                  key={policy.id}
                  policy={policy}
                  onActivate={() => onActivate(policy)}
                />
              ))}
            </div>
          </div>
        ))}
    </div>
  );
}

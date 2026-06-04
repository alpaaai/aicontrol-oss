import type { Policy } from "@/api/policies";
import { Pencil, Trash2, CheckCircle, XCircle } from "lucide-react";
import { CONDITION_TYPE_LABELS } from "./condition-form/conditionUtils";
import type { ConditionType } from "./condition-form/conditionUtils";

interface Props {
  policies: Policy[];
  onEdit: (p: Policy) => void;
  onDelete: (p: Policy) => void;
}

const actionBadge: Record<string, string> = {
  deny:   "bg-ac-deny-bg text-ac-deny",
  review: "bg-ac-review-bg text-ac-review",
  allow:  "bg-ac-allow-bg text-ac-allow",
};

const conditionTypeLabel = (ruleType: string): string =>
  CONDITION_TYPE_LABELS[ruleType as ConditionType] ?? ruleType;

export function PolicyTable({ policies, onEdit, onDelete }: Props) {
  return (
    <div className="bg-ac-card border border-ac-border rounded-[10px] overflow-hidden">
      <div
        className="grid gap-3 px-4 py-2.5 text-[11px] font-medium text-ac-text-muted
                   border-b border-ac-border bg-gray-50"
        style={{ gridTemplateColumns: "1fr 110px 120px 60px 70px 70px" }}
      >
        <div>Policy</div>
        <div>Condition type</div>
        <div>Action</div>
        <div>Priority</div>
        <div>Status</div>
        <div />
      </div>

      {policies.length === 0 && (
        <div className="text-center text-sm text-ac-text-muted py-10">
          No active policies. Create your first policy or activate one from the Policy Library.
        </div>
      )}

      {policies.map((p) => (
        <div
          key={p.id}
          className="grid gap-3 px-4 py-3 text-[13px] border-b border-gray-50
                     hover:bg-gray-50/60 transition-colors items-center"
          style={{ gridTemplateColumns: "1fr 110px 120px 60px 70px 70px" }}
        >
          <div>
            <p className="font-medium text-ac-text-primary truncate">{p.name}</p>
            {p.description && (
              <p className="text-[12px] text-ac-text-muted truncate mt-0.5">
                {p.description}
              </p>
            )}
            {p.compliance_frameworks && p.compliance_frameworks.length > 0 && (
              <div className="flex gap-1 mt-1 flex-wrap">
                {p.compliance_frameworks.map((fw) => (
                  <span
                    key={fw}
                    className="text-[10px] bg-ac-enterprise-bg text-ac-enterprise px-1.5 py-0.5 rounded font-medium"
                  >
                    {fw}
                  </span>
                ))}
              </div>
            )}
          </div>

          <div>
            <span className="text-[11px] font-mono bg-gray-100 text-ac-text-muted px-2 py-0.5 rounded">
              {conditionTypeLabel(p.rule_type)}
            </span>
          </div>

          <div>
            <span
              className={`text-[11px] font-medium px-2 py-0.5 rounded ${
                actionBadge[p.action] ?? "bg-gray-100 text-gray-600"
              }`}
            >
              {p.action}
            </span>
          </div>

          <div className="text-[12px] text-ac-text-muted tabular-nums">
            {p.priority ?? 100}
          </div>

          <div>
            {p.active ? (
              <span className="flex items-center gap-1 text-[12px] text-ac-allow">
                <CheckCircle size={12} />
                Active
              </span>
            ) : (
              <span className="flex items-center gap-1 text-[12px] text-ac-text-muted">
                <XCircle size={12} />
                Inactive
              </span>
            )}
          </div>

          <div className="flex items-center gap-2">
            <button
              onClick={() => onEdit(p)}
              className="text-ac-text-muted hover:text-ac-primary transition-colors"
              aria-label={`Edit ${p.name}`}
            >
              <Pencil size={13} />
            </button>
            <button
              onClick={() => onDelete(p)}
              className="text-ac-text-muted hover:text-ac-deny transition-colors"
              aria-label={`Delete ${p.name}`}
            >
              <Trash2 size={13} />
            </button>
          </div>
        </div>
      ))}
    </div>
  );
}

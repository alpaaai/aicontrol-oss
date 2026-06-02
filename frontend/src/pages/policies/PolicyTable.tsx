import type { Policy } from "@/api/policies";
import { Pencil, Trash2, CheckCircle, XCircle } from "lucide-react";

interface Props {
  policies: Policy[];
  onEdit: (p: Policy) => void;
  onDelete: (p: Policy) => void;
}

const severityBadge: Record<string, string> = {
  low: "bg-gray-100 text-gray-600",
  medium: "bg-amber-100 text-amber-700",
  high: "bg-red-100 text-red-600",
};

export function PolicyTable({ policies, onEdit, onDelete }: Props) {
  return (
    <div className="bg-ac-card border border-ac-border rounded-[10px] overflow-hidden">
      <div
        className="grid gap-3 px-4 py-2.5 text-[11px] font-medium text-ac-text-muted
                   uppercase tracking-wide border-b border-ac-border bg-gray-50"
        style={{ gridTemplateColumns: "1fr 80px 120px 180px 70px 80px" }}
      >
        <div>Policy</div>
        <div>Severity</div>
        <div>Type</div>
        <div>Compliance</div>
        <div>Status</div>
        <div />
      </div>

      {policies.length === 0 && (
        <div className="text-center text-sm text-ac-text-muted py-10">
          No policies yet. Create your first policy.
        </div>
      )}

      {policies.map((p) => (
        <div
          key={p.id}
          className="grid gap-3 px-4 py-3 text-[13px] border-b border-gray-50
                     hover:bg-gray-50/60 transition-colors"
          style={{ gridTemplateColumns: "1fr 80px 120px 180px 70px 80px" }}
        >
          <div>
            <p className="font-medium text-ac-text-primary truncate">{p.name}</p>
            {p.description && (
              <p className="text-[12px] text-ac-text-muted truncate mt-0.5">
                {p.description}
              </p>
            )}
            {p.created_by && (
              <p className="text-[11px] text-ac-text-muted mt-0.5">by {p.created_by}</p>
            )}
          </div>
          <div className="flex items-center">
            {p.severity ? (
              <span
                className={`text-[10px] font-medium px-1.5 py-0.5 rounded ${
                  severityBadge[p.severity] ?? "bg-gray-100 text-gray-600"
                }`}
              >
                {p.severity}
              </span>
            ) : (
              <span className="text-[11px] text-ac-text-muted">—</span>
            )}
          </div>
          <div className="flex items-center">
            <span className="text-[12px] font-mono text-ac-text-primary bg-gray-100 px-2 py-0.5 rounded">
              {p.rule_type}
            </span>
          </div>
          <div className="flex items-center gap-1 flex-wrap">
            {p.compliance_frameworks?.map((tag) => (
              <span
                key={tag}
                className="text-[10px] bg-ac-enterprise-bg text-ac-enterprise px-1.5 py-0.5 rounded font-medium"
              >
                {tag}
              </span>
            ))}
            {p.applies_to_agents > 0 && (
              <span className="text-[10px] bg-gray-100 text-gray-600 px-1.5 py-0.5 rounded">
                {p.applies_to_agents} agent{p.applies_to_agents !== 1 ? "s" : ""}
              </span>
            )}
          </div>
          <div className="flex items-center">
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
            >
              <Pencil size={13} />
            </button>
            <button
              onClick={() => onDelete(p)}
              className="text-ac-text-muted hover:text-ac-deny transition-colors"
            >
              <Trash2 size={13} />
            </button>
          </div>
        </div>
      ))}
    </div>
  );
}

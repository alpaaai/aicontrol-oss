import type { Policy } from "@/api/policies";
import { Pencil, Trash2, CheckCircle, XCircle } from "lucide-react";

interface Props {
  policies: Policy[];
  onEdit: (p: Policy) => void;
  onDelete: (p: Policy) => void;
}

export function PolicyTable({ policies, onEdit, onDelete }: Props) {
  return (
    <div className="bg-ac-card border border-ac-border rounded-[10px] overflow-hidden">
      <div
        className="grid gap-3 px-4 py-2.5 text-[11px] font-medium text-ac-text-muted
                   uppercase tracking-wide border-b border-ac-border bg-gray-50"
        style={{ gridTemplateColumns: "1fr 120px 180px 80px 80px" }}
      >
        <div>Policy</div>
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
          style={{ gridTemplateColumns: "1fr 120px 180px 80px 80px" }}
        >
          <div>
            <p className="font-medium text-ac-text-primary truncate">{p.name}</p>
            {p.description && (
              <p className="text-[12px] text-ac-text-muted truncate mt-0.5">
                {p.description}
              </p>
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

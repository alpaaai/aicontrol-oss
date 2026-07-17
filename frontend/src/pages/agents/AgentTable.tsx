import type { Agent } from "@/api/agents";

interface Props {
  agents: Agent[];
  selectedId: string | null;
  onSelect: (a: Agent) => void;
}

function stalenessClass(lastActive: string | null): string {
  if (!lastActive) return "text-ac-text-muted";
  const days = (Date.now() - new Date(lastActive).getTime()) / 86400000;
  if (days > 90) return "text-red-500";
  if (days > 30) return "text-amber-500";
  return "text-ac-text-primary";
}

export function AgentTable({ agents, selectedId, onSelect }: Props) {
  return (
    <div className="bg-ac-card border border-ac-border rounded-lg overflow-y-auto flex-1">
      <div
        className="grid gap-3 px-4 py-2.5 text-[11px] font-medium text-ac-text-muted
                   uppercase tracking-wide border-b border-ac-border bg-gray-50"
        style={{ gridTemplateColumns: "1fr 70px 110px 80px 80px 70px" }}
      >
        <div>Agent</div>
        <div>Tools</div>
        <div>Framework</div>
        <div>Status</div>
        <div>Last active</div>
        <div>Deny %</div>
      </div>

      {agents.length === 0 && (
        <div className="text-center text-sm text-ac-text-muted py-10">
          No agents registered yet.
        </div>
      )}

      {agents.map((a) => (
        <div
          key={a.id}
          onClick={() => onSelect(a)}
          className={`grid gap-3 px-4 py-3 text-[13px] border-b border-gray-50
                      cursor-pointer transition-colors
                      ${
                        selectedId === a.id
                          ? "bg-ac-primary-bg"
                          : "hover:bg-ac-peacock-50"
                      }`}
          style={{ gridTemplateColumns: "1fr 70px 110px 80px 80px 70px" }}
        >
          <div>
            <p className="font-medium text-ac-text-primary">{a.name}</p>
            {a.owner && (
              <p className="text-[12px] text-ac-text-muted">{a.owner}</p>
            )}
          </div>
          <div className="flex items-center text-ac-text-muted">
            {a.approved_tools.length}
          </div>
          <div className="flex items-center text-[12px] font-mono text-ac-text-muted">
            {a.framework ?? "—"}
          </div>
          <div className="flex items-center">
            <span
              className={`text-[12px] font-medium ${
                a.status === "active" ? "text-ac-allow" : "text-ac-text-muted"
              }`}
            >
              {a.status}
            </span>
          </div>
          <div className={`flex items-center text-[12px] ${stalenessClass(a.last_active)}`}>
            {a.last_active
              ? new Date(a.last_active).toLocaleDateString()
              : "Never"}
          </div>
          <div className="flex items-center text-[12px]">
            {a.deny_rate != null ? (
              <span className={a.deny_rate > 0.2 ? "text-red-500 font-medium" : a.deny_rate > 0.05 ? "text-amber-500" : "text-ac-text-muted"}>
                {(a.deny_rate * 100).toFixed(1)}%
              </span>
            ) : (
              <span className="text-ac-text-muted">—</span>
            )}
          </div>
        </div>
      ))}
    </div>
  );
}

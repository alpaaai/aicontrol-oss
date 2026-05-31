import type { Agent } from "@/api/agents";

interface Props {
  agents: Agent[];
  selectedId: string | null;
  onSelect: (a: Agent) => void;
}

export function AgentTable({ agents, selectedId, onSelect }: Props) {
  return (
    <div className="bg-ac-card border border-ac-border rounded-[10px] overflow-y-auto flex-1">
      <div
        className="grid gap-3 px-4 py-2.5 text-[11px] font-medium text-ac-text-muted
                   uppercase tracking-wide border-b border-ac-border bg-gray-50"
        style={{ gridTemplateColumns: "1fr 100px 120px 80px" }}
      >
        <div>Agent</div>
        <div>Tools</div>
        <div>Framework</div>
        <div>Status</div>
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
                          : "hover:bg-gray-50"
                      }`}
          style={{ gridTemplateColumns: "1fr 100px 120px 80px" }}
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
        </div>
      ))}
    </div>
  );
}
